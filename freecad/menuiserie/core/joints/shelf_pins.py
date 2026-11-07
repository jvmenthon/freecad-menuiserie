# SPDX-License-Identifier: LGPL-2.1-or-later
"""Perçage LR32 et taquets de tablette : deux colonnes de trous au pas de 32 mm dans un côté.

Un perçage ne relie pas deux pièces : ``guest`` est la même pièce que ``host`` (le côté de
caisson debout). Deux colonnes de trous de 5 mm au pas de 32 mm (système « ligne et rangée de
32 mm ») sont percées dans une face, à 37 mm des bouts horizontaux ; les taquets de la tablette
sont des pièces rapportées plantées dans un rang de trous (ADR 0033). Calculs dans le repère du
côté ; sa longueur ou sa largeur est la verticale du document, son épaisseur est horizontale.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, Final

from freecad.menuiserie.core.geometry import Axis, Box, Cylinder, JointError, PlacedBlock, Vec3
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.joints._base import (
    JointKind,
    JointPlan,
    choice_param,
    count_param,
    derived_param,
    flag_param,
    length_param,
    mm_text,
    validate_params,
)
from freecad.menuiserie.core.joints._shelf_layout import (
    Layout,
    Neighbor,
    choose_face,
    free_window,
    heights_of,
    pin_rows,
    side_boxes,
    touching_boxes,
)

__all__ = [
    "FACES",
    "Neighbor",
    "ShelfPinsParams",
    "ShelfPinsStrategy",
    "ShelfPinsValues",
    "picked_choice",
]

MIN_BOTTOM_MM: Final = 3.0  # matière laissée au fond d'un trou
AUTO_EDGE_MM: Final = 37.0  # distance des colonnes aux bouts horizontaux, par défaut
AUTO_MARGIN_MM: Final = 64.0  # distance du premier et du dernier trou aux bouts verticaux
AUTO_DIAMETER_MM: Final = 5.0
AUTO_DEPTH_MM: Final = 12.0
FACES: Final = ("auto", "plus", "minus")  # face percée : intérieure, +Z ou -Z du côté
_DOWN: Final = Vec3(0.0, 0.0, -1.0)
_TILT_TOLERANCE: Final = 1e-3
_EPSILON: Final = 1e-9

NOT_UPRIGHT: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Le perçage se pose sur un côté debout : son épaisseur doit être horizontale et sa longueur "
    "ou sa largeur verticale.",
)
BAD_VALUE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Le pas et la saillie des taquets doivent être strictement positifs."
)
HOLE_TOO_DEEP: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Trou de {depth} mm trop profond pour un côté de {thickness} mm : il faut laisser {bottom} mm "
    "de matière.",
)
TOO_SHORT: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Le côté est trop petit pour {rows} rangs de trous au pas de {pitch} mm, à {margin} mm des "
    "bouts et {edge} mm des bords.",
)
NO_SUCH_ROW: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Le taquet est prévu au rang {row} mais il n'y a que {rows} rangs de trous."
)


@dataclass(frozen=True)
class ShelfPinsParams:
    """Paramètres du perçage et des taquets (mm) ; 0 = automatique.

    ``neighbors`` n'est pas un réglage : les pièces du document autour du côté, qui bornent la
    zone percée et reçoivent des taquets."""

    hole_diameter: float = length_param(0.0)  # 5
    hole_depth: float = length_param(0.0)  # 12
    pitch: float = length_param(32.0)
    edge_distance: float = length_param(0.0)  # colonnes aux bouts horizontaux : 37 mm
    end_margin: float = length_param(0.0)  # trou le plus proche d'une pièce assemblée : 64 mm
    rows: int = count_param(0)  # 0 = autant de rangs que la zone libre en reçoit
    with_pins: bool = flag_param(True)
    pin_row: int = count_param(0)  # 0 = un rang sous chaque tablette ; sinon rang depuis le bas
    pin_projection: float = length_param(7.0)  # saillie du taquet hors de la face
    face: str = choice_param("auto", FACES)
    zone_height: float = length_param(0.0)  # hauteur (depuis le bas) dans la zone à percer
    neighbors: tuple[Neighbor, ...] = derived_param(())

    def __post_init__(self) -> None:
        validate_params(self)
        if min(self.pitch, self.pin_projection) <= 0:
            raise JointError(BAD_VALUE, {})


@dataclass(frozen=True)
class ShelfPinsValues:
    """Valeurs effectives du perçage (mm), affichées par le panneau."""

    hole_diameter: float
    hole_depth: float
    pitch: float
    edge_distance: float
    end_margin: float
    rows: int
    pin_row: int  # premier rang de taquets depuis le bas (1 : le plus bas), 0 : aucun
    pin_projection: float
    with_pins: bool
    pin_rows: tuple[int, ...] = ()  # rangs (depuis 0) qui portent des taquets
    heights: tuple[float, ...] = ()  # hauteur de chaque rang depuis le bas du côté
    face: str = "plus"  # face percée : « plus » (+Z du côté) ou « minus » (-Z)
    zone_height: float = 0.0  # milieu de la zone percée, depuis le bas du côté

    @property
    def count(self) -> int:
        """Nombre de taquets (un par colonne dans chaque rang choisi)."""
        return 2 * len(self.pin_rows)

    @property
    def hole_count(self) -> int:
        """Nombre de trous percés."""
        return 2 * self.rows

    def pin_top(self, row: int) -> float:
        """Hauteur du dessus du taquet du rang ``row`` (où repose le dessous de la tablette)."""
        return self.heights[row] + self.hole_diameter / 2


class ShelfPinsStrategy:
    """Perçage LR32 : deux colonnes de trous dans un côté, taquets rapportés."""

    kind: ClassVar[JointKind] = JointKind.SHELF_PINS

    def resolve(
        self, host: PlacedBlock, guest: PlacedBlock, params: ShelfPinsParams
    ) -> ShelfPinsValues:
        """Valeurs effectives : distances, nombre de rangs et rangs des taquets."""
        return _checked(host, params)[0]

    def plan(self, host: PlacedBlock, guest: PlacedBlock, params: ShelfPinsParams) -> JointPlan:
        """Trous percés dans la face intérieure ; taquets plantés dans les rangs choisis."""
        values, layout = _checked(host, params)
        vertical, down = _upright(host)
        box = host.local_box()
        face = Axis.of(2, layout.face_sign)
        plane = box.lo(2) if face.sign < 0 else box.hi(2)
        horizontal = 1 - vertical
        bottom = box.hi(vertical) if down > 0 else box.lo(vertical)
        columns = (
            box.lo(horizontal) + values.edge_distance,
            box.hi(horizontal) - values.edge_distance,
        )
        holes: list[Cylinder] = []
        pins: list[Cylinder | Box] = []
        radius = values.hole_diameter / 2
        for row, height in enumerate(layout.heights):
            level = bottom - down * height
            for column in columns:
                base = _point(vertical, level, horizontal, column, plane)
                holes.append(Cylinder(base, face.opposite(), radius, values.hole_depth))
                if row in layout.pin_rows:
                    stem_base = _point(vertical, level, horizontal, column, plane)
                    pins.append(Cylinder(stem_base, face.opposite(), radius, values.hole_depth))
                    pins.append(_ledge(vertical, level, horizontal, column, plane, face, values))
        return JointPlan(host_cuts=tuple(holes), inserts=tuple(pins))


def _ledge(  # noqa: PLR0913
    vertical: int,
    level: float,
    horizontal: int,
    column: float,
    plane: float,
    face: Axis,
    values: ShelfPinsValues,
) -> Box:
    """Partie du taquet hors du côté : section carrée de la largeur de la tige, à dessus plat
    (où repose la tablette), qui sort de ``pin_projection`` hors de la face."""
    radius = values.hole_diameter / 2
    out = plane + face.sign * values.pin_projection
    ranges = [(0.0, 0.0)] * 3
    ranges[vertical] = (level - radius, level + radius)
    ranges[horizontal] = (column - radius, column + radius)
    ranges[2] = (min(plane, out), max(plane, out))
    return Box.from_ranges(ranges)


def picked_choice(host: PlacedBlock, point: Vec3) -> tuple[str, float]:
    """Face (``plus`` ou ``minus``) et hauteur depuis le bas du côté d'un point cliqué sur le
    côté (repère du côté) : le perçage se fait sur cette face, dans la zone de ce point."""
    vertical, down = _upright(host)
    box = host.local_box()
    bottom = box.hi(vertical) if down > 0 else box.lo(vertical)
    near_plus = abs(point.z - box.hi(2)) <= abs(point.z - box.lo(2))
    height = (bottom - point.component(vertical)) * down
    return ("plus" if near_plus else "minus"), max(height, 0.0)


def _point(vertical: int, level: float, horizontal: int, column: float, z: float) -> Vec3:
    point = Vec3(0.0, 0.0, z).with_component(vertical, level)
    return point.with_component(horizontal, column)


def _upright(host: PlacedBlock) -> tuple[int, float]:
    """(axe local vertical, sens vers le bas sur cet axe) d'un côté debout, sinon refus."""
    down = host.placement.inverse().rotate(_DOWN)
    vertical = 0 if abs(down.component(0)) > abs(down.component(1)) else 1
    if abs(abs(down.component(vertical)) - 1.0) > _TILT_TOLERANCE:
        raise JointError(NOT_UPRIGHT, {})
    return vertical, 1.0 if down.component(vertical) > 0 else -1.0


