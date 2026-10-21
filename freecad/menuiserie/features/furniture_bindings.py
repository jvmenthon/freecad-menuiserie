# SPDX-License-Identifier: LGPL-2.1-or-later
"""Membres d'un ensemble vus par ``core.furniture`` et liaisons dans le document (§ 4.4.3).

Lecture : chaque membre devient un :class:`Member` (bloc ou boîte relatifs à l'``Origin`` de
l'ensemble, options, propriétés pilotées par l'utilisateur). Écriture : ``setExpression`` puis
relecture du texte normalisé par FreeCAD, enregistré dans ``FurnitureBindings`` ; retrait :
seulement les expressions dont le texte est celui enregistré. Un objet n'écrit jamais dans un
autre : :func:`member_option_changed` ne relie que le membre modifié.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from freecad.menuiserie.core.furniture import (
    Binding,
    Edge,
    FurnitureBox,
    FurnitureError,
    InteriorMode,
    Member,
    Notice,
    bindings_for,
    check_resize,
    driven_properties,
    follow_rules,
    predict,
    same_binding,
    with_default_options,
)
from freecad.menuiserie.core.geometry import PlacedBlock, RigidTransform, Vec3
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.furniture import (
    OPTIONS,
    follows_user_changes,
    furniture_of,
    is_furniture,
    option_name,
    origin_of,
    writing,
)
from freecad.menuiserie.features.i18n import (
    report_warning,
    templated_message,
    translated,
    translated_errors,
)
from freecad.menuiserie.features.joints.base import is_joint
from freecad.menuiserie.features.machined_part import machined_part_of
from freecad.menuiserie.features.solids import rigid_transform
from freecad.menuiserie.features.wood_part import dimensions_of, is_wood_part

__all__ = [
    "MemberSet",
    "bind_members",
    "expressions_of",
    "joined_pairs",
    "member_of",
    "member_option_changed",
    "members_of",
    "notice_messages",
    "read_members",
    "rebind",
    "remove_bindings",
    "report",
    "report_resize",
    "resize_notices",
]

_JOINT_GROUP = "Assembly::JointGroup"  # joints de l'atelier Assembly intégré (sans import)


@dataclass(frozen=True)
class MemberSet:
    """Ensemble lu dans le document : cotes, ``Origin``, membres et objets par clé (``Name``)."""

    furniture: DocumentObject
    box: FurnitureBox
    members: tuple[Member, ...]
    objects: Mapping[str, DocumentObject]


def expressions_of(obj: DocumentObject) -> dict[str, str]:
    """Expressions de ``obj`` par chemin de propriété (``Placement.Base.y``, sans le point
    initial que FreeCAD ajoute aux sous-chemins)."""
    return {path.lstrip("."): text for path, text in obj.ExpressionEngine}


def members_of(furniture: DocumentObject) -> list[DocumentObject]:
    """Membres directs de ``furniture`` (``InList`` filtrée par le lien ``Furniture``), par nom."""
    found = {obj.Name: obj for obj in furniture.InList if furniture_of(obj) == furniture}
    return [found[name] for name in sorted(found)]


def _in_joint_group(obj: DocumentObject) -> bool:
    return obj.TypeId == _JOINT_GROUP or any(parent.TypeId == _JOINT_GROUP for parent in obj.InList)


def _assembly_constrained(obj: DocumentObject) -> bool:
    """Vrai si un joint de l'atelier Assembly cite ``obj`` (ou sa pièce usinée) : sa position
    est alors une « contrainte » de l'utilisateur (détection au mieux, risque R6)."""
    candidates = [obj]
    machined = machined_part_of(obj) if is_wood_part(obj) else None
    if machined is not None:
        candidates.append(machined)
    return any(_in_joint_group(parent) for item in candidates for parent in item.InList)


