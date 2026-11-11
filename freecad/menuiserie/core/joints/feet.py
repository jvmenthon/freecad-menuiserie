# SPDX-License-Identifier: LGPL-2.1-or-later
"""Pieds de caisson réglables : une grille de perçages sous un panneau horizontal.

Un pied ne relie pas deux pièces : ``guest`` est la même pièce que ``host`` (le panneau du dessous).
Chaque pied perce la face du dessous d'un logement de tige ; l'embase et la tige sont des pièces
rapportées (ADR 0033). Calculs dans le repère de l'hôte, la face du dessous étant celle qui regarde
vers le bas du document.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from itertools import pairwise
from typing import ClassVar, Final

from freecad.menuiserie.core.geometry import (
    Axis,
    Cylinder,
    JointError,
    PlacedBlock,
    Vec3,
)
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.joints._base import (
    JointKind,
    JointPlan,
    choice_param,
    count_param,
    length_param,
    mm_text,
    validate_params,
)
from freecad.menuiserie.core.joints.dowels import positions

__all__ = ["FOOT_MATERIALS", "FootParams", "FootStrategy", "FootValues"]

MIN_BOTTOM_MM: Final = 3.0  # matière laissée au-dessus du logement de la tige
FOOT_MATERIALS: Final = ("plastic", "wood")  # matière du pied : plastique (défaut) ou bois
AUTO_SPAN_MM: Final = 800.0  # écart maximal entre deux pieds, en nombre automatique
AUTO_EDGE_MM: Final = 50.0  # distance des pieds au bord du panneau, par défaut
_DOWN: Final = Vec3(0.0, 0.0, -1.0)
_TILT_TOLERANCE: Final = 1e-3

NOT_HORIZONTAL: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Les pieds se posent sous un panneau couché : sa face du dessous doit être celle de son "
    "épaisseur.",
)
TOO_SMALL: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Le panneau est trop petit pour {columns} x {rows} pieds d'embase {base} mm à {edge} mm des "
    "bords.",
)
HOLE_TOO_DEEP: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Logement de tige de {depth} mm trop profond pour un panneau de {thickness} mm : il faut "
    "laisser {bottom} mm de matière.",
)
STEM_TOO_WIDE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "La tige ({diameter} mm) doit être plus fine que l'embase ({base} mm)."
)


@dataclass(frozen=True)
class FootParams:
    """Paramètres des pieds (mm) ; 0 = automatique (M10, embase Ø50, 15 mm de haut, trou de
    12 mm, distance au bord de 50 mm)."""

    stem_diameter: float = length_param(10.0)  # tige filetée
    base_diameter: float = length_param(50.0)
    height: float = length_param(15.0)  # hauteur visible sous le panneau
    hole_depth: float = length_param(12.0)
    columns: int = count_param(0)  # 0 = automatique selon la longueur du panneau
    rows: int = count_param(0)
    edge_distance: float = length_param(0.0)
    foot_material: str = choice_param("plastic", FOOT_MATERIALS)

    def __post_init__(self) -> None:
        validate_params(self)


@dataclass(frozen=True)
class FootValues:
    """Valeurs effectives des pieds (mm), affichées par le panneau."""

    stem_diameter: float
    base_diameter: float
    height: float
    hole_depth: float
    columns: int
    rows: int
    edge_distance: float
    centers: tuple[tuple[float, float], ...]  # (x, y) de chaque pied dans l'hôte
    foot_material: str = "plastic"

    @property
    def count(self) -> int:
        """Nombre total de pieds."""
        return len(self.centers)


class FootStrategy:
    """Pieds de caisson : perçages sous le panneau, embases rapportées."""

    kind: ClassVar[JointKind] = JointKind.FOOT

    def resolve(self, host: PlacedBlock, guest: PlacedBlock, params: FootParams) -> FootValues:
        """Valeurs effectives : distance au bord et centres des pieds."""
        _underside(host)
        return _checked(host, params)

    def plan(self, host: PlacedBlock, guest: PlacedBlock, params: FootParams) -> JointPlan:
        """Pieds en bois : logement de tige percé et tige rapportée. Pieds en plastique (vissés,
        vis non modélisées) : embase seule sous le panneau, qui n'est pas percé."""
        face = _underside(host)
        values = _checked(host, params)
        box = host.local_box()
        plane = box.lo(2) if face.sign < 0 else box.hi(2)
        holes, inserts = [], []
        for x, y in values.centers:
            base = Vec3(x, y, plane)
            inserts.append(Cylinder(base, face, values.base_diameter / 2, values.height))
            if values.foot_material == "wood":
                stem = Cylinder(base, face.opposite(), values.stem_diameter / 2, values.hole_depth)
                holes.append(stem)
                inserts.append(stem)
        return JointPlan(host_cuts=tuple(holes), inserts=tuple(inserts))


