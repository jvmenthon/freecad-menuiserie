# SPDX-License-Identifier: LGPL-2.1-or-later
"""Coulisses de tiroir à billes : pose face à face entre un côté de caisson et un côté de tiroir.

Contrairement aux assemblages de chant ou de bout, les deux pièces sont séparées par un jeu (la
coulisse l'occupe) : le côté du caisson (``host``) et celui du tiroir (``guest``) se font face. La
coulisse, pièce rapportée, est posée à hauteur réglée sur le côté du caisson ; chaque côté reçoit
des avant-trous au pas du système 32 (ADR 0033). Calculs dans le repère de l'hôte.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import ClassVar, Final

from freecad.menuiserie.core.geometry import (
    CONTACT_TOLERANCE_MM,
    Axis,
    Box,
    Cylinder,
    JointError,
    PlacedBlock,
    RigidTransform,
    Vec3,
    moved,
    moved_box,
    relative_axes,
    relative_transform,
)
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.joints._base import (
    JointKind,
    JointPlan,
    count_param,
    flag_param,
    length_param,
    mm_text,
    offset_param,
    validate_params,
)

__all__ = ["SLIDE_LENGTHS", "SlideParams", "SlideStrategy", "SlideValues"]

SLIDE_LENGTHS: Final = (250.0, 300.0, 350.0, 400.0, 450.0, 500.0, 550.0, 600.0)
FIRST_HOLE_MM: Final = 37.0  # premier trou, depuis l'avant de la coulisse (système 32)
HOLE_STEP_MM: Final = 32.0
MIN_BOTTOM_MM: Final = 3.0
AUTO_HOLE_COUNT: Final = 3
GUEST_PILOT_MM: Final = 3.0  # avant-trou de vis dans le côté du tiroir
GUEST_PILOT_DEPTH_MM: Final = 8.0

NO_GAP: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Les côtés doivent se faire face avec un jeu pour la coulisse (12,7 mm d'ordinaire) : sur "
    "l'axe où ils sont les plus proches, l'écart est de {gap} mm (négatif : ils se chevauchent). "
    "Écartez le côté du tiroir de celui du caisson.",
)
NO_OVERLAP: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Les deux côtés ne se font pas face : leurs surfaces ne se recouvrent pas."
)
TOO_SHORT: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Les côtés se recouvrent sur {overlap} mm : aucune coulisse du commerce ne tient "
    "(250 mm au moins).",
)
TOO_LONG: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Coulisse de {length} mm trop longue pour {overlap} mm de recouvrement (retrait de "
    "{setback} mm compris).",
)
TOO_LOW: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Coulisse de {height} mm de haut : elle sort des côtés, qui se recouvrent sur {overlap} mm "
    "de hauteur.",
)
HOLE_TOO_DEEP: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Avant-trou de {depth} mm trop profond pour un côté de {thickness} mm : il faut "
    "{bottom} mm de matière.",
)
BAD_VALUE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Une dimension de la coulisse doit être strictement positive."
)


@dataclass(frozen=True)
class SlideParams:
    """Paramètres d'une coulisse (mm) ; 0 = automatique pour la longueur et le nombre."""

    length: float = length_param(0.0)
    height_offset: float = offset_param(0.0)  # décalage de la coulisse depuis le milieu
    front_setback: float = length_param(0.0)  # retrait depuis l'avant des côtés
    reversed: bool = flag_param(False)  # avant = bout opposé
    thickness: float = length_param(12.7)
    slide_height: float = length_param(45.0)
    hole_count: int = count_param(0)
    hole_diameter: float = length_param(5.0)
    hole_depth: float = length_param(12.0)

    def __post_init__(self) -> None:
        validate_params(self)
        positive = (self.thickness, self.slide_height, self.hole_diameter, self.hole_depth)
        if min(positive) <= 0 or self.hole_count == 1:
            raise JointError(BAD_VALUE, {})


@dataclass(frozen=True)
class SlideValues:
    """Valeurs effectives de la coulisse (mm), affichées par le panneau."""

    length: float
    gap: float
    thickness: float
    hole_count: int
    hole_positions: tuple[float, ...]  # depuis l'avant de la coulisse

    @property
    def count(self) -> int:
        """Une coulisse par assemblage (liste de débit)."""
        return 1