def _driven(obj: DocumentObject, entering: bool) -> frozenset[str]:
    recorded = {} if entering else dict(obj.FurnitureBindings)
    driven = driven_properties(expressions_of(obj), recorded)
    return driven | {"Placement"} if _assembly_constrained(obj) else driven


def _mode(obj: DocumentObject) -> InteriorMode:
    try:
        return InteriorMode(getattr(obj, "PositionMode", InteriorMode.STAY.value))
    except ValueError:  # valeur d'une version plus récente : la pièce ne bouge pas
        return InteriorMode.STAY


def _fixed(obj: DocumentObject) -> frozenset[Edge]:
    return frozenset(edge for edge in Edge if bool(getattr(obj, option_name(edge), False)))


def _relative(point: Vec3, origin: Vec3) -> Vec3:
    return Vec3(point.x - origin.x, point.y - origin.y, point.z - origin.z)


def member_of(obj: DocumentObject, origin: Vec3, *, entering: bool = False) -> Member:
    """Membre vu par ``core`` dans le repère de l'ensemble d'``Origin`` ``origin``.

    ``entering`` : objet qui entre dans l'ensemble (options à calculer, toutes ses expressions
    sont des formules de l'utilisateur). ``ValueError`` traduite pour une cote invalide."""
    common = {
        "key": obj.Name,
        "label": str(obj.Label),
        "mode": InteriorMode.STAY if entering else _mode(obj),
        "fixed": None if entering else _fixed(obj),
        "driven": _driven(obj, entering),
    }
    with translated_errors():
        if is_furniture(obj):
            box = FurnitureBox(obj.Width.Value, obj.Depth.Value, obj.Height.Value)
            return Member(box=box, origin=_relative(origin_of(obj), origin), **common)
        transform = rigid_transform(obj.Placement)
        placement = RigidTransform(transform.rotation, _relative(transform.translation, origin))
        return Member(block=PlacedBlock(dimensions_of(obj), placement), **common)


def read_members(
    furniture: DocumentObject,
    entering: Sequence[DocumentObject] = (),
    box: FurnitureBox | None = None,
) -> MemberSet:
    """Membres de ``furniture`` et objets ``entering``, options manquantes calculées (F3) ;
    ``box`` remplace les cotes actuelles (aperçu d'un redimensionnement)."""
    with translated_errors():
        current = box or FurnitureBox(
            furniture.Width.Value, furniture.Depth.Value, furniture.Height.Value
        )
    origin = origin_of(furniture)
    objects = [*members_of(furniture), *entering]
    entering_names = {obj.Name for obj in entering}
    members = [member_of(obj, origin, entering=obj.Name in entering_names) for obj in objects]
    resolved = with_default_options(current, members)
    return MemberSet(furniture, current, resolved, {obj.Name: obj for obj in objects})


def _bindings(members: MemberSet, keys: Iterable[str]) -> tuple[list[Binding], list[Notice]]:
    """Liaisons et avertissements des membres ``keys`` (règles et liaisons de ``core``)."""
    chosen = set(keys)
    subset = [member for member in members.members if member.key in chosen]
    rules, rule_notices = follow_rules(members.box, subset)
    nested = furniture_of(members.furniture) is not None
    with translated_errors():
        bindings, notices = bindings_for(
            str(members.furniture.Label), members.box, subset, rules, nested=nested
        )
    return list(bindings), [*rule_notices, *notices]


def remove_bindings(obj: DocumentObject) -> None:
    """Retire de ``obj`` les seules liaisons de l'atelier (texte = celui enregistré)."""
    current = expressions_of(obj)
    for prop, text in dict(getattr(obj, "FurnitureBindings", {})).items():
        if prop in current and same_binding(current[prop], text):
            obj.setExpression(prop, None)


def _write(obj: DocumentObject, bindings: Sequence[Binding]) -> None:
    """Remplace les liaisons de l'atelier de ``obj`` par ``bindings`` ; textes relus."""
    with writing(obj):
        remove_bindings(obj)
        recorded: dict[str, str] = {}
        for binding in bindings:
            obj.setExpression(binding.prop, binding.expression)
            recorded[binding.prop] = expressions_of(obj)[binding.prop]
        obj.FurnitureBindings = recorded


