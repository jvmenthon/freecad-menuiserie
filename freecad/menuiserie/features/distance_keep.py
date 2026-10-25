# SPDX-License-Identifier: LGPL-2.1-or-later
"""« Garder cette distance » : de deux éléments choisis à l'objet Distance (DI-c, § 4.7).

La distance définie entre deux éléments (face, arête, sommet) de deux pièces peut être gardée si
les deux pièces sont membres du **même ensemble**, d'équerre avec lui, si la direction de la
mesure est parallèle à un axe de l'ensemble (``core.distance.ensemble_axis``, D5) et si chaque
élément est sur une face de sa pièce (début ou fin de son étendue sur l'axe). La géométrie est
lue **avant** tout déplacement (:func:`read_geometry`) : les côtés des pièces sont ceux du
début. :func:`plan_keep` contrôle ensuite la distance mesurée et la rangée (une Distance compte
comme une pièce verrouillée : rangée bloquée refusée avant toute écriture, F4).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

import FreeCAD as App

from freecad.menuiserie.core.distance import FrameAxis, Gap, ensemble_axis
from freecad.menuiserie.core.furniture import (
    FurnitureAxis,
    KeptGap,
    Span,
    check_kept,
    follow_rules,
    member_spans,
)
from freecad.menuiserie.core.geometry import ANGLE_TOLERANCE, CONTACT_TOLERANCE_MM, Vec3
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.snap import EdgeTarget, FaceTarget, Frame, Target, VertexTarget
from freecad.menuiserie.features.distance import LABEL
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.furniture import furniture_of, origin_of
from freecad.menuiserie.features.furniture_bindings import read_members
from freecad.menuiserie.features.i18n import translated, translated_errors
from freecad.menuiserie.features.picked import PickedElement
from freecad.menuiserie.features.snap_geometry import to_vec3

__all__ = ["KeepError", "KeepGeometry", "KeepPlan", "plan_keep", "read_geometry"]

PLANNED_KEY: Final = "Distance(nouvelle)"  # clé de la Distance avant sa création (pas un Name)
_TWO_PIECES: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Une distance ne se garde qu'entre deux pièces de l'atelier."
)
_NOT_MEMBERS: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Les deux pièces doivent être membres du même ensemble pour garder la distance.",
)
_NOT_PARALLEL: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "La direction de la distance n'est parallèle à aucun axe de l'ensemble : elle ne peut pas "
    "être gardée.",
)
_NOT_ON_FACE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "« {label} » n'est pas sur une face de sa pièce perpendiculaire à l'axe : la distance ne "
    "peut pas être gardée.",
)
_ZERO: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Une distance nulle ne peut pas être gardée : les deux faces se touchent."
)
_NOT_SQUARE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "« {label} » n'est pas d'équerre avec l'ensemble : la distance ne peut pas être gardée.",
)


class KeepError(ValueError):
    """La distance ne peut pas être gardée ; message traduit. ``blocked`` : vrai si c'est une
    rangée bloquée (la pièce verrouillée est la cause), pour proposer « Ne plus garder et
    appliquer »."""

    def __init__(self, message: str, *, blocked: bool = False) -> None:
        super().__init__(message)
        self.blocked = blocked


@dataclass(frozen=True)
class _Located:
    """Élément choisi dans le repère de l'ensemble (relatif à son ``Origin``) : un point et, pour
    une arête, sa direction."""

    point: Vec3
    direction: Vec3 | None
    label: str


@dataclass(frozen=True)
class KeepGeometry:
    """Ce que la lecture d'avant déplacement garde : ensemble, pièces (premier et second
    élément), clés, étendues relatives, éléments situés et axes de l'ensemble dans le repère
    global."""

    furniture: DocumentObject
    pieces: tuple[DocumentObject, DocumentObject]
    spans: tuple[dict[FurnitureAxis, Span], dict[FurnitureAxis, Span]]
    located: tuple[_Located, _Located]
    frame: Frame


@dataclass(frozen=True)
class KeepPlan:
    """Distance à créer : ensemble, pièces et :class:`KeptGap` (clé provisoire)."""

    furniture: DocumentObject
    first: DocumentObject
    second: DocumentObject
    gap: KeptGap


def _frame(container: DocumentObject | None) -> tuple[Frame, App.Placement]:
    """Axes de l'ensemble dans le repère global (ceux de son conteneur) et placement global du
    conteneur."""
    placement = container.getGlobalPlacement() if container is not None else App.Placement()
    axes = [to_vec3(placement.Rotation.multVec(App.Vector(*unit))) for unit in _UNITS]
    return Frame(Vec3(0.0, 0.0, 0.0), *axes), placement


_UNITS: Final = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))


def _reference(target: Target) -> tuple[Vec3, Vec3 | None]:
    """Point de l'élément (n'importe lequel pour un plan) et direction d'une arête."""
    if isinstance(target, FaceTarget):
        return target.frame.origin, None
    if isinstance(target, EdgeTarget):
        direction = Vec3(
            target.end.x - target.start.x,
            target.end.y - target.start.y,
            target.end.z - target.start.z,
        )
        return target.start, direction
    if isinstance(target, VertexTarget):
        return target.point, None
    raise TypeError(type(target).__name__)