def _underside(host: PlacedBlock) -> Axis:
    """Face du panneau qui regarde vers le bas du document (axe local Z, sinon refus)."""
    down = host.placement.inverse().rotate(_DOWN)
    major = max(range(3), key=lambda i: abs(down.component(i)))
    if major != 2 or abs(abs(down.component(2)) - 1.0) > _TILT_TOLERANCE:
        raise JointError(NOT_HORIZONTAL, {})
    return Axis.of(2, down.component(2))


def _effective(params: FootParams) -> FootParams:
    """Paramètres sans zéro : une cote à 0 (automatique) prend la valeur par défaut."""
    defaults = FootParams()
    return replace(
        params,
        stem_diameter=params.stem_diameter or defaults.stem_diameter,
        base_diameter=params.base_diameter or defaults.base_diameter,
        height=params.height or defaults.height,
        hole_depth=params.hole_depth or defaults.hole_depth,
    )


def _checked(host: PlacedBlock, given: FootParams) -> FootValues:
    params = _effective(given)
    box = host.local_box()
    thickness = box.size(2)
    wood = params.foot_material == "wood"  # seul un pied en bois a une tige et perce le panneau
    if wood and params.stem_diameter >= params.base_diameter:
        text = {"diameter": mm_text(params.stem_diameter), "base": mm_text(params.base_diameter)}
        raise JointError(STEM_TOO_WIDE, text)
    if wood and params.hole_depth > thickness - MIN_BOTTOM_MM:
        text = {
            "depth": mm_text(params.hole_depth),
            "thickness": mm_text(thickness),
            "bottom": mm_text(MIN_BOTTOM_MM),
        }
        raise JointError(HOLE_TOO_DEEP, text)
    edge = params.edge_distance or AUTO_EDGE_MM
    columns = params.columns or _auto_count(box.size(0), edge)
    rows = params.rows or _auto_count(box.size(1), edge)
    xs = _line(box.size(0), edge, columns, params.base_diameter)
    ys = _line(box.size(1), edge, rows, params.base_diameter)
    if xs is None or ys is None:
        text = {
            "columns": str(columns),
            "rows": str(rows),
            "base": mm_text(params.base_diameter),
            "edge": mm_text(edge),
        }
        raise JointError(TOO_SMALL, text)
    centers = tuple((box.lo(0) + x, box.lo(1) + y) for x in xs for y in ys)
    return FootValues(
        params.stem_diameter,
        params.base_diameter,
        params.height,
        params.hole_depth,
        columns,
        rows,
        edge,
        centers,
        params.foot_material,
    )


def _auto_count(size: float, edge: float) -> int:
    """Pieds le long d'un côté : 2, plus un par tranche entamée de 800 mm entre les pieds
    extrêmes."""
    return max(2, math.ceil((size - 2 * edge) / AUTO_SPAN_MM) + 1)


def _line(size: float, edge: float, count: int, base: float) -> tuple[float, ...] | None:
    """Positions des pieds le long d'un côté, ou ``None`` si l'embase déborde ou se chevauche."""
    if size - 2 * edge < 0 and count > 1:
        return None
    line = positions(size, edge, count)
    inside = line[0] - base / 2 >= -1e-6 and size - line[-1] - base / 2 >= -1e-6
    apart = all(b - a >= base for a, b in pairwise(line))
    return line if inside and apart else None
