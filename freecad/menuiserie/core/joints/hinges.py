# SPDX-License-Identifier: LGPL-2.1-or-later
"""Charnières à cuvette : une porte (``guest``) articulée sur un côté de caisson (``host``).

La porte est posée devant le chant avant du côté (recouvrement total ou mi-épaisseur) ou logée
contre sa face intérieure (porte insérée). Chaque charnière perce la porte d'une cuvette ronde
(Ø35, ADR 0033) à ``edge_distance`` du chant de la porte, et le côté de deux avant-trous de
platine au pas de 32 mm, à 37 mm du chant avant. Nombre automatique selon la hauteur, positions
à 100 mm des angles. Calculs dans le repère de l'hôte.
"""

from __future__ import annotations

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
    MIN_WALL_MM,
    JointKind,
    JointPlan,
    count_param,
    length_param,
    mm_text,
    validate_params,
)

__all__ = ["AUTO_COUNT_STEPS", "HingeParams", "HingeStrategy", "HingeValues", "auto_count"]

# Nombre automatique : (hauteur maximale en mm, nombre de charnières) ; 4 au-delà du dernier seuil.
AUTO_COUNT_STEPS: Final = ((900.0, 2), (1600.0, 3))
MORE_HINGES: Final = 4
MAX_GAP_MM: Final = 5.0  # jeu entre la porte et le côté, au plus, pour qu'elle y soit articulée
MIN_BOTTOM_MM: Final = 3.0  # matière laissée au fond d'un perçage
MIN_EDGE_MM: Final = MIN_WALL_MM

NO_CONTACT: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "La porte n'est pas articulée sur le côté : elle doit toucher son chant avant (recouvrement) "
    "ou sa face intérieure (porte insérée), à {gap} mm au plus, en chevauchant sa hauteur.",
)
NOT_A_DOOR: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "La porte doit être posée de chant devant le côté : son épaisseur ({thickness} mm) doit être "
    "sa plus petite dimension.",
)
BAD_VALUE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Une dimension de la charnière doit être strictement positive, et il en faut deux au moins.",
)
EDGE_TOO_SMALL: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Distance de la cuvette au chant de la porte trop petite ({edge} mm) : {min} mm au moins.",
)
PITCH_TOO_SMALL: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Entraxe des vis de platine trop petit ({pitch} mm) : {min} mm au moins pour des "
    "avant-trous de {diameter} mm.",
)
CUP_TOO_DEEP: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Cuvette de {depth} mm trop profonde pour une porte de {thickness} mm : il faut {bottom} mm "
    "de matière au fond.",
)
CUP_TOO_WIDE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "La cuvette de {diameter} mm à {edge} mm du chant ne tient pas dans une porte de "
    "{width} mm de large.",
)
PILOT_TOO_DEEP: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Avant-trou de platine de {depth} mm trop profond pour un côté de {thickness} mm : il faut "
    "{bottom} mm de matière.",
)
PLATE_OUT: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Les vis de platine à {distance} mm du chant avant sortent du côté, profond de {depth} mm.",
)
OUT_OF_DOOR: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Charnières à {distance} mm des angles : la cuvette et la platine demandent {reach} mm au "
    "moins, et la hauteur commune de {height} mm doit laisser la place.",
)
TOO_CLOSE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "{count} charnières sur {height} mm de hauteur commune : elles se toucheraient (pas de "
    "{step} mm, {min} mm au moins).",
)


def auto_count(height: float) -> int:
    """Nombre de charnières d'une porte de ``height`` mm : 2 jusqu'à 900 mm, 3 jusqu'à 1 600 mm,
    puis 4."""
    for limit, count in AUTO_COUNT_STEPS:
        if height <= limit:
            return count
    return MORE_HINGES


@dataclass(frozen=True)
class HingeParams:
    """Paramètres des charnières (mm) ; 0 = automatique pour le nombre."""

    count: int = count_param(0)
    cup_diameter: float = length_param(35.0)
    cup_depth: float = length_param(13.0)
    edge_distance: float = length_param(5.0)  # du bord de la cuvette au chant de la porte
    end_distance: float = length_param(100.0)  # du centre de la charnière à l'angle de la porte
    screw_pitch: float = length_param(32.0)  # entraxe des vis de platine
    plate_distance: float = length_param(37.0)  # des vis de platine au chant avant du côté
    pilot_diameter: float = length_param(3.0)
    pilot_depth: float = length_param(10.0)

    def __post_init__(self) -> None:
        validate_params(self)
        sizes = (
            self.cup_diameter,
            self.cup_depth,
            self.edge_distance,
            self.end_distance,
            self.screw_pitch,
            self.plate_distance,
            self.pilot_diameter,
            self.pilot_depth,
        )
        if min(sizes) <= 0 or self.count == 1:
            raise JointError(BAD_VALUE, {})
        if self.edge_distance < MIN_EDGE_MM:
            raise JointError(
                EDGE_TOO_SMALL, {"edge": mm_text(self.edge_distance), "min": mm_text(MIN_EDGE_MM)}
            )
        least_pitch = self.pilot_diameter + MIN_WALL_MM
        if self.screw_pitch < least_pitch:
            text = {
                "pitch": mm_text(self.screw_pitch),
                "min": mm_text(least_pitch),
                "diameter": mm_text(self.pilot_diameter),
            }
            raise JointError(PITCH_TOO_SMALL, text)