@dataclass(frozen=True)
class _Frame:
    """Disposition des côtés dans le repère de l'hôte."""

    normal: int  # axe qui traverse le jeu
    sign: int  # +1 : l'invité est du côté +
    host_plane: float
    guest_plane: float
    length_axis: int
    height_axis: int
    overlap: Box  # recouvrement dans les deux autres axes
    to_guest: RigidTransform  # hôte → invité
    guest_extent: float  # épaisseur de l'invité à travers le jeu


class SlideStrategy:
    """Coulisse à billes posée face à face avec un jeu."""

    kind: ClassVar[JointKind] = JointKind.DRAWER_SLIDE

    def resolve(self, host: PlacedBlock, guest: PlacedBlock, params: SlideParams) -> SlideValues:
        """Valeurs effectives : longueur, jeu et position des trous."""
        return _values(_frame(host, guest), params)

    def plan(self, host: PlacedBlock, guest: PlacedBlock, params: SlideParams) -> JointPlan:
        """Avant-trous des deux côtés et coulisse rapportée dans le jeu."""
        frame = _frame(host, guest)
        values = _values(frame, params)
        host_cuts, guest_cuts = [], []
        host_depth = _depth(host.local_box().size(frame.normal), params.hole_depth)
        for hole in values.hole_positions:
            center = _along(frame, params, hole)
            host_cuts.append(
                Cylinder(
                    center.with_component(frame.normal, frame.host_plane),
                    Axis.of(frame.normal, -frame.sign),
                    params.hole_diameter / 2,
                    host_depth,
                )
            )
            pilot = Cylinder(
                center.with_component(frame.normal, frame.guest_plane),
                Axis.of(frame.normal, frame.sign),
                GUEST_PILOT_MM / 2,
                _depth(frame.guest_extent, GUEST_PILOT_DEPTH_MM),
            )
            guest_cuts.append(moved(pilot, frame.to_guest))
        return JointPlan(
            host_cuts=tuple(host_cuts),
            guest_cuts=tuple(guest_cuts),
            inserts=(_body(frame, params, values),),
        )


def _frame(host: PlacedBlock, guest: PlacedBlock) -> _Frame:
    relative_axes(host, guest)  # JointError si les pièces ne sont pas d'équerre
    to_host = relative_transform(host, guest)
    host_box = host.local_box()
    guest_box = moved_box(guest.local_box(), to_host)
    gaps = [
        (max(guest_box.lo(i) - host_box.hi(i), host_box.lo(i) - guest_box.hi(i)), i)
        for i in range(3)
    ]
    separated = [item for item in gaps if item[0] > CONTACT_TOLERANCE_MM]
    if not separated:
        raise JointError(NO_GAP, {"gap": mm_text(max(gaps)[0])})  # axe le plus proche du jeu
    _gap, index = min(separated)  # côtés face à face : l'axe de plus petit écart
    above = guest_box.lo(index) - host_box.hi(index) > host_box.lo(index) - guest_box.hi(index)
    return _facing(index, above, host_box, guest_box, to_host)


def _facing(
    index: int, above: bool, host_box: Box, guest_box: Box, to_host: RigidTransform
) -> _Frame:
    others = [i for i in range(3) if i != index]
    ranges = {}
    for other in others:
        low = max(host_box.lo(other), guest_box.lo(other))
        high = min(host_box.hi(other), guest_box.hi(other))
        if high - low <= CONTACT_TOLERANCE_MM:
            raise JointError(NO_OVERLAP, {})
        ranges[other] = (low, high)
    length_axis = max(others, key=lambda i: ranges[i][1] - ranges[i][0])
    height_axis = next(i for i in others if i != length_axis)
    overlap = Box.from_ranges([ranges.get(i, (host_box.lo(i), host_box.hi(i))) for i in range(3)])
    if above:
        host_plane, guest_plane, sign = host_box.hi(index), guest_box.lo(index), 1
    else:
        host_plane, guest_plane, sign = host_box.lo(index), guest_box.hi(index), -1
    return _Frame(
        index,
        sign,
        host_plane,
        guest_plane,
        length_axis,
        height_axis,
        overlap,
        to_host.inverse(),
        guest_box.size(index),
    )


