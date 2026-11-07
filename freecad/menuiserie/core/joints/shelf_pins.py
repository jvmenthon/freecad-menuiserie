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

from freecad.menuiserie.core.geometry import Axis, Cylinder, JointError, PlacedBlock, Vec3
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.joints._base import (
    JointKind,
    JointPlan,
    count_param,
    flag_param,
    length_param,
    mm_text,
    validate_params,
)

__all__ = ["ShelfPinsParams", "ShelfPinsStrategy", "ShelfPinsValues"]

MIN_BOTTOM_MM: Final = 3.0  # matière laissée au fond d'un trou
AUTO_EDGE_MM: Final = 37.0  # distance des colonnes aux bouts horizontaux, par défaut
AUTO_MARGIN_MM: Final = 64.0  # distance du premier et du dernier trou aux bouts verticaux
_DOWN: Final = Vec3(0.0, 0.0, -1.0)
_TILT_TOLERANCE: Final = 1e-3

NOT_UPRIGHT: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Le perçage se pose sur un côté debout : son épaisseur doit être horizontale et sa longueur "
    "ou sa largeur verticale.",
)
BAD_VALUE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Les dimensions du perçage doivent être strictement positives."
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
    """Paramètres du perçage et des taquets (mm) ; 0 = automatique."""

    hole_diameter: float = length_param(5.0)
    hole_depth: float = length_param(12.0)
    pitch: float = length_param(32.0)
    edge_distance: float = length_param(0.0)  # colonnes aux bouts horizontaux : 37 mm
    end_margin: float = length_param(0.0)  # premier et dernier trou aux bouts verticaux : 64 mm
    rows: int = count_param(0)  # 0 = autant de rangs que le côté en reçoit
    with_pins: bool = flag_param(True)
    pin_row: int = count_param(0)  # rang des taquets, depuis le bas ; 0 = rang du milieu
    pin_projection: float = length_param(7.0)  # saillie du taquet hors de la face
    reversed: bool = flag_param(False)  # face opposée (par défaut la face +Z du côté)

    def __post_init__(self) -> None:
        validate_params(self)
        if min(self.hole_diameter, self.hole_depth, self.pitch, self.pin_projection) <= 0:
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
    pin_row: int  # 0 : pas de taquet
    pin_projection: float
    with_pins: bool

    @property
    def count(self) -> int:
        """Nombre de taquets (un par colonne dans le rang choisi)."""
        return 2 if self.with_pins else 0

    @property
    def hole_count(self) -> int:
        """Nombre de trous percés."""
        return 2 * self.rows


class ShelfPinsStrategy:
    """Perçage LR32 : deux colonnes de trous dans un côté, taquets rapportés."""

    kind: ClassVar[JointKind] = JointKind.SHELF_PINS

    def resolve(
        self, host: PlacedBlock, guest: PlacedBlock, params: ShelfPinsParams
    ) -> ShelfPinsValues:
        """Valeurs effectives : distances, nombre de rangs et rang des taquets."""
        _upright(host)
        return _checked(host, params)

    def plan(self, host: PlacedBlock, guest: PlacedBlock, params: ShelfPinsParams) -> JointPlan:
        """Trous percés dans la face choisie ; taquets plantés dans le rang choisi."""
        vertical, down = _upright(host)
        values = _checked(host, params)
        box = host.local_box()
        face = Axis.of(2, -1.0 if params.reversed else 1.0)
        plane = box.lo(2) if face.sign < 0 else box.hi(2)
        horizontal = 1 - vertical
        bottom = box.hi(vertical) if down > 0 else box.lo(vertical)
        columns = (
            box.lo(horizontal) + values.edge_distance,
            box.hi(horizontal) - values.edge_distance,
        )
        holes, pins = [], []
        radius = values.hole_diameter / 2
        for row in range(values.rows):
            level = bottom - down * (values.end_margin + row * values.pitch)
            for column in columns:
                base = _point(vertical, level, horizontal, column, plane)
                holes.append(Cylinder(base, face.opposite(), radius, values.hole_depth))
                if values.with_pins and row + 1 == values.pin_row:
                    deep = _point(
                        vertical, level, horizontal, column, plane - face.sign * values.hole_depth
                    )
                    height = values.hole_depth + values.pin_projection
                    pins.append(Cylinder(deep, face, radius, height))
        return JointPlan(host_cuts=tuple(holes), inserts=tuple(pins))


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


def _checked(host: PlacedBlock, params: ShelfPinsParams) -> ShelfPinsValues:
    box = host.local_box()
    vertical, _down = _upright(host)
    thickness, height = box.size(2), box.size(vertical)
    if params.hole_depth > thickness - MIN_BOTTOM_MM:
        text = {
            "depth": mm_text(params.hole_depth),
            "thickness": mm_text(thickness),
            "bottom": mm_text(MIN_BOTTOM_MM),
        }
        raise JointError(HOLE_TOO_DEEP, text)
    edge = params.edge_distance or AUTO_EDGE_MM
    margin = params.end_margin or AUTO_MARGIN_MM
    span = height - 2 * margin
    rows = params.rows or (int(span // params.pitch) + 1 if span >= 0 else 0)
    wide = box.size(1 - vertical) - 2 * edge - params.hole_diameter
    if rows < 1 or span < (rows - 1) * params.pitch - 1e-6 or wide < 0:
        text = {
            "rows": str(max(rows, 1)),
            "pitch": mm_text(params.pitch),
            "margin": mm_text(margin),
            "edge": mm_text(edge),
        }
        raise JointError(TOO_SHORT, text)
    pin_row = params.pin_row or (rows + 1) // 2
    if params.with_pins and pin_row > rows:
        raise JointError(NO_SUCH_ROW, {"row": str(pin_row), "rows": str(rows)})
    return ShelfPinsValues(
        params.hole_diameter,
        params.hole_depth,
        params.pitch,
        edge,
        margin,
        rows,
        pin_row if params.with_pins else 0,
        params.pin_projection,
        params.with_pins,
    )