def bind_members(members: MemberSet, keys: Iterable[str]) -> list[Notice]:
    """Calcule et écrit les liaisons des membres ``keys`` d'après la géométrie actuelle et
    leurs options ; renvoie les avertissements."""
    chosen = sorted(set(keys))
    bindings, notices = _bindings(members, chosen)
    for key in chosen:
        _write(members.objects[key], [b for b in bindings if b.key == key])
    return notices


def rebind(furniture: DocumentObject) -> list[Notice]:
    """Relie tous les membres de ``furniture``, puis ceux de ses sous-ensembles, d'après la
    géométrie actuelle et les options enregistrées (« Relier les pièces »)."""
    members = read_members(furniture)
    notices = bind_members(members, members.objects)
    for obj in members.objects.values():
        if is_furniture(obj):
            notices.extend(rebind(obj))
    return notices


def joined_pairs(members: MemberSet) -> list[tuple[str, str]]:
    """Paires (hôte, invitée) des assemblages dont les deux brutes sont membres."""
    pairs = {
        (parent.HostPart.Name, parent.GuestPart.Name)
        for obj in members.objects.values()
        for parent in obj.InList
        if is_joint(parent) and parent.HostPart is not None and parent.GuestPart is not None
    }
    return sorted(pair for pair in pairs if set(pair) <= members.objects.keys())


def resize_notices(furniture: DocumentObject, old: FurnitureBox, new: FurnitureBox) -> list[Notice]:
    """Contrôle (``check_resize``) du passage de ``old`` à ``new``, puis, pour chaque
    sous-ensemble dont les cotes changeraient, de ses propres membres.
    :class:`FurnitureError` si le redimensionnement est refusé."""
    members = read_members(furniture, box=old)
    rules, _ = follow_rules(old, members.members)
    notices = list(check_resize(old, new, members.members, rules, joined_pairs(members)))
    after = predict(old, new, members.members, rules)
    for member in members.members:
        moved = after.get(member.key)
        new_box = moved.box if moved is not None else None
        if member.box is not None and new_box is not None and new_box != member.box:
            notices.extend(resize_notices(members.objects[member.key], member.box, new_box))
    return notices


def notice_messages(notices: Iterable[Notice]) -> tuple[str, ...]:
    """Avertissements traduits, sans doublon, dans l'ordre."""
    messages = (translated(notice.template, notice.params) for notice in notices)
    return tuple(dict.fromkeys(messages))


def report(messages: Iterable[str]) -> None:
    """Avertissements dans la vue rapport."""
    for message in messages:
        report_warning(message)


def report_resize(furniture: DocumentObject, old: FurnitureBox, new: FurnitureBox) -> None:
    """Cote saisie dans l'éditeur de propriétés : elle est appliquée (Q4) ; avertissements
    pour les formules de l'utilisateur et pour une pièce ou un assemblage cassé."""
    try:
        report(notice_messages(resize_notices(furniture, old, new)))
    except FurnitureError as error:
        report([templated_message(error)])
    except ValueError as error:  # membre illisible : rien à contrôler de plus
        report([str(error)])


def member_option_changed(obj: DocumentObject, prop: str) -> None:
    """Option ou mode changé par l'utilisateur (éditeur de propriétés, script) : recalcule
    et écrit les seules liaisons de ``obj``, dans la transaction en cours."""
    if prop != "PositionMode" and prop not in OPTIONS:
        return
    furniture = furniture_of(obj)
    if furniture is None or not follows_user_changes(obj):  # ni recalcul, ni annulation
        return
    try:
        report(notice_messages(bind_members(read_members(furniture), [obj.Name])))
    except ValueError as error:  # libellé ou cote illisible : liaisons laissées telles quelles
        report([str(error)])
