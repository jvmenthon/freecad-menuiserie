# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fabrique de l'ensemble et gestion de ses membres (J4b', critères N1, N7, N8, N11).

Chaque opération valide tout avant de modifier le document (``TypeError`` ou ``ValueError``
traduites), puis écrit les propriétés de membre et les liaisons. Ni transaction ni recalcul :
c'est à l'appelant (``api.py``, commandes) de les faire.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from typing import Final

from freecad.menuiserie.core.furniture import (
    Edge,
    FurnitureBox,
    FurnitureError,
    InteriorMode,
    Notice,
    check_membership,
    label_reference,
)
from freecad.menuiserie.core.geometry import Vec3
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.text import quoted_value
from freecad.menuiserie.features import schema
from freecad.menuiserie.features.freecad_types import DocumentObject, expressions_of
from freecad.menuiserie.features.furniture import (
    DEFAULT_LABEL,
    DIMENSIONS,
    MEMBER_PROPERTIES,
    MODES,
    create_furniture,
    furniture_of,
    has_member_properties,
    is_furniture,
    option_name,
    origin_of,
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
from freecad.menuiserie.features.furniture_relink import relink_remaining
from freecad.menuiserie.features.furniture_variants import resize_notices
from freecad.menuiserie.features.i18n import templated_message, translated, translated_errors
from freecad.menuiserie.features.machined_part import blank_of
from freecad.menuiserie.features.solids import rigid_transform
from freecad.menuiserie.features.wood_part import dimensions_of

__all__ = [
    "NOT_IN_FURNITURE",
    "UNKNOWN_EDGE",
    "add_members",
    "build_furniture",
    "checked_furniture",
    "join_with_options",
    "member_object",
    "quoted_label",
    "relink",
    "remove_members",
    "resize",
    "set_options",
]

_NOT_A_MEMBER: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "« {label} » n'est ni une pièce de bois, ni une pièce usinée, ni un ensemble."
)
_NOT_FURNITURE: Final = QT_TRANSLATE_NOOP("Menuiserie", "« {label} » n'est pas un ensemble.")
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
_DRIVEN_DIMENSION: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "« {label} » : {property} suit une expression ; modifiez cette expression ou l'ensemble "
    "qui la pilote.",
)


def quoted_label(obj: DocumentObject) -> dict[str, str]:
    return {"label": quoted_value(getattr(obj, "Label", obj))}


def member_object(obj: DocumentObject) -> DocumentObject:
    """Objet qui porte les propriétés de membre : l'ensemble lui-même, ou la brute d'une pièce
    (de bois ou usinée) ; ``TypeError`` traduite sinon."""
    if is_furniture(obj):
        return obj
    try:
        return blank_of(obj)
    except TypeError:
        raise TypeError(translated(_NOT_A_MEMBER, quoted_label(obj))) from None


def checked_furniture(obj: DocumentObject) -> DocumentObject:
    """``obj`` s'il est un ensemble ; ``TypeError`` traduite sinon."""
    if not is_furniture(obj):
        raise TypeError(translated(_NOT_FURNITURE, quoted_label(obj)))
    return obj


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
    obj: DocumentObject, doc: object, container: object, furniture: DocumentObject | None
) -> DocumentObject:
    member = member_object(obj)
    if member.Document != doc:
        raise ValueError(translated(_OTHER_DOCUMENT, quoted_label(member)))
    current = furniture_of(member)
    if current is not None:
        params = {**quoted_label(member), "furniture": quoted_value(current.Label)}
        raise ValueError(translated(_ALREADY_MEMBER, params))
    if member.getParentGeoFeatureGroup() != container:
        raise ValueError(translated(_OTHER_CONTAINER, quoted_label(member)))
    if furniture is not None and is_furniture(member):
        parents, labels = _ancestry(furniture)
        labels[member.Name] = str(member.Label)
        try:
            check_membership(furniture.Name, member.Name, parents, labels)
        except FurnitureError as error:
            raise ValueError(templated_message(error)) from error
    return member


def _candidates(
    objects: Sequence[DocumentObject], furniture: DocumentObject | None
) -> list[DocumentObject]:
    """Objets qui entrent dans l'ensemble (brutes ou ensembles, sans doublon), contrôlés :
    même document et même conteneur que l'ensemble (ou que le premier objet), aucun membre
    d'un ensemble, aucun cycle d'ensembles."""
    if not objects:
        raise ValueError(translated(_NO_OBJECT))
    reference = furniture if furniture is not None else member_object(objects[0])
    doc, container = reference.Document, reference.getParentGeoFeatureGroup()
    found: dict[str, DocumentObject] = {}
    for obj in objects:
        member = _checked(obj, doc, container, furniture)
        found.setdefault(member.Name, member)
    return list(found.values())


def _corners(obj: DocumentObject) -> list[Vec3]:
    """Sommets de la boîte d'un membre dans le repère de son conteneur."""
    if is_furniture(obj):
        low = origin_of(obj)
        sizes = (obj.Width.Value, obj.Depth.Value, obj.Height.Value)
        return [low, Vec3(low.x + sizes[0], low.y + sizes[1], low.z + sizes[2])]
    with translated_errors():
        size = dimensions_of(obj)
    transform = rigid_transform(obj.Placement)
    return [
        transform.apply(Vec3(x, y, z))
        for x in (0.0, size.length)
        for y in (0.0, size.width)
        for z in (0.0, size.thickness)
    ]


def _enclosing(objects: Sequence[DocumentObject]) -> tuple[FurnitureBox, Vec3]:
    """Boîte qui contient les membres (cotes et coin minimal), arrondie au millionième de mm."""
    points = [point for obj in objects for point in _corners(obj)]
    low = [round(min(p.component(i) for p in points), 6) + 0.0 for i in range(3)]  # pas de -0
    high = [round(max(p.component(i) for p in points), 6) for i in range(3)]
    with translated_errors():
        box = FurnitureBox(*(hi - lo for lo, hi in zip(low, high, strict=True)))
    return box, Vec3.of(low)