def _checked(host: PlacedBlock, params: ShelfPinsParams) -> tuple[ShelfPinsValues, Layout]:
    box = host.local_box()
    vertical, down = _upright(host)
    bottom = box.hi(vertical) if down > 0 else box.lo(vertical)
    diameter = params.hole_diameter or AUTO_DIAMETER_MM
    depth = params.hole_depth or AUTO_DEPTH_MM
    thickness, total = box.size(2), box.size(vertical)
    if depth > thickness - MIN_BOTTOM_MM:
        text = {
            "depth": mm_text(depth),
            "thickness": mm_text(thickness),
            "bottom": mm_text(MIN_BOTTOM_MM),
        }
        raise JointError(HOLE_TOO_DEEP, text)
    edge = params.edge_distance or AUTO_EDGE_MM
    margin = params.end_margin or AUTO_MARGIN_MM
    boxes = side_boxes(host, params.neighbors, vertical)
    sign = choose_face(params.face, host, boxes)
    touching = touching_boxes(boxes, host, sign)
    fixed = [heights_of(other, bottom, down, vertical) for other, fixed in touching if fixed]
    shelves = [heights_of(other, bottom, down, vertical) for other, fixed in touching if not fixed]
    window = free_window(fixed, total, params.zone_height)
    first = window[0] + margin
    span = window[1] - margin - first
    rows = params.rows or (int(span // params.pitch + _EPSILON) + 1 if span >= 0 else 0)
    wide = box.size(1 - vertical) - 2 * edge - diameter
    if rows < 1 or span < (rows - 1) * params.pitch - 1e-6 or wide < 0:
        text = {
            "rows": str(max(rows, 1)),
            "pitch": mm_text(params.pitch),
            "margin": mm_text(margin),
            "edge": mm_text(edge),
        }
        raise JointError(TOO_SHORT, text)
    heights = tuple(first + index * params.pitch for index in range(rows))
    if not params.with_pins:
        chosen: tuple[int, ...] = ()
    elif params.pin_row:
        if params.pin_row > rows:
            raise JointError(NO_SUCH_ROW, {"row": str(params.pin_row), "rows": str(rows)})
        chosen = (params.pin_row - 1,)
    else:
        chosen = pin_rows(heights, shelves, diameter / 2)
    values = ShelfPinsValues(
        diameter,
        depth,
        params.pitch,
        edge,
        margin,
        rows,
        chosen[0] + 1 if chosen else 0,
        params.pin_projection,
        params.with_pins,
        chosen,
        heights,
        "plus" if sign > 0 else "minus",
        (window[0] + window[1]) / 2,
    )
    return values, Layout(sign, heights, chosen)
