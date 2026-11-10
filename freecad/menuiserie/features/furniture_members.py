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
    is_furniture,
    option_name,
    writing,
)
from freecad.menuiserie.features.furniture_bindings import (
    MemberSet,
    bind_members,
    member_of,
    read_members,
    rebind,
    remove_bindings,
)
from freecad.menuiserie.features.furniture_checks import (
    NOT_IN_FURNITURE,
    checked_furniture,
    member_object,
    quoted_label,
)
from freecad.menuiserie.features.furniture_container import (
    create_with_std_part,
    outer_container,
    placement_container,
    scopes,
    std_part_of,
)
from freecad.menuiserie.features.furniture_detach import detach_members, remove_members
from freecad.menuiserie.features.furniture_enclosing import enclosing
from freecad.menuiserie.features.furniture_entry import adopt, leave, taken_along
from freecad.menuiserie.features.furniture_plan import (
    EntryNoticeKind,
    Placement,
    chain_of,
    check_assembled,
    plan_entry,
    redirection_notice,
    split_creation,
)
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
    "join_with_options",
    "member_object",
    "planned_resize",
    "quoted_label",
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


def _in_scope(
    member: DocumentObject, allowed: Sequence[DocumentObject | None], *, relative: bool
) -> bool:
    """Le conteneur de ``member`` est l'un des ``allowed``. ``relative`` (un membre qui change
    d'ensemble) : on compare les conteneurs hors Std Parts d'ensemble, car un membre de A n'est
    pas dans le conteneur du Std Part de B mais dans celui de A."""
    container = placement_container(member)
    if not relative:
        return container in allowed
    return outer_container(container) in {outer_container(item) for item in allowed}


def _checked(
    obj: DocumentObject,
    doc: object,
    allowed: Sequence[DocumentObject | None],
    furniture: DocumentObject | None,
    move: bool = False,
) -> DocumentObject:
    member = member_object(obj)
    if member.Document != doc:
        raise ValueError(translated(_OTHER_DOCUMENT, quoted_label(member)))
    current = furniture_of(member)
    if current is not None and (not move or current == furniture):  # déjà là : options gardées
        params = {**quoted_label(member), "furniture": quoted_value(current.Label)}
        raise ValueError(translated(_ALREADY_MEMBER, params))
    if furniture is not None and is_furniture(member):
        parents, labels = _ancestry(furniture)
        labels[member.Name] = str(member.Label)
        try:
            check_membership(furniture.Name, member.Name, parents, labels)
        except FurnitureError as error:
            raise ValueError(templated_message(error)) from error
    if not _in_scope(member, allowed, relative=move and current is not None):
        raise ValueError(translated(_OTHER_CONTAINER, quoted_label(member)))
    return member


def _candidates(
    objects: Sequence[DocumentObject], furniture: DocumentObject | None, move: bool = False
) -> list[DocumentObject]:
    """Objets qui entrent dans l'ensemble (brutes ou ensembles, sans doublon), contrôlés :
    même document et même conteneur que le Std Part de l'ensemble (ou que le premier objet), aucun
    membre d'un ensemble (sauf avec ``move``, où ils changent d'ensemble), aucun cycle."""
    if not objects:
        raise ValueError(translated(_NO_OBJECT))
    reference = furniture if furniture is not None else member_object(objects[0])
    allowed = scopes(furniture) if furniture is not None else (placement_container(reference),)
    found: dict[str, DocumentObject] = {}
    for obj in objects:
        member = _checked(obj, reference.Document, allowed, furniture, move)
        found.setdefault(member.Name, member)
    return list(found.values())


def _join(obj: DocumentObject, furniture: DocumentObject, fixed: frozenset[Edge]) -> None:
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
            _join(entering.objects[member.key], furniture, member.fixed or frozenset())
    notices.extend(bind_members(entering, [obj.Name for obj in objects]))
    for obj in objects:
        if is_furniture(obj):
            notices.extend(rebind(obj))
    return notices


def _checked_label(label: str) -> str:
    with translated_errors():
        label_reference(label)
    return label


def _common_parent(objects: Sequence[DocumentObject]) -> DocumentObject | None:
    """Ensemble dont tous les ``objects`` sont membres (ADR 0037), ``None`` sinon."""
    parents = {furniture_of(member_object(obj)) for obj in objects}
    parent = next(iter(parents), None)
    return parent if len(parents) == 1 else None