def _join(obj: DocumentObject, furniture: DocumentObject, fixed: frozenset[Edge]) -> None:
    """Fait de ``obj`` un membre de ``furniture`` (mode ``Stay``, options ``fixed``, cotes non
    fixes). Les propriétés d'un orphelin (ensemble supprimé) sont réécrites, et ses anciennes
    liaisons de l'atelier retirées."""
    values: dict[str, object] = {
        "Furniture": furniture,
        "FurnitureBindings": {},
        "Locked": False,
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
    """Options par défaut (F3), propriétés de membre et liaisons des ``objects`` ; les
    sous-ensembles sont ensuite reliés à nouveau (``nested`` : leurs membres suivent leur
    ``Origin``)."""
    entering: MemberSet = read_members(furniture, entering=objects)
    for member in entering.members:
        if member.key in {obj.Name for obj in objects}:
            _join(entering.objects[member.key], furniture, member.fixed or frozenset())
    notices = bind_members(entering, [obj.Name for obj in objects])
    for obj in objects:
        if is_furniture(obj):
            notices.extend(rebind(obj))
    return notices


def _checked_label(label: str) -> str:
    with translated_errors():
        label_reference(label)
    return label


def build_furniture(
    objects: Sequence[DocumentObject], label: str = ""
) -> tuple[DocumentObject, list[Notice]]:
    """Crée un ensemble autour de ``objects`` (boîte qui les contient) et les y fait entrer ;
    tout est contrôlé avant la création."""
    members = _candidates(objects, None)
    text = _checked_label(label or translated(DEFAULT_LABEL))
    box, origin = _enclosing(members)
    for obj in members:
        member_of(obj, origin, entering=True)  # cote illisible : refus avant création
    container = members[0].getParentGeoFeatureGroup()
    furniture = create_furniture(members[0].Document, box, origin, text, container)
    return furniture, _enter(furniture, members)


def add_members(furniture: DocumentObject, objects: Sequence[DocumentObject]) -> list[Notice]:
    """Fait entrer ``objects`` dans ``furniture`` ; les membres présents gardent leurs options
    et leurs liaisons."""
    checked_furniture(furniture)
    members = _candidates(objects, furniture)
    _checked_label(str(furniture.Label))
    read_members(furniture, entering=members)  # cotes illisibles : refus avant modification
    return _enter(furniture, members)


def remove_members(objects: Sequence[DocumentObject]) -> None:
    """Retire ``objects`` de leur ensemble : seules les liaisons de l'atelier et les propriétés
    de membre sont supprimées, la géométrie ne change pas. Un orphelin (ensemble supprimé) est
    accepté. Les pièces qui restent sont reliées sans elles."""
    targets = {member.Name: member for member in map(member_object, objects)}
    for member in targets.values():
        if not has_member_properties(member):
            raise ValueError(translated(NOT_IN_FURNITURE, quoted_label(member)))
    furnitures = {f.Name: f for f in (furniture_of(m) for m in targets.values()) if f is not None}
    for member in targets.values():
        with writing(member):
            remove_bindings(member)
            for spec in MEMBER_PROPERTIES:
                if spec.name in member.PropertiesList:
                    member.removeProperty(spec.name)
    for furniture in furnitures.values():  # les voisines ne citent plus les pièces retirées
        relink_remaining(furniture, set(targets))


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


def planned_resize(
    furniture: DocumentObject, sizes: Mapping[str, float | None], unlocked: Collection[str] = ()
) -> tuple[FurnitureBox, list[Notice]]:
    """Contrôle (``check_resize``, sous-ensembles compris) des cotes ``sizes`` (``Width``,
    ``Depth``, ``Height`` ; ``None`` = inchangée) : nouvelles cotes et avertissements. Rien n'est
    écrit. ``unlocked`` : clés des pièces à considérer comme déverrouillées."""
    checked_furniture(furniture)
    old = read_members(furniture).box
    changed = {name: value for name, value in sizes.items() if value is not None}
    driven = sorted(set(changed) & set(expressions_of(furniture)))
    if driven:
        params = {**quoted_label(furniture), "property": driven[0]}
        raise ValueError(translated(_DRIVEN_DIMENSION, params))
    values = [changed.get(name, getattr(old, name.lower())) for name in DIMENSIONS]
    with translated_errors():
        new = FurnitureBox(*values)
        return new, resize_notices(furniture, old, new, unlocked)


def resize(furniture: DocumentObject, sizes: Mapping[str, float | None]) -> list[Notice]:
    """Contrôle (:func:`planned_resize`) puis écrit les cotes ``sizes``. Refus avant toute
    écriture (:class:`LockedPiecesError` si une rangée est bloquée par des pièces verrouillées)."""
    new, notices = planned_resize(furniture, sizes)
    write_box(furniture, new, sizes)
    return notices


def write_box(
    furniture: DocumentObject, new: FurnitureBox, sizes: Mapping[str, float | None]
) -> None:
    """Écrit les cotes de ``new`` dont ``sizes`` n'est pas ``None``."""
    with writing(furniture):
        for name, value in sizes.items():
            if value is not None:
                setattr(furniture, name, getattr(new, name.lower()))


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
    options = {member_object(obj).Name: (mode, fixed) for obj, mode, fixed in entries}
    for member in members:
        mode, fixed = options[member.Name]
        _join(member, furniture, fixed)
        with writing(member):
            member.PositionMode = mode.value
    return bind_members(read_members(furniture), [member.Name for member in members])