@dataclass(frozen=True)
class HingeValues:
    """Valeurs effectives des charnières (mm), affichées par le panneau et comptées dans la liste
    de débit : ``count`` charnières, centrées aux ``positions`` (depuis le bas de la hauteur
    commune de la porte et du côté)."""

    count: int
    positions: tuple[float, ...]
    height: float  # hauteur commune de la porte et du côté
    cup_diameter: float
    cup_depth: float


@dataclass(frozen=True)
class _Frame:
    """Disposition de la porte devant le côté, dans le repère de l'hôte."""

    depth: int  # axe de la profondeur du côté (la porte est à l'avant)
    front: int  # +1 : l'avant du côté est vers +depth
    front_plane: float  # coordonnée du chant avant du côté
    thin: int  # axe de l'épaisseur du côté
    inside: int  # +1 : l'intérieur du caisson est vers +thin
    height: int  # axe de la hauteur
    span: tuple[float, float]  # hauteur commune de la porte et du côté
    host_thickness: float
    host_depth: float
    door_back: float  # coordonnée de la face intérieure de la porte (sur l'axe depth)
    door_thickness: float
    door_edge: float  # coordonnée du chant articulé de la porte (sur l'axe thin)
    door_width: float
    door_height: float
    plate_plane: float  # coordonnée de la face du côté qui reçoit la platine (sur l'axe thin)
    to_guest: RigidTransform


class HingeStrategy:
    """Charnières à cuvette : cuvettes dans la porte, avant-trous de platine dans le côté."""

    kind: ClassVar[JointKind] = JointKind.HINGE

    def resolve(self, host: PlacedBlock, guest: PlacedBlock, params: HingeParams) -> HingeValues:
        """Nombre de charnières et positions, après contrôle des cotes."""
        return _values(_frame(host, guest), params)

    def plan(self, host: PlacedBlock, guest: PlacedBlock, params: HingeParams) -> JointPlan:
        """Avant-trous de platine dans le côté, cuvettes dans la porte (et dans les pièces
        rapportées)."""
        frame = _frame(host, guest)
        values = _values(frame, params)
        _check_depths(frame, params)
        pilots: list[Cylinder] = []
        cups: list[Cylinder] = []
        for position in values.positions:
            center = frame.span[0] + position
            cups.append(_cup(frame, params, center))
            pilots += _pilots(frame, params, center)
        return JointPlan(
            host_cuts=tuple(pilots),
            guest_cuts=tuple(moved(cup, frame.to_guest) for cup in cups),
            inserts=tuple(cups),
        )


def _gaps(host_box: Box, guest_box: Box) -> list[float]:
    """Écart signé entre les boîtes sur chaque axe (négatif : elles se chevauchent)."""
    return [
        max(guest_box.lo(i) - host_box.hi(i), host_box.lo(i) - guest_box.hi(i)) for i in range(3)
    ]


def _frame(host: PlacedBlock, guest: PlacedBlock) -> _Frame:
    relative_axes(host, guest)  # JointError si les pièces ne sont pas d'équerre
    to_host = relative_transform(host, guest)
    host_box = host.local_box()
    guest_box = moved_box(guest.local_box(), to_host)
    gaps = _gaps(host_box, guest_box)
    touching = [
        i
        for i in range(3)
        if -CONTACT_TOLERANCE_MM <= gaps[i] <= MAX_GAP_MM
        and all(gaps[j] < -CONTACT_TOLERANCE_MM for j in range(3) if j != i)
    ]
    if len(touching) != 1:
        raise JointError(NO_CONTACT, {"gap": mm_text(MAX_GAP_MM)})
    thin = min(range(3), key=host_box.size)
    others = [i for i in range(3) if i != thin]
    if touching[0] == thin:  # porte insérée, contre la face intérieure du côté
        height = max(others, key=guest_box.size)
        depth = next(i for i in others if i != height)
    else:  # porte devant le chant avant
        depth = touching[0]
        height = next(i for i in others if i != depth)
    if guest_box.size(depth) > min(guest_box.size(i) for i in range(3)) + CONTACT_TOLERANCE_MM:
        raise JointError(NOT_A_DOOR, {"thickness": mm_text(guest_box.size(depth))})
    front = 1 if guest_box.center(depth) > host_box.center(depth) else -1
    inside = 1 if guest_box.center(thin) >= host_box.center(thin) else -1
    low = max(host_box.lo(height), guest_box.lo(height))
    high = min(host_box.hi(height), guest_box.hi(height))
    return _Frame(
        depth=depth,
        front=front,
        front_plane=host_box.hi(depth) if front > 0 else host_box.lo(depth),
        thin=thin,
        inside=inside,
        height=height,
        span=(low, high),
        host_thickness=host_box.size(thin),
        host_depth=host_box.size(depth),
        door_back=guest_box.lo(depth) if front > 0 else guest_box.hi(depth),
        door_thickness=guest_box.size(depth),
        door_edge=guest_box.lo(thin) if inside > 0 else guest_box.hi(thin),
        door_width=guest_box.size(thin),
        door_height=guest_box.size(height),
        plate_plane=host_box.hi(thin) if inside > 0 else host_box.lo(thin),
        to_guest=to_host.inverse(),
    )


