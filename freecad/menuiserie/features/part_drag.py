# SPDX-License-Identifier: LGPL-2.1-or-later
"""Écriture d'un glissement à la souris : déplacer, redimensionner, annuler, relier (SM-b).

Un glissement va de :func:`begin_drag` à :func:`end_drag` (ou :func:`restore`, Échap). Pendant le
glissement, seules les propriétés de la **brute** sont écrites (``Placement``, ``Length``,
``Width``, ``Thickness``), sans recalcul du document ; ``DragMemento`` garde l'état du début
(Memento) et sert de référence : les écritures sont absolues par rapport à lui, rien ne
s'accumule. Pour un membre d'ensemble, les liaisons **de l'atelier** sur ces propriétés sont
mises de côté au début ; au relâchement tout l'ensemble est relié (ADR 0019, point 6). Une
formule de l'utilisateur n'est jamais retirée : elle rend l'axe non glissable
(:class:`DragLimits`). L'épaisseur ne se tire que sur le massif (Q4, amendée le 2026-10-26) ; pour
un membre d'ensemble elle est traitée comme une épaisseur saisie dans le panneau
(:func:`_relink_thickness`). Aucun import de ``FreeCADGui`` ; la transaction et la vue rapport
sont l'affaire de ``gui/``.

Points d'extension :

- pièce en bois (``ShapedPart``, #87) : ses cotes sont celles du dessin (sorties), donc pas de
  poignée (:func:`can_resize`, seul endroit qui décide des poignées d'une pièce) ; elle se
  déplace comme une pièce de bois, par ``Placement`` ; la famille (massif ou panneau) ne décide
  que de l'épaisseur (:func:`_solid`) ;
- Distance gardée (DI-c, B6) : au relâchement, la ``Value`` des Distances de la pièce prend la
  distance nouvelle (:func:`end_drag`, avant la liaison de l'ensemble) ; Échap la rétablit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final

import FreeCAD as App

from freecad.menuiserie.core.geometry import ANGLE_TOLERANCE, Vec3
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.magnet import THICKNESS_AXIS
from freecad.menuiserie.core.text import quoted_value
from freecad.menuiserie.features.distance import AXES, distances_touching
from freecad.menuiserie.features.freecad_types import DocumentObject, expressions_of
from freecad.menuiserie.features.furniture import furniture_of, writing
from freecad.menuiserie.features.furniture_bindings import (
    bind_members,
    notice_messages,
    read_members,
    workshop_expressions,
)
from freecad.menuiserie.features.furniture_edits import thickness_notices
from freecad.menuiserie.features.furniture_relink import relink_thickness
from freecad.menuiserie.features.furniture_variants import follow_distances
from freecad.menuiserie.features.i18n import translated, translated_errors
from freecad.menuiserie.features.joints.base import is_joint, plan_for
from freecad.menuiserie.features.machined_part import blank_of, machined_part_of
from freecad.menuiserie.features.shaped_part import is_shaped_part, is_timber
from freecad.menuiserie.features.snap_geometry import to_vec3
from freecad.menuiserie.features.wood_part_schema import part_kind

__all__ = [
    "DragLimits",
    "DragMemento",
    "begin_drag",
    "can_resize",
    "drag_limits",
    "end_drag",
    "move_part",
    "raw_part",
    "resize_part",
    "restore",
]

SIZE_PROPS: Final = ("Length", "Width", "Thickness")  # axes 0, 1 et 2 de la pièce
_BASE: Final = ("Placement.Base.x", "Placement.Base.y", "Placement.Base.z")
_TOUCHED: Final = (*_BASE, *SIZE_PROPS)
_WHOLE_PLACEMENT: Final = ("Placement", "Placement.Base")
_NO_LONGER_TOUCHING: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "L'assemblage « {label} » ne touche plus ses pièces après le déplacement : {detail}",
)
_FIXED_AXIS: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "« {label} » : l'axe {axis} est piloté par une formule, il ne peut pas bouger."
)
_FIXED_SIZE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "« {label} » : cette cote ne peut pas être tirée à la souris."
)


@dataclass(frozen=True)
class DragLimits:
    """Ce qu'un glissement a le droit de faire sur une pièce brute.

    ``fixed_axes`` : axes de la pièce (0 = X, 1 = Y, 2 = Z) dont une formule **de
    l'utilisateur** pilote la position (aucune flèche) ; ``resizable_axes`` : axes dont une
    poignée est permise (l'axe 2, l'épaisseur, seulement pour le massif), vide si la pièce est
    verrouillée ou si ses cotes ne se tirent pas (:func:`can_resize`)."""

    fixed_axes: frozenset[int] = frozenset()
    resizable_axes: frozenset[int] = frozenset()


@dataclass(frozen=True)
class DragMemento:
    """État d'une brute au début d'un glissement : placement, cotes, liaisons mises de côté
    (propriété → expression), liaisons enregistrées (``FurnitureBindings``), assemblages déjà
    invalides (pour n'avertir que des nouveaux) et ``Value`` des Distances gardées de la pièce."""

    part: DocumentObject
    placement: App.Placement
    length: float
    width: float
    thickness: float
    aside: dict[str, str]
    recorded: dict[str, str]
    invalid_joints: frozenset[str]
    distances: dict[str, float] = field(default_factory=dict)


def raw_part(obj: DocumentObject) -> DocumentObject:
    """Brute que glisser ``obj`` déplace : la brute elle-même, la ``Base`` d'une pièce usinée,
    la pièce invitée d'un assemblage (ADR 0006). ``TypeError`` traduite pour tout autre objet."""
    if is_joint(obj) and is_timber(obj.GuestPart):
        return obj.GuestPart
    return blank_of(obj)


def can_resize(part: DocumentObject) -> bool:
    """Vrai si des poignées sont permises sur la brute ``part`` : pas si elle est verrouillée
    (``Locked``, ADR 0019, B5), ni si c'est une pièce en bois : ses cotes sont celles du dessin
    (#87)."""
    return not (bool(getattr(part, "Locked", False)) or is_shaped_part(part))


def _solid(part: DocumentObject) -> bool:
    """Vrai si la brute ``part`` est du massif : seule son épaisseur se tire (Q4). Un panneau
    (contreplaqué, MDF, mélaminé) garde l'épaisseur de la bibliothèque."""
    # is_panel est une propriété : la règle Semgrep la prend à tort pour une méthode non appelée.
    # nosemgrep: python.lang.maintainability.is-function-without-parentheses
    return not part_kind(part, None).is_panel


def _user_expressions(part: DocumentObject) -> set[str]:
    return set(expressions_of(part)) - set(workshop_expressions(part))


def _coordinates(axis: int, rotation: App.Rotation) -> set[int]:
    """Coordonnées du ``Placement`` (0 = x…) que déplacer la pièce sur son axe ``axis`` change."""
    unit = [App.Vector(1, 0, 0), App.Vector(0, 1, 0), App.Vector(0, 0, 1)][axis]
    direction = rotation.multVec(unit)
    return {i for i in range(3) if abs(to_vec3(direction).component(i)) > ANGLE_TOLERANCE}


def _fixed_coordinates(user: set[str]) -> set[int]:
    if user & set(_WHOLE_PLACEMENT):
        return {0, 1, 2}
    return {i for i, path in enumerate(_BASE) if path in user}


def _driven_gap_coordinates(part: DocumentObject) -> set[int]:
    """Axes (0 = X…) des Distances gardées de ``part`` dont ``Value`` porte une expression : le
    suivi n'y touche pas (:func:`follow_distances`), la pièce glissée reviendrait au recalcul."""
    return {
        AXES.index(distance.Axis)
        for distance in distances_touching(part.Document, {part.Name})
        if "Value" in expressions_of(distance) and distance.Axis in AXES
    }


def drag_limits(part: DocumentObject) -> DragLimits:
    """Limites du glissement de la brute ``part`` (B4, B5, B6 bis) d'après ses formules **de
    l'utilisateur**, sur la pièce ou sur la ``Value`` de l'une de ses Distances gardées (les
    liaisons de l'atelier sont mises de côté, donc ne comptent pas)."""
    user = _user_expressions(part)
    coordinates = _fixed_coordinates(user) | _driven_gap_coordinates(part)
    rotation = part.Placement.Rotation
    fixed = frozenset(i for i in range(3) if _coordinates(i, rotation) & coordinates)
    if not can_resize(part):
        return DragLimits(fixed, frozenset())
    sizes = frozenset(i for i, prop in enumerate(SIZE_PROPS) if prop not in user)
    if not _solid(part):
        sizes -= {THICKNESS_AXIS}
    return DragLimits(fixed, sizes - fixed)


def _invalid_joints(part: DocumentObject) -> frozenset[str]:
    return frozenset(
        joint.Name for joint in part.InList if is_joint(joint) and "Invalid" in joint.State
    )


def begin_drag(part: DocumentObject) -> DragMemento:
    """Début d'un glissement : mémorise la brute de ``part`` et, pour un membre d'ensemble,
    met de côté les liaisons de l'atelier sur ``Placement.Base.x/y/z``, ``Length``, ``Width`` et
    ``Thickness`` (B3). Une formule de l'utilisateur n'est jamais retirée (B4)."""
    raw = raw_part(part)
    recorded = dict(raw.FurnitureBindings) if "FurnitureBindings" in raw.PropertiesList else {}
    aside = {} if furniture_of(raw) is None else dict(workshop_expressions(raw))
    aside = {prop: text for prop, text in aside.items() if prop in _TOUCHED}
    with writing(raw):
        for prop in aside:
            raw.setExpression(prop, None)
    return DragMemento(
        raw,
        App.Placement(raw.Placement),
        raw.Length.Value,
        raw.Width.Value,
        raw.Thickness.Value,
        aside,
        recorded,
        _invalid_joints(raw),
        {d.Name: d.Value.Value for d in distances_touching(raw.Document, {raw.Name})},
    )


def _write_placement(memento: DragMemento, placement: App.Placement) -> None:
    """Écrit ``placement`` dans la brute, puis dans sa pièce usinée (affichage sans recalcul)."""
    raw = memento.part
    with writing(raw):
        if raw.Placement != placement:
            raw.Placement = placement
    machined = machined_part_of(raw)
    if machined is not None and machined.Placement != placement:
        machined.Placement = placement


def _recompute_machined(raw: DocumentObject) -> None:
    """Recalcule la pièce usinée de ``raw`` (affichage pendant le glissement), sauf si l'un de ses
    assemblages ne tient plus : son ``execute()`` lèverait à chaque appel et FreeCAD imprimerait
    sa trace à chaque image. Le recalcul du document au relâchement la reprend et prévient
    (:func:`end_drag`, B7)."""
    machined = machined_part_of(raw)
    if machined is None:
        return
    for joint in getattr(machined, "Joints", ()):
        try:
            plan_for(joint)
        except ValueError:
            return
    machined.recompute()


def _shifted(memento: DragMemento, shift: Vec3) -> App.Placement:
    """Placement du début décalé de ``shift`` (mm, repère de la pièce)."""
    start = memento.placement
    offset = start.Rotation.multVec(App.Vector(shift.x, shift.y, shift.z))
    return App.Placement(start.Base + offset, start.Rotation)


def _check_axes(memento: DragMemento, shift: Vec3) -> None:
    fixed = drag_limits(memento.part).fixed_axes
    for axis in fixed:
        if abs(shift.component(axis)) > ANGLE_TOLERANCE:
            params = {"label": str(memento.part.Label), "axis": "XYZ"[axis]}
            raise ValueError(translated(_FIXED_AXIS, params))


def move_part(memento: DragMemento, delta: Vec3) -> None:
    """Place la brute à ``delta`` mm (repère de la pièce) de sa position du début (B2) ; sans
    recalcul du document. ``ValueError`` traduite si ``delta`` bouge un axe fixé par une formule
    de l'utilisateur."""
    _check_axes(memento, delta)
    _write_placement(memento, _shifted(memento, delta))


def resize_part(memento: DragMemento, prop: str, value: float, origin_shift: Vec3) -> None:
    """Fixe ``Length``, ``Width`` ou ``Thickness`` (``prop``) de la brute à ``value`` mm et décale
    son origine de ``origin_shift`` (repère de la pièce, d'après le début ; poignée de début) (B2).
    Seule la brute et sa pièce usinée sont recalculées, pas le document. ``ValueError`` traduite
    si la cote ne peut pas être tirée (:func:`drag_limits`)."""
    allowed = drag_limits(memento.part).resizable_axes
    if prop not in SIZE_PROPS or SIZE_PROPS.index(prop) not in allowed:
        raise ValueError(translated(_FIXED_SIZE, {"label": str(memento.part.Label)}))
    raw = memento.part
    with writing(raw):
        setattr(raw, prop, value)
    _write_placement(memento, _shifted(memento, origin_shift))
    raw.recompute()
    _recompute_machined(raw)


def restore(memento: DragMemento) -> None:
    """Échap : ramène la brute à son état du début (placement, cotes, liaisons mises de côté).
    Le document n'est pas recalculé ; la pièce usinée reprend le placement."""
    raw = memento.part
    _write_placement(memento, memento.placement)
    with writing(raw):
        sizes = (memento.length, memento.width, memento.thickness)
        for prop, value in zip(SIZE_PROPS, sizes, strict=True):
            if getattr(raw, prop).Value != value and prop not in expressions_of(raw):
                setattr(raw, prop, value)
        for prop, text in memento.aside.items():
            raw.setExpression(prop, text)
        if "FurnitureBindings" in raw.PropertiesList:
            raw.FurnitureBindings = memento.recorded
    for name, value in memento.distances.items():
        distance = raw.Document.getObject(name)
        if distance is not None and distance.Value.Value != value:
            distance.Value = value
    raw.recompute()
    _recompute_machined(raw)


def _relink_thickness(memento: DragMemento, furniture: DocumentObject) -> list[str]:
    """Épaisseur tirée d'un membre d'ensemble : traitée comme une épaisseur saisie dans le panneau
    (ADR 0019, points 5 et 6). L'épaisseur est contrôlée (rangée bloquée : ``ValueError``
    traduite) sur la géométrie d'avant, cohérente ; puis tout l'ensemble est relié : l'épaisseur
    est gardée, la rangée des autres membres se recalcule."""
    raw = memento.part
    new = raw.Thickness.Value
    with translated_errors():
        notices = thickness_notices(furniture, raw, new, previous=memento.thickness)
    relinked = relink_thickness(furniture, raw, new, memento.thickness)
    return list(notice_messages([*relinked, *notices]))


def _relink(memento: DragMemento) -> list[str]:
    """Relie tout l'ensemble de la brute d'après sa position nouvelle ; en cas d'erreur, la brute
    revient (:func:`restore`) et l'erreur est relancée. Si l'épaisseur a été tirée, la brute
    reprend d'abord son placement du début : les liaisons sont calculées sur la géométrie
    d'avant (:func:`_relink_thickness`)."""
    furniture = furniture_of(memento.part)
    if furniture is None:
        return []
    thicker = memento.part.Thickness.Value != memento.thickness
    try:
        if thicker:
            _write_placement(memento, memento.placement)
        follow_distances(furniture, memento.distances.keys())
        if thicker:
            return _relink_thickness(memento, furniture)
        members = read_members(furniture)
        return list(notice_messages(bind_members(members, members.objects)))
    except ValueError:
        restore(memento)
        raise


def _joint_warnings(memento: DragMemento) -> list[str]:
    """Avertissement pour chaque assemblage de la brute devenu invalide (B7) : le glissement est
    gardé, on prévient seulement (règle Q4 de J4)."""
    raw = memento.part
    warnings = []
    for joint in raw.InList:
        if (
            is_joint(joint)
            and "Invalid" in joint.State
            and joint.Name not in memento.invalid_joints
        ):
            params = {"label": quoted_value(joint.Label), "detail": joint.getStatusString()}
            warnings.append(translated(_NO_LONGER_TOUCHING, params))
    return warnings


def end_drag(memento: DragMemento) -> list[str]:
    """Relâchement : relie tout l'ensemble de la brute (membre d'ensemble, B3), recalcule le
    document une fois et renvoie les avertissements à mettre dans la vue rapport (liaisons,
    assemblage qui ne touche plus : B7). Rangée bloquée : la brute revient à son état du début et
    :class:`~freecad.menuiserie.features.furniture_bindings.LockedPiecesError` (ou ``ValueError``)
    est levée, pour proposer « Déverrouiller et appliquer » (ADR 0019)."""
    messages = _relink(memento)
    memento.part.Document.recompute()
    return [*messages, *_joint_warnings(memento)]
