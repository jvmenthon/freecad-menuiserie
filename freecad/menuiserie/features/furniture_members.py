# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fabrique de l'ensemble et gestion de ses membres (J4b', critères N1, N7, N8, N11).

Chaque opération valide tout avant de modifier le document (``TypeError`` ou ``ValueError``
traduites), puis écrit les propriétés de membre et les liaisons. Ni transaction ni recalcul :
c'est à l'appelant (``api.py``, commandes) de les faire.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Final

from freecad.menuiserie.core.furniture import (
    Edge,
    FurnitureError,
    InteriorMode,
    Notice,
    check_membership,
    label_reference,
)
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.text import quoted_value
from freecad.menuiserie.features import schema
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.furniture import (
    DEFAULT_LABEL,
    MEMBER_PROPERTIES,
    MODES,
    furniture_of,
    has_member_properties,
    is_furniture,
    option_name,
    writing,
)
from freecad.menuiserie.features.furniture_bindings import (
    MemberSet,
    bind_members,
    member_of,
    members_of,
    read_members,
    rebind,
    remove_bindings,
)
from freecad.menuiserie.features.furniture_checks import (
    checked_furniture,
    member_object,
    quoted_label,
)
from freecad.menuiserie.features.furniture_container import (
    create_with_std_part,
    placement_container,
    scopes,
    std_part_of,
)
from freecad.menuiserie.features.furniture_enclosing import enclosing
from freecad.menuiserie.features.furniture_entry import (
    adopt,
    check_assembled,
    dissolve,
    leave,
    taken_along,
)
from freecad.menuiserie.features.furniture_relink import relink_remaining
from freecad.menuiserie.features.furniture_resize import planned_resize, resize, write_box
from freecad.menuiserie.features.i18n import templated_message, translated, translated_errors
from freecad.menuiserie.features.shaped_part import is_shaped_part

__all__ = [
    "DRAWN_LOCKED",
    "NOT_IN_FURNITURE",
    "UNKNOWN_EDGE",
    "add_members",
    "build_furniture",
    "checked_furniture",
    "detach_members",
    "join_member",
    "join_with_options",
    "member_object",
    "planned_resize",
    "quoted_label",
    "release_furniture",
    "relink",
    "remove_members",
    "resize",
    "set_options",
    "write_box",
]

_NO_OBJECT: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Choisissez au moins une pièce pour former un ensemble."
)
_ALREADY_MEMBER: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "« {label} » est déjà membre de l'ensemble « {furniture} »."
)
NOT_IN_FURNITURE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "« {label} » n'est membre d'aucun ensemble."
)
_OTHER_DOCUMENT: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "« {label} » appartient à un autre document."
)
_OTHER_CONTAINER: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "« {label} » n'est pas dans le même conteneur (pièce ou corps) que l'ensemble et ses "
    "autres membres.",
)
_UNKNOWN_MODE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Mode de position inconnu : « {value} » (Stay ou Proportional attendu)."
)
UNKNOWN_EDGE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Option « fixe » inconnue : « {value} » (Left, Right, Front, Back, Bottom ou Top, avec "
    "vrai ou faux).",
)
_UNKNOWN_LOCKED: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Option « cotes fixes » inconnue : « {value} » (vrai ou faux attendu)."
)
DRAWN_LOCKED: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "« {label} » : cotes dessinées, toujours fixes ; une pièce en bois ne s'étire pas, "
    "modifiez le dessin.",
)


def _ancestry(furniture: DocumentObject) -> tuple[dict[str, str], dict[str, str]]:
    """Ensemble → ensemble parent, et libellés, en remontant depuis ``furniture``."""
    parents: dict[str, str] = {}
    labels = {furniture.Name: str(furniture.Label)}
    current = furniture
    while (parent := furniture_of(current)) is not None and current.Name not in parents:
        parents[current.Name] = parent.Name
        labels[parent.Name] = str(parent.Label)
        current = parent
    return parents, labels