def _values(frame: _Frame, params: HingeParams) -> HingeValues:
    height = frame.span[1] - frame.span[0]
    count = params.count or auto_count(frame.door_height)
    reach = max(params.cup_diameter, params.screw_pitch + params.pilot_diameter) / 2 + MIN_WALL_MM
    if params.end_distance < reach - CONTACT_TOLERANCE_MM or height < 2 * params.end_distance:
        text = {
            "distance": mm_text(params.end_distance),
            "reach": mm_text(reach),
            "height": mm_text(height),
        }
        raise JointError(OUT_OF_DOOR, text)
    if params.edge_distance + params.cup_diameter + MIN_WALL_MM > frame.door_width:
        text = {
            "diameter": mm_text(params.cup_diameter),
            "edge": mm_text(params.edge_distance),
            "width": mm_text(frame.door_width),
        }
        raise JointError(CUP_TOO_WIDE, text)
    step = (height - 2 * params.end_distance) / (count - 1)
    if step < params.cup_diameter + MIN_WALL_MM - CONTACT_TOLERANCE_MM:
        text = {
            "count": str(count),
            "height": mm_text(height),
            "step": mm_text(step),
            "min": mm_text(params.cup_diameter + MIN_WALL_MM),
        }
        raise JointError(TOO_CLOSE, text)
    positions = tuple(params.end_distance + index * step for index in range(count))
    return HingeValues(count, positions, height, params.cup_diameter, params.cup_depth)


def _check_depths(frame: _Frame, params: HingeParams) -> None:
    if params.cup_depth > frame.door_thickness - MIN_BOTTOM_MM + CONTACT_TOLERANCE_MM:
        text = {
            "depth": mm_text(params.cup_depth),
            "thickness": mm_text(frame.door_thickness),
            "bottom": mm_text(MIN_BOTTOM_MM),
        }
        raise JointError(CUP_TOO_DEEP, text)
    if params.pilot_depth > frame.host_thickness - MIN_BOTTOM_MM + CONTACT_TOLERANCE_MM:
        text = {
            "depth": mm_text(params.pilot_depth),
            "thickness": mm_text(frame.host_thickness),
            "bottom": mm_text(MIN_BOTTOM_MM),
        }
        raise JointError(PILOT_TOO_DEEP, text)
    margin = params.pilot_diameter / 2 + MIN_WALL_MM
    if not margin <= params.plate_distance <= frame.host_depth - margin:
        text = {"distance": mm_text(params.plate_distance), "depth": mm_text(frame.host_depth)}
        raise JointError(PLATE_OUT, text)


def _point(frame: _Frame, depth: float, thin: float, height: float) -> Vec3:
    origin = Vec3(0.0, 0.0, 0.0)
    return (
        origin.with_component(frame.depth, depth)
        .with_component(frame.thin, thin)
        .with_component(frame.height, height)
    )


def _cup(frame: _Frame, params: HingeParams, center: float) -> Cylinder:
    """Cuvette percée dans la face intérieure de la porte, à ``edge_distance`` de son chant."""
    radius = params.cup_diameter / 2
    thin = frame.door_edge + frame.inside * (params.edge_distance + radius)
    base = _point(frame, frame.door_back, thin, center)
    return Cylinder(base, Axis.of(frame.depth, frame.front), radius, params.cup_depth)


def _pilots(frame: _Frame, params: HingeParams, center: float) -> list[Cylinder]:
    """Deux avant-trous de platine, au pas ``screw_pitch``, dans la face intérieure du côté."""
    depth = frame.front_plane - frame.front * params.plate_distance
    axis = Axis.of(frame.thin, -frame.inside)
    return [
        Cylinder(
            _point(frame, depth, frame.plate_plane, center + shift * params.screw_pitch / 2),
            axis,
            params.pilot_diameter / 2,
            params.pilot_depth,
        )
        for shift in (-1, 1)
    ]