def _located(
    element: PickedElement, target: Target, placement: App.Placement, origin: Vec3
) -> _Located:
    point, direction = _reference(target)
    inverse = placement.inverse()
    local = inverse.multVec(App.Vector(point.x, point.y, point.z))
    relative = Vec3(local.x - origin.x, local.y - origin.y, local.z - origin.z)
    turned = None
    if direction is not None:
        vector = inverse.Rotation.multVec(App.Vector(direction.x, direction.y, direction.z))
        turned = to_vec3(vector)
    return _Located(relative, turned, element.label())


def read_geometry(
    elements: tuple[PickedElement, PickedElement],
    targets: tuple[Target, Target],
    pieces: tuple[DocumentObject | None, DocumentObject | None],
) -> KeepGeometry:
    """Géométrie des deux éléments et des deux pièces **avant** leur déplacement.
    :class:`KeepError` si la distance ne peut pas être gardée (une pièce n'est pas à l'atelier,
    pièces hors d'un même ensemble, pièce pas d'équerre)."""
    first, second = pieces
    if first is None or second is None:
        raise KeepError(translated(_TWO_PIECES))
    furniture = furniture_of(first)
    if furniture is None or furniture_of(second) != furniture:
        raise KeepError(translated(_NOT_MEMBERS))
    with translated_errors():
        members = {m.key: m for m in read_members(furniture).members}
    try:
        spans = (dict(member_spans(members[first.Name])), dict(member_spans(members[second.Name])))
    except Exception as error:  # FurnitureError : pas d'équerre
        raise KeepError(translated(_NOT_SQUARE, {"label": str(first.Label)})) from error
    frame, placement = _frame(furniture.getParentGeoFeatureGroup())
    origin = origin_of(furniture)
    located = (
        _located(elements[0], targets[0], placement, origin),
        _located(elements[1], targets[1], placement, origin),
    )
    return KeepGeometry(furniture, (first, second), spans, located, frame)


def _side(item: _Located, span: Span, axis: FurnitureAxis) -> bool:
    """Vrai si l'élément est sur la face de fin de la pièce, faux sur celle de début ;
    :class:`KeepError` s'il n'est sur aucune (ou si une arête est parallèle à l'axe)."""
    coordinate = item.point.component(axis.index)
    parallel = item.direction is not None and _along(item.direction, axis)
    if not parallel and abs(coordinate - span.lo) <= CONTACT_TOLERANCE_MM:
        return False
    if not parallel and abs(coordinate - span.hi) <= CONTACT_TOLERANCE_MM:
        return True
    raise KeepError(translated(_NOT_ON_FACE, {"label": item.label}))


def _along(direction: Vec3, axis: FurnitureAxis) -> bool:
    length = (direction.x**2 + direction.y**2 + direction.z**2) ** 0.5
    return abs(direction.component(axis.index)) >= (1.0 - ANGLE_TOLERANCE) * length


def _blocked(plan: KeepPlan) -> None:
    """Refus avant écriture si la Distance rend une rangée sans cellule libre (F4)."""
    members = read_members(plan.furniture, planned=[plan.gap])
    rules, _ = follow_rules(members.box, members.members)
    try:
        with translated_errors():
            check_kept(members.members, rules, plan.gap.key)
    except ValueError as error:
        raise KeepError(str(error), blocked=True) from error


def plan_keep(geometry: KeepGeometry, gap: Gap, value: float) -> KeepPlan:
    """Distance à créer pour la mesure ``gap`` et la valeur ``value`` (mm). :class:`KeepError`
    si la direction n'est pas celle d'un axe de l'ensemble, si un élément n'est pas sur une face
    de sa pièce, si ``value`` est nulle ou si une rangée serait bloquée."""
    axis_name = ensemble_axis(gap, geometry.frame)
    if axis_name is None:
        raise KeepError(translated(_NOT_PARALLEL))
    axis = FurnitureAxis.of(tuple(FrameAxis).index(axis_name))
    first, second = geometry.pieces
    ends = [
        _side(item, spans[axis], axis)
        for item, spans in zip(geometry.located, geometry.spans, strict=True)
    ]
    if value <= CONTACT_TOLERANCE_MM:
        raise KeepError(translated(_ZERO))
    label = translated(LABEL, {"a": str(first.Label), "b": str(second.Label)})
    kept = KeptGap(PLANNED_KEY, first.Name, ends[0], second.Name, ends[1], axis, label)
    plan = KeepPlan(geometry.furniture, first, second, kept)
    _blocked(plan)
    return plan


def reason(geometry: KeepGeometry | KeepError, gap: Gap | None) -> str | None:
    """Raison pour laquelle la distance ne peut pas être gardée, ``None`` si elle peut l'être
    (hors valeur et rangée : voir :func:`plan_keep`) ; pour griser la case du panneau."""
    if isinstance(geometry, KeepError):
        return str(geometry)
    if gap is None:
        return None
    try:
        plan_keep(geometry, gap, 1.0)
    except KeepError as refusal:
        return None if refusal.blocked else str(refusal)
    return None