def _checked(
    obj: DocumentObject,
    doc: object,
    allowed: Sequence[DocumentObject | None],
    furniture: DocumentObject | None,
) -> DocumentObject:
    member = member_object(obj)
    if member.Document != doc:
        raise ValueError(translated(_OTHER_DOCUMENT, quoted_label(member)))
    current = furniture_of(member)
    if current is not None:
        params = {**quoted_label(member), "furniture": quoted_value(current.Label)}
        raise ValueError(translated(_ALREADY_MEMBER, params))
    if furniture is not None and is_furniture(member):
        parents, labels = _ancestry(furniture)
        labels[member.Name] = str(member.Label)
        try:
            check_membership(furniture.Name, member.Name, parents, labels)
        except FurnitureError as error:
            raise ValueError(templated_message(error)) from error
    if placement_container(member) not in allowed:
        raise ValueError(translated(_OTHER_CONTAINER, quoted_label(member)))
    return member


def _candidates(
    objects: Sequence[DocumentObject], furniture: DocumentObject | None
) -> list[DocumentObject]:
    """Objets qui entrent dans l'ensemble (brutes ou ensembles, sans doublon), contrôlés :
    même document et même conteneur que le Std Part de l'ensemble (ou que le premier objet), aucun
    membre d'un ensemble, aucun cycle d'ensembles."""
    if not objects:
        raise ValueError(translated(_NO_OBJECT))
    reference = furniture if furniture is not None else member_object(objects[0])
    allowed = scopes(furniture) if furniture is not None else (placement_container(reference),)
    found: dict[str, DocumentObject] = {}
    for obj in objects:
        member = _checked(obj, reference.Document, allowed, furniture)
        found.setdefault(member.Name, member)
    return list(found.values())


def join_member(obj: DocumentObject, furniture: DocumentObject, fixed: frozenset[Edge]) -> None:
    """Fait de ``obj`` un membre de ``furniture`` (mode ``Stay``, options ``fixed``, cotes non
    fixes). Les propriétés d'un orphelin (ensemble supprimé) sont réécrites, et ses anciennes
    liaisons de l'atelier retirées."""
    values: dict[str, object] = {
        "Furniture": furniture,
        "FurnitureBindings": {},
        "Locked": is_shaped_part(obj),  # cotes dessinées : toujours fixes (ADR 0020, décision 8)
        **{option_name(edge): edge in fixed for edge in Edge},
    }
    with writing(obj):
        remove_bindings(obj)
        schema.add_missing_properties(obj, MEMBER_PROPERTIES, choices={"PositionMode": list(MODES)})
        obj.PositionMode = list(MODES)
        obj.PositionMode = InteriorMode.STAY.value
        for name, value in values.items():
            setattr(obj, name, value)
        schema.apply_editor_modes(obj, MEMBER_PROPERTIES)


def _enter(furniture: DocumentObject, objects: Sequence[DocumentObject]) -> list[Notice]:
    """Les ``objects`` sont rangés dans le Std Part de ``furniture`` (E1 à E3), puis reçoivent
    leurs options par défaut (F3), leurs propriétés de membre et leurs liaisons ; les
    sous-ensembles sont ensuite reliés à nouveau (leur ``Origin`` vient de passer au Std Part)."""
    notices = taken_along(objects) if std_part_of(furniture) is not None else []
    adopt(furniture, objects)
    entering: MemberSet = read_members(furniture, entering=objects)
    for member in entering.members:
        if member.key in {obj.Name for obj in objects}:
            join_member(entering.objects[member.key], furniture, member.fixed or frozenset())
    notices.extend(bind_members(entering, [obj.Name for obj in objects]))
    for obj in objects:
        if is_furniture(obj):
            notices.extend(rebind(obj))
    return notices


def _checked_label(label: str) -> str:
    with translated_errors():
        label_reference(label)
    return label