def _values(frame: _Frame, params: SlideParams) -> SlideValues:
    gap = abs(frame.guest_plane - frame.host_plane)
    span = frame.overlap.size(frame.length_axis)
    room = span - params.front_setback
    if params.length:
        length = params.length
    else:
        fitting = [size for size in SLIDE_LENGTHS if size <= room + CONTACT_TOLERANCE_MM]
        if not fitting:
            raise JointError(TOO_SHORT, {"overlap": mm_text(span)})
        length = fitting[-1]
    if length > room + CONTACT_TOLERANCE_MM:
        text = {
            "length": mm_text(length),
            "overlap": mm_text(span),
            "setback": mm_text(params.front_setback),
        }
        raise JointError(TOO_LONG, text)
    height = frame.overlap.size(frame.height_axis)
    low = height / 2 + params.height_offset - params.slide_height / 2
    if low < -CONTACT_TOLERANCE_MM or low + params.slide_height > height + CONTACT_TOLERANCE_MM:
        text = {"height": mm_text(params.slide_height), "overlap": mm_text(height)}
        raise JointError(TOO_LOW, text)
    count = params.hole_count or AUTO_HOLE_COUNT
    return SlideValues(length, gap, params.thickness, count, _holes(length, count))


def _holes(length: float, count: int) -> tuple[float, ...]:
    """Trous au pas du système 32 : le premier à 37 mm de l'avant, les suivants répartis par
    multiples de 32 mm jusqu'à 37 mm du bout."""
    step = HOLE_STEP_MM * max(
        1, math.floor((length - 2 * FIRST_HOLE_MM) / (HOLE_STEP_MM * (count - 1)))
    )
    return tuple(FIRST_HOLE_MM + index * step for index in range(count))


def _front(frame: _Frame, params: SlideParams) -> tuple[float, int]:
    """Coordonnée de l'avant de la coulisse sur l'axe de longueur, et sens vers l'arrière."""
    box = frame.overlap
    if params.reversed:
        return box.hi(frame.length_axis) - params.front_setback, -1
    return box.lo(frame.length_axis) + params.front_setback, 1


def _along(frame: _Frame, params: SlideParams, distance: float) -> Vec3:
    """Point de l'axe de la coulisse à ``distance`` de son avant (à mi-hauteur de la coulisse)."""
    start, direction = _front(frame, params)
    point = Vec3(0.0, 0.0, 0.0).with_component(frame.length_axis, start + direction * distance)
    middle = frame.overlap.center(frame.height_axis) + params.height_offset
    return point.with_component(frame.height_axis, middle)


def _depth(thickness: float, wanted: float) -> float:
    """Profondeur d'un trou dans une pièce de ``thickness`` mm : ``wanted``, sans percer jusqu'au
    parement ; :class:`JointError` s'il ne reste pas ``MIN_BOTTOM_MM`` de matière."""
    if wanted > thickness - MIN_BOTTOM_MM + CONTACT_TOLERANCE_MM:
        text = {
            "depth": mm_text(wanted),
            "thickness": mm_text(thickness),
            "bottom": mm_text(MIN_BOTTOM_MM),
        }
        raise JointError(HOLE_TOO_DEEP, text)
    return wanted


def _body(frame: _Frame, params: SlideParams, values: SlideValues) -> Box:
    """Coulisse : boîte dans le jeu, collée au côté du caisson."""
    start, direction = _front(frame, params)
    end = start + direction * values.length
    middle = frame.overlap.center(frame.height_axis) + params.height_offset
    reach = min(params.thickness, values.gap)
    far = frame.host_plane + frame.sign * reach
    box = frame.overlap.with_range(frame.length_axis, min(start, end), max(start, end))
    box = box.with_range(
        frame.height_axis, middle - params.slide_height / 2, middle + params.slide_height / 2
    )
    return box.with_range(frame.normal, min(frame.host_plane, far), max(frame.host_plane, far))