def build_furniture(
    objects: Sequence[DocumentObject], label: str = ""
) -> tuple[DocumentObject, list[Notice]]:
    """Crée un ensemble autour de ``objects`` (boîte qui les contient) et les y fait entrer ;
    tout est contrôlé avant la création. Des objets tous membres d'un même ensemble en sortent
    (propriétés gardées : Ctrl+Z les rétablit, FreeCAD 1.1) et le nouvel ensemble, membre de ce
    parent, les reçoit (sous-ensemble, ADR 0037). Une pièce assemblée à une pièce qui reste dans
    le parent y reste (avertissement) ; ``ValueError`` s'il ne reste rien à ranger ou si
    l'assemblage mène à un autre ensemble. Un refus après la sortie relève de la transaction de
    l'appelant (annulation)."""
    parent = _common_parent(objects)
    if parent is None:
        members = _candidates(objects, None)
    else:
        members = list({m.Name: m for m in map(member_object, objects)}.values())
    wanted = ("", *chain_of(parent))
    entering, notices = split_creation(plan_entry(members, wanted), wanted, parent)
    _checked_label(label or translated(DEFAULT_LABEL))
    if parent is not None:
        detach_members(entering, keep_properties=True)
    furniture, more = _create(entering, label)
    notices += more
    return furniture, notices if parent is None else [*notices, *add_members(parent, [furniture])]


def _create(objects: Sequence[DocumentObject], label: str) -> tuple[DocumentObject, list[Notice]]:
    """Ensemble neuf autour de ``objects``, de plus haut niveau ou dans leur conteneur."""
    members = _candidates(objects, None)
    text = _checked_label(label or translated(DEFAULT_LABEL))
    box, origin = enclosing(members)
    for obj in members:
        member_of(obj, origin, entering=True)  # cote illisible : refus avant création
    outer = placement_container(members[0])
    furniture = create_with_std_part(members[0].Document, box, origin, text, outer)
    return furniture, _enter(furniture, members)


def add_members(
    furniture: DocumentObject, objects: Sequence[DocumentObject], *, move: bool = False
) -> list[Notice]:
    """Fait entrer ``objects`` dans ``furniture`` ; les membres présents gardent leurs options
    et leurs liaisons. Une pièce assemblée à une pièce qui reste dans un autre ensemble va dans
    l'ensemble cohérent le plus proche (celui de cette pièce, s'il est dans la même branche) et
    non dans ``furniture`` : avertissement ; ``ValueError`` s'il n'y a aucun rangement cohérent.
    Avec ``move``, des objets déjà membres d'un autre ensemble en sortent
    (:func:`detach_members`, propriétés gardées, puis :func:`leave`) et entrent ici avec les
    options par défaut."""
    checked_furniture(furniture)
    members = _candidates(objects, furniture, move)
    _checked_label(str(furniture.Label))
    read_members(furniture, entering=members)  # cotes illisibles : refus avant modification
    wanted = chain_of(furniture)
    homes: dict[str, list[DocumentObject]] = {}
    redirected: list[tuple[Placement, DocumentObject]] = []
    for placement in plan_entry(members, wanted):
        home = furniture if placement.dest == wanted else _ensemble(furniture, placement.dest[0])
        homes.setdefault(home.Name, []).append(placement.obj)
        if placement.dest != wanted:
            redirected.append((placement, home))
    notices: list[Notice] = []
    for name, group in homes.items():
        home = furniture if name == furniture.Name else _ensemble(furniture, name)
        notices += _enter_in(home, group)
    for placement, home in redirected:
        stays = placement.obj not in homes[home.Name] or furniture_of(placement.obj) == home
        kind = EntryNoticeKind.STAYED if stays else EntryNoticeKind.REDIRECTED
        notices.append(redirection_notice(placement, furniture, home, kind))
    return notices


def _ensemble(reference: DocumentObject, name: str) -> DocumentObject:
    """Ensemble de nom ``name`` du document de ``reference``."""
    found: DocumentObject = reference.Document.getObject(name)
    return found


def _enter_in(home: DocumentObject, group: Sequence[DocumentObject]) -> list[Notice]:
    """Fait entrer ``group`` dans ``home`` ; ceux qui y sont déjà ne bougent pas, ceux d'un autre
    ensemble en sortent d'abord (propriétés gardées)."""
    coming = [member for member in group if furniture_of(member) != home]
    leaving = [member for member in coming if furniture_of(member) is not None]
    if leaving:
        leave(detach_members(leaving, keep_properties=True))
    return _enter(home, coming) if coming else []


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
        _join(member, furniture, fixed)
        with writing(member):
            member.PositionMode = mode.value
    return bind_members(read_members(furniture), [member.Name for member in members])