def _build_inside(
    objects: Sequence[DocumentObject], label: str
) -> tuple[DocumentObject, list[Notice]] | None:
    """Sous-ensemble de l'ensemble commun à ``objects`` (tous membres du même, ADR 0037) : les
    pièces en sortent, entrent dans le nouvel ensemble, membre du parent. ``None`` sinon. Un
    refus après la sortie relève de la transaction de l'appelant (annulation)."""
    parents = {furniture_of(member_object(obj)) for obj in objects}
    parent = next(iter(parents), None)
    if parent is None or len(parents) != 1:
        return None
    _checked_label(label or translated(DEFAULT_LABEL))
    remove_members(objects)
    furniture, notices = build_furniture(objects, label)
    return furniture, [*notices, *add_members(parent, [furniture])]


def build_furniture(
    objects: Sequence[DocumentObject], label: str = ""
) -> tuple[DocumentObject, list[Notice]]:
    """Crée un ensemble autour de ``objects`` (boîte qui les contient) et les y fait entrer ;
    tout est contrôlé avant la création."""
    if (inside := _build_inside(objects, label)) is not None:
        return inside
    members = _candidates(objects, None)
    text = _checked_label(label or translated(DEFAULT_LABEL))
    box, origin = enclosing(members)
    for obj in members:
        member_of(obj, origin, entering=True)  # cote illisible : refus avant création
    check_assembled(members)
    outer = placement_container(members[0])
    furniture = create_with_std_part(members[0].Document, box, origin, text, outer)
    return furniture, _enter(furniture, members)


def add_members(furniture: DocumentObject, objects: Sequence[DocumentObject]) -> list[Notice]:
    """Fait entrer ``objects`` dans ``furniture`` ; les membres présents gardent leurs options
    et leurs liaisons."""
    checked_furniture(furniture)
    members = _candidates(objects, furniture)
    _checked_label(str(furniture.Label))
    read_members(furniture, entering=members)  # cotes illisibles : refus avant modification
    check_assembled(members, furniture)
    return _enter(furniture, members)


def detach_members(objects: Sequence[DocumentObject]) -> list[DocumentObject]:
    """Première moitié de :func:`remove_members` : les liaisons de l'atelier et les propriétés de
    membre de ``objects`` sont supprimées, les voisines reliées sans eux ; ils ne sortent pas de
    leur Std Part. Renvoie ceux qui avaient un ensemble. ``ValueError`` traduite, avant toute
    modification, pour un objet qui n'est membre d'aucun ensemble."""
    targets = {member.Name: member for member in map(member_object, objects)}
    for member in targets.values():
        if not has_member_properties(member):
            raise ValueError(translated(NOT_IN_FURNITURE, quoted_label(member)))
    furnitures = {f.Name: f for f in (furniture_of(m) for m in targets.values()) if f is not None}
    owned = [member for member in targets.values() if furniture_of(member) is not None]
    for member in targets.values():
        with writing(member):
            remove_bindings(member)
            for spec in MEMBER_PROPERTIES:
                if spec.name in member.PropertiesList:
                    member.removeProperty(spec.name)
    for furniture in furnitures.values():  # les voisines ne citent plus les pièces retirées
        relink_remaining(furniture, set(targets))
    return owned


def remove_members(objects: Sequence[DocumentObject]) -> list[str]:
    """Retire ``objects`` de leur ensemble : les liaisons de l'atelier et les propriétés de membre
    sont supprimées, puis ils sortent du Std Part de l'ensemble sans bouger (E2) ; la géométrie
    ne change pas. Un orphelin (ensemble supprimé) est accepté. Les pièces qui restent sont
    reliées sans elles. Renvoie les avertissements traduits (pièce assemblée à une pièce qui
    reste : elle garde son Std Part)."""
    return leave(detach_members(objects))


