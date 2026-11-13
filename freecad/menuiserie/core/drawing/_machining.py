# SPDX-License-Identifier: LGPL-2.1-or-later
"""Usinages d'une pièce pour son plan : formes des plans d'usinage → lignes du tableau.

Les formes d'usinage (``PlanSolid``) sont dans le repère local de la pièce : X sur la longueur,
Y sur la largeur, Z sur l'épaisseur, origine au coin. Sur le plan de pièce, la vue de face
montre X vers la droite et Y vers le haut : une position « x, y » se mesure donc depuis le coin
bas gauche de la vue de face. Chaque usinage est décrit par son encombrement, la face par où il
s'ouvre et sa profondeur ; un perçage par son diamètre et le centre de son entrée. Les usinages
identiques d'un même assemblage sont regroupés sur une ligne.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Final

from freecad.menuiserie.core._polyhedron import PlanSolid, Polyhedron, SlantedCylinder
from freecad.menuiserie.core.geometry import Box, Cylinder, Prism, Vec3
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP

__all__ = [
    "MAX_NOTE_LINES",
    "Machining",
    "MachiningKind",
    "capped",
    "machining_lines",
    "machinings",
]

_TOLERANCE_MM: Final = 0.01
MAX_POSITIONS: Final = 6  # positions écrites sur une ligne, au plus
MAX_NOTE_LINES: Final = 8  # lignes du tableau des usinages, titre compris (bande de 45 mm)
_FACES: Final = {
    (2, 1): QT_TRANSLATE_NOOP("Menuiserie", "face"),
    (2, -1): QT_TRANSLATE_NOOP("Menuiserie", "contre-face"),
    (1, 1): QT_TRANSLATE_NOOP("Menuiserie", "chant haut"),
    (1, -1): QT_TRANSLATE_NOOP("Menuiserie", "chant bas"),
    (0, 1): QT_TRANSLATE_NOOP("Menuiserie", "bout droit"),
    (0, -1): QT_TRANSLATE_NOOP("Menuiserie", "bout gauche"),
}
_INSIDE: Final = QT_TRANSLATE_NOOP("Menuiserie", "dans la masse")
_HOLE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "{label} : {count} perçage(s) Ø {diameter}, prof. {depth}, {face}, à {positions}"
)
_CUT: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "{label} : {count} enlèvement(s) {size}, prof. {depth}, {face}, à {positions}",
)
_ADDED: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "{label} : {count} ajout(s) {size}, {face}, à {positions}"
)


class MachiningKind(Enum):
    """Perçage (cylindre), enlèvement (logement, rainure, feuillure…) ou ajout (tenon…)."""

    HOLE = "hole"
    CUT = "cut"
    ADDED = "added"


@dataclass(frozen=True)
class Machining:
    """Un usinage, dans le repère local de la pièce. ``low`` et ``high`` : coins de son
    encombrement ; ``face`` : (indice d'axe, signe) de la face par où il s'ouvre, ``None`` s'il
    ne touche aucune face ; ``depth`` : son étendue le long de cet axe (ou son épaisseur la plus
    faible s'il est dans la masse) ; ``diameter`` : celui d'un perçage, 0 sinon."""

    label: str
    kind: MachiningKind
    low: tuple[float, float, float]
    high: tuple[float, float, float]
    face: tuple[int, int] | None
    depth: float
    diameter: float = 0.0

    @property
    def size(self) -> tuple[float, float, float]:
        """Étendue le long de X, Y et Z."""
        return (
            self.high[0] - self.low[0],
            self.high[1] - self.low[1],
            self.high[2] - self.low[2],
        )


def _points(solid: PlanSolid) -> list[Vec3]:
    """Points dont l'encombrement est celui de ``solid`` (majoré pour un cylindre en biais)."""
    if isinstance(solid, Box):
        return [solid.min, solid.max]
    if isinstance(solid, Cylinder):
        index, sign = solid.axis.index, solid.axis.sign
        start = [solid.base.x, solid.base.y, solid.base.z]
        end = list(start)
        end[index] += sign * solid.height
        corners = []
        for point in (start, end):
            for delta in (-solid.radius, solid.radius):
                moved = [value + delta for value in point]
                moved[index] = point[index]
                corners.append(Vec3(*moved))
        return corners
    if isinstance(solid, Prism):
        shift = solid.extrusion
        return [
            *solid.points,
            *(Vec3(p.x + shift.x, p.y + shift.y, p.z + shift.z) for p in solid.points),
        ]
    if isinstance(solid, SlantedCylinder):
        d, h, r = solid.direction, solid.height, solid.radius
        tip = Vec3(solid.base.x + d.x * h, solid.base.y + d.y * h, solid.base.z + d.z * h)
        return [
            Vec3(p.x + sx * r, p.y + sy * r, p.z + sz * r)
            for p in (solid.base, tip)
            for sx, sy, sz in ((-1, -1, -1), (1, 1, 1))
        ]
    if isinstance(solid, Polyhedron):
        return list(solid.vertices())
    return []


def _face(
    low: Sequence[float], high: Sequence[float], size: Sequence[float]
) -> tuple[int, int] | None:
    """Face de la pièce que touche l'encombrement, de la plus grande à la plus petite : face et
    contre-face, puis chants, puis bouts."""
    for index in (2, 1, 0):
        if high[index] >= size[index] - _TOLERANCE_MM and low[index] > _TOLERANCE_MM:
            return index, 1
        if low[index] <= _TOLERANCE_MM and high[index] < size[index] - _TOLERANCE_MM:
            return index, -1
    return None


def _clipped(value: float, limit: float) -> float:
    return min(max(value, 0.0), limit)


def _one(
    label: str, solid: PlanSolid, kind: MachiningKind, size: Sequence[float]
) -> Machining | None:
    points = _points(solid)
    if not points:
        return None
    raw_low = [min(getattr(p, a) for p in points) for a in "xyz"]
    raw_high = [max(getattr(p, a) for p in points) for a in "xyz"]
    if kind is MachiningKind.ADDED:  # hors de la pièce : encombrement brut
        extent = [raw_high[i] - raw_low[i] for i in range(3)]
        face = _added_face(raw_low, raw_high, size)
        depth = extent[face[0]] if face is not None else min(extent)
        return Machining(label, kind, _triple(raw_low), _triple(raw_high), face, depth)
    low = [_clipped(value, limit) for value, limit in zip(raw_low, size, strict=True)]
    high = [_clipped(value, limit) for value, limit in zip(raw_high, size, strict=True)]
    extent = [high[i] - low[i] for i in range(3)]
    if min(extent) <= _TOLERANCE_MM:
        return None  # rien n'entre dans la pièce
    face = _face(low, high, size)
    depth = extent[face[0]] if face is not None else min(extent)
    diameter = 0.0
    if isinstance(solid, (Cylinder, SlantedCylinder)):
        kind, diameter = MachiningKind.HOLE, 2.0 * solid.radius
    return Machining(label, kind, _triple(low), _triple(high), face, depth, diameter)


def _added_face(
    low: Sequence[float], high: Sequence[float], size: Sequence[float]
) -> tuple[int, int] | None:
    """Face de la pièce d'où sort un ajout (tenon, languette)."""
    for index in (0, 1, 2):
        if low[index] >= size[index] - _TOLERANCE_MM:
            return index, 1
        if high[index] <= _TOLERANCE_MM:
            return index, -1
    return None


def _triple(values: Sequence[float]) -> tuple[float, float, float]:
    return float(values[0]), float(values[1]), float(values[2])


def machinings(
    items: Iterable[tuple[str, PlanSolid, MachiningKind]], size: Sequence[float]
) -> list[Machining]:
    """Usinages de la pièce de cotes ``size`` (longueur, largeur, épaisseur) d'après les formes
    ``items`` (libellé de l'assemblage, forme dans le repère local, enlèvement ou ajout). Les
    formes qui n'entament pas la pièce sont ignorées."""
    found = (_one(label, solid, kind, size) for label, solid, kind in items)
    return [item for item in found if item is not None]


def _number(value: float) -> str:
    rounded = round(value, 1)
    return f"{0.0 if rounded == 0 else rounded:g}"


def _position(item: Machining) -> str:
    """Coin bas gauche (ou centre d'un perçage) vu de face : « x 50 y 15 »."""
    if item.kind is MachiningKind.HOLE:
        x = (item.low[0] + item.high[0]) / 2
        y = (item.low[1] + item.high[1]) / 2
    else:
        x, y = item.low[0], item.low[1]
    return f"x {_number(x)} y {_number(y)}"


def _size_text(item: Machining) -> str:
    return " \u00d7 ".join(_number(value) for value in item.size)


def _group_key(item: Machining) -> tuple[object, ...]:
    return (
        item.label,
        item.kind,
        item.face,
        round(item.depth, 1),
        round(item.diameter, 1),
        tuple(round(value, 1) for value in item.size),
    )


def machining_lines(items: Sequence[Machining]) -> list[tuple[str, dict[str, str]]]:
    """Lignes du tableau des usinages : (gabarit à traduire, valeurs), dans l'ordre des usinages.
    Les usinages identiques d'un même assemblage partagent une ligne qui donne leur nombre et
    jusqu'à ``MAX_POSITIONS`` positions."""
    groups: dict[tuple[object, ...], list[Machining]] = {}
    for item in items:
        groups.setdefault(_group_key(item), []).append(item)
    lines: list[tuple[str, dict[str, str]]] = []
    for group in groups.values():
        first = group[0]
        positions = sorted(_position(item) for item in group)
        shown = "; ".join(positions[:MAX_POSITIONS])
        if len(positions) > MAX_POSITIONS:
            shown += "; …"
        values = {
            "label": first.label,
            "count": str(len(group)),
            "depth": _number(first.depth),
            # Texte à traduire lui aussi : gabarit sans valeur.
            "face": _FACES[first.face] if first.face is not None else _INSIDE,
            "positions": shown,
            "size": _size_text(first),
            "diameter": _number(first.diameter),
        }
        template = {
            MachiningKind.HOLE: _HOLE,
            MachiningKind.CUT: _CUT,
            MachiningKind.ADDED: _ADDED,
        }[first.kind]
        lines.append((template, values))
    return lines


def capped(lines: Sequence[str], more: str) -> list[str]:
    """``lines`` réduites à ``MAX_NOTE_LINES`` : au-delà, la dernière ligne gardée est ``more``
    (déjà traduite, qui peut citer ``{count}``, le nombre de lignes omises)."""
    if len(lines) <= MAX_NOTE_LINES:
        return list(lines)
    kept = list(lines[: MAX_NOTE_LINES - 1])
    return [*kept, more.replace("{count}", str(len(lines) - len(kept)))]