def release_furniture(furniture: DocumentObject) -> list[str]:
    """Suppression de ``furniture`` par l'interface (avant ``removeObject``) : ses copies de
    répétition sont dissociées (ADR 0044 : leurs expressions citent son Std Part et ses pièces,
    qui sans cela ne sortiraient pas), ses membres sortent du Std Part, qui est supprimé s'il est
    vide (:func:`.furniture_entry.dissolve`). Renvoie les avertissements traduits."""
    from freecad.menuiserie.features.repeat import is_copy
    from freecad.menuiserie.features.repeat_links import detach_copies, unlink_inner_copies

    detach_copies(furniture)
    if is_copy(furniture):  # copie supprimée à la main : ses membres copiés deviennent libres
        unlink_inner_copies(furniture)
    members = members_of(furniture)
    return [*(remove_members(members) if members else []), *dissolve(furniture)]


def _checked_options(
    mode: str | None, fixed: Mapping[str, bool] | None, locked: bool | None = None
) -> dict[str, str | bool]:
    values: dict[str, str | bool] = {}
    if locked is not None:
        if not isinstance(locked, bool):
            raise ValueError(translated(_UNKNOWN_LOCKED, {"value": quoted_value(locked)}))
        values["Locked"] = locked
    if mode is not None:
        if mode not in MODES:
            raise ValueError(translated(_UNKNOWN_MODE, {"value": quoted_value(mode)}))
        values["PositionMode"] = mode
    for name, value in (fixed or {}).items():
        if name not in {edge.value for edge in Edge} or not isinstance(value, bool):
            raise ValueError(translated(UNKNOWN_EDGE, {"value": quoted_value(name)}))
        values[option_name(Edge(name))] = value
    return values


def set_options(
    obj: DocumentObject,
    mode: str | None,
    fixed: Mapping[str, bool] | None,
    locked: bool | None = None,
) -> list[Notice]:
    """Change le mode, les options « fixe » et le verrou « cotes fixes » (``locked``) d'un
    membre, puis relie tout l'ensemble : l'option d'un membre peut changer la rangée des autres
    (ADR 0019, point 6)."""
    member = member_object(obj)
    furniture = furniture_of(member)
    if furniture is None:
        raise ValueError(translated(NOT_IN_FURNITURE, quoted_label(member)))
    if locked is False and is_shaped_part(member):
        raise ValueError(translated(DRAWN_LOCKED, quoted_label(member)))
    values = _checked_options(mode, fixed, locked)
    read_members(furniture)  # cotes illisibles : refus avant modification
    with writing(member):
        for name, value in values.items():
            setattr(member, name, value)
    members = read_members(furniture)
    return bind_members(members, members.objects)


def relink(furniture: DocumentObject) -> list[Notice]:
    """« Relier les pièces » : liaisons recalculées, options gardées."""
    checked_furniture(furniture)
    _checked_label(str(furniture.Label))
    return rebind(furniture)


# --- Gabarits (J4d, ADR 0010) ---------------------------------------------------------------


def join_with_options(
    furniture: DocumentObject,
    entries: Sequence[tuple[DocumentObject, InteriorMode, frozenset[Edge]]],
) -> list[Notice]:
    """Fait entrer des pièces dans ``furniture`` avec le mode et les options « fixe » donnés
    (un gabarit fixe lui-même ses jeux et ses retraits, au lieu des options par défaut), puis
    les relie. Mêmes refus, avant toute modification, que :func:`add_members`."""
    checked_furniture(furniture)
    members = _candidates([obj for obj, _mode, _fixed in entries], furniture)
    _checked_label(str(furniture.Label))
    read_members(furniture, entering=members)  # cotes illisibles : refus avant modification
    check_assembled(members, furniture)
    adopt(furniture, members)
    options = {member_object(obj).Name: (mode, fixed) for obj, mode, fixed in entries}
    for member in members:
        mode, fixed = options[member.Name]
        join_member(member, furniture, fixed)
        with writing(member):
            member.PositionMode = mode.value
    return bind_members(read_members(furniture), [member.Name for member in members])
