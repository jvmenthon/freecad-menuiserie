# SPDX-License-Identifier: LGPL-2.1-or-later
"""Usinages d'une pièce pour son plan : formes des plans d'usinage → lignes du tableau.

Les formes d'usinage (``PlanSolid``) sont dans le repère local de la pièce : X sur la longueur,
Y sur la largeur, Z sur l'épaisseur, origine au coin. Sur le plan de pièce, la vue de face
montre X vers la droite et Y vers le haut : une position « x, y » se mesure donc depuis le coin
bas gauche de la vue de face. Chaque usinage est décrit par son encombrement, la face par où il
s'ouvre et sa profondeur (l'épaisseur traversée s'il est débouchant) ; un perçage par son
diamètre, sa longueur le long de son axe et le centre de son entrée. Les usinages identiques d'un
même assemblage sont regroupés sur une ligne.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace
from enum import Enum
from typing import Final

from freecad.menuiserie.core._polyhedron import PlanSolid, Polyhedron, SlantedCylinder
from freecad.menuiserie.core.drawing._names import NAMES
from freecad.menuiserie.core.geometry import Box, Cylinder, Prism, Vec3
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP

__all__ = [
    "CONTINUATION",
    "MAX_NOTE_LINES",
    "NAMES",
    "Machining",
    "MachiningItem",
    "MachiningKind",
    "capped",
    "machining_lines",
    "machinings",
]

_TOLERANCE_MM: Final = 0.01
MAX_POSITIONS: Final = 4  # positions écrites sur une ligne, au plus
MAX_NOTE_LINES: Final = 8  # lignes du tableau des usinages, titre compris (bande de 45 mm)
CONTINUATION: Final = "    "  # retrait des suites d'une ligne coupée à la largeur de la bande
# Où se trouve l'usinage : (indice d'axe, signe) → texte à traduire, avec sa préposition.
_FACES: Final = {
    (2, 1): QT_TRANSLATE_NOOP("Menuiserie", "sur la face"),
    (2, -1): QT_TRANSLATE_NOOP("Menuiserie", "sur la contre-face"),
    (1, 1): QT_TRANSLATE_NOOP("Menuiserie", "sur le chant haut"),
    (1, -1): QT_TRANSLATE_NOOP("Menuiserie", "sur le chant bas"),
    (0, 1): QT_TRANSLATE_NOOP("Menuiserie", "au bout droit"),
    (0, -1): QT_TRANSLATE_NOOP("Menuiserie", "au bout gauche"),
}
_INSIDE: Final = QT_TRANSLATE_NOOP("Menuiserie", "dans la masse")
_HOLE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "{label} : {count} {name} Ø {diameter}, prof. {depth}, {face}, à {positions}"
)
_CUT: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "{label} : {count} {name} {size}, prof. {depth}, {face}, à {positions}"
)
_ADDED: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "{label} : {count} {name} {size}, longueur {depth}, {face}, à {positions}"
)
_DEFAULT_NAMES: Final = {"hole": "hole", "cut": "cut", "added": "added"}


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
    faible s'il est dans la masse) ; ``diameter`` : celui d'un perçage, 0 sinon ; ``entry`` :
    centre de l'entrée d'un perçage (x, y), ``None`` sinon ; ``name`` : nom de l'usinage pour le
    menuisier (clé de ``NAMES``)."""

    label: str
    kind: MachiningKind
    low: tuple[float, float, float]
    high: tuple[float, float, float]
    face: tuple[int, int] | None
    depth: float
    diameter: float = 0.0
    entry: tuple[float, float] | None = None
    name: str = ""  # clé de ``NAMES`` (mortaise, queue…), vide : nom générique du genre

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
    contre-face, puis chants, puis bouts. Un usinage débouchant (qui touche les deux faces
    opposées) s'ouvre sur la première des deux."""
    for index in (2, 1, 0):
        touches_high = high[index] >= size[index] - _TOLERANCE_MM
        touches_low = low[index] <= _TOLERANCE_MM
        if touches_high:
            return index, 1
        if touches_low:
            return index, -1
    return None


def _clipped(value: float, limit: float) -> float:
    return min(max(value, 0.0), limit)


def _axis(solid: Cylinder | SlantedCylinder) -> tuple[Vec3, Vec3]:
    """Début et fin de l'axe d'un perçage (cylindre droit ou en biais)."""
    if isinstance(solid, Cylinder):
        end = [solid.base.x, solid.base.y, solid.base.z]
        end[solid.axis.index] += solid.axis.sign * solid.height
        return solid.base, Vec3(*end)
    d, h = solid.direction, solid.height
    return solid.base, Vec3(solid.base.x + d.x * h, solid.base.y + d.y * h, solid.base.z + d.z * h)


def _inside(start: Vec3, end: Vec3, size: Sequence[float]) -> tuple[Vec3, Vec3] | None:
    """Partie du segment ``start`` → ``end`` dans la pièce (découpe de Liang-Barsky)."""
    first, last = 0.0, 1.0
    origin = (start.x, start.y, start.z)
    delta = (end.x - start.x, end.y - start.y, end.z - start.z)
    for value, step, limit in zip(origin, delta, size, strict=True):
        if abs(step) < 1e-12:
            if value < -_TOLERANCE_MM or value > limit + _TOLERANCE_MM:
                return None
            continue
        low, high = sorted(((0.0 - value) / step, (limit - value) / step))
        first, last = max(first, low), min(last, high)
    if last - first <= 0.0:
        return None

    def at(t: float) -> Vec3:
        return Vec3(*(value + t * step for value, step in zip(origin, delta, strict=True)))

    return at(first), at(last)


def _hole(
    label: str,
    solid: Cylinder | SlantedCylinder,
    low: Sequence[float],
    high: Sequence[float],
    size: Sequence[float],
) -> Machining | None:
    """Perçage : profondeur le long de son axe dans la pièce, position au centre de son
    entrée (le bout de l'axe le plus proche de la face où il s'ouvre)."""
    inside = _inside(*_axis(solid), size)
    if inside is None:
        return None
    start, end = inside
    depth = math.dist((start.x, start.y, start.z), (end.x, end.y, end.z))
    face = _face(low, high, size)
    entry = start
    if face is not None:
        index, sign = face
        plane = size[index] if sign > 0 else 0.0
        entry = min((start, end), key=lambda p: abs((p.x, p.y, p.z)[index] - plane))
    return Machining(
        label,
        MachiningKind.HOLE,
        _triple(low),
        _triple(high),
        face,
        depth,
        2.0 * solid.radius,
        (entry.x, entry.y),
    )


def _one(
    label: str, solid: PlanSolid, kind: MachiningKind, size: Sequence[float]
) -> Machining | None:
    points = _points(solid)
    if not points:
        return None
    raw_low = [min(getattr(p, a) for p in points) for a in "xyz"]
    raw_high = [max(getattr(p, a) for p in points) for a in "xyz"]
    if kind is MachiningKind.ADDED:  # hors de la pièce : encombrement brut
        return _added(label, raw_low, raw_high, size)
    low = [_clipped(value, limit) for value, limit in zip(raw_low, size, strict=True)]
    high = [_clipped(value, limit) for value, limit in zip(raw_high, size, strict=True)]
    extent = [high[i] - low[i] for i in range(3)]
    if min(extent) <= _TOLERANCE_MM:
        return None  # rien n'entre dans la pièce
    if isinstance(solid, (Cylinder, SlantedCylinder)):
        return _hole(label, solid, low, high, size)
    face = _face(low, high, size)
    depth = extent[face[0]] if face is not None else min(extent)
    return Machining(label, kind, _triple(low), _triple(high), face, depth)


def _added(
    label: str, low: Sequence[float], high: Sequence[float], size: Sequence[float]
) -> Machining | None:
    """Ajout (tenon, languette) : ignoré s'il ne touche pas la pièce ; sa face est celle d'où
    il dépasse le plus, sa profondeur ce dépassement."""
    if any(low[i] > size[i] + _TOLERANCE_MM or high[i] < -_TOLERANCE_MM for i in range(3)):
        return None
    face = _added_face(low, high, size)
    extent = [high[i] - low[i] for i in range(3)]
    if face is None:
        depth = min(extent)
    else:
        index, sign = face
        depth = high[index] - size[index] if sign > 0 else -low[index]
    return Machining(label, MachiningKind.ADDED, _triple(low), _triple(high), face, depth)


def _added_face(
    low: Sequence[float], high: Sequence[float], size: Sequence[float]
) -> tuple[int, int] | None:
    """Face de la pièce d'où sort un ajout (tenon, languette) : celle qu'il dépasse le plus."""
    beyond = []
    for index in (0, 1, 2):
        beyond.append((high[index] - size[index], (index, 1)))
        beyond.append((-low[index], (index, -1)))
    amount, face = max(beyond, key=lambda item: item[0])
    return face if amount > _TOLERANCE_MM else None


def _triple(values: Sequence[float]) -> tuple[float, float, float]:
    return float(values[0]), float(values[1]), float(values[2])


MachiningItem = tuple[str, PlanSolid, MachiningKind] | tuple[str, PlanSolid, MachiningKind, str]


def machinings(items: Iterable[MachiningItem], size: Sequence[float]) -> list[Machining]:
    """Usinages de la pièce de cotes ``size`` (longueur, largeur, épaisseur) d'après les formes
    ``items`` (libellé de l'assemblage, forme dans le repère local, enlèvement ou ajout et,
    facultatif, nom de l'usinage : clé de ``NAMES``). Les formes qui n'entament pas la pièce
    sont ignorées."""
    found: list[Machining] = []
    for item in items:
        label, solid, kind = item[0], item[1], item[2]
        name = item[3] if len(item) > 3 else ""
        one = _one(label, solid, kind, size)
        if one is not None:
            found.append(replace(one, name=_name(one, str(name))))
    return found


def _name(item: Machining, name: str) -> str:
    """Nom donné, sinon nom générique du genre ; un perçage garde un nom de perçage."""
    if item.kind is MachiningKind.HOLE and not name.endswith("hole"):
        return "hole"
    return name if name in NAMES else _DEFAULT_NAMES[item.kind.value]


def _number(value: float) -> str:
    """Cote au dixième, écrite à la française (« 58,5 »)."""
    rounded = round(value, 1)
    return f"{0.0 if rounded == 0 else rounded:g}".replace(".", ",")


def _position(item: Machining) -> str:
    """Coin bas gauche (ou centre d'un perçage) vu de face : « x 50 y 15 ». Un tenon ou une
    queue qui sort d'un bout (d'un chant) n'est repéré que le long de ce bout (de ce chant)."""
    if item.entry is not None:
        x, y = item.entry
    else:
        x, y = item.low[0], item.low[1]
    if item.kind is MachiningKind.ADDED and item.face is not None and item.face[0] == 0:
        return f"y {_number(y)}"
    if item.kind is MachiningKind.ADDED and item.face is not None and item.face[0] == 1:
        return f"x {_number(x)}"
    return f"x {_number(x)} y {_number(y)}"


def _size_text(item: Machining) -> str:
    """Taille vue de la face d'entrée : les deux étendues autres que la profondeur (largeur sur
    la longueur ou la largeur de la pièce, puis l'autre), les trois dans la masse."""
    sizes = item.size
    if item.face is None:
        shown = list(sizes)
    else:
        shown = [value for index, value in enumerate(sizes) if index != item.face[0]]
    return " \u00d7 ".join(_number(value) for value in shown)


def _group_key(item: Machining) -> tuple[object, ...]:
    return (
        item.label,
        item.kind,
        item.name,
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
            # Texte à traduire lui aussi, au singulier ou au pluriel.
            "name": NAMES[first.name][0 if len(group) == 1 else 1],
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
    (déjà traduite, qui peut citer ``{count}``, le nombre d'usinages omis). Un usinage coupé
    sur plusieurs lignes (suites en retrait ``CONTINUATION``) est gardé ou omis en entier."""
    if len(lines) <= MAX_NOTE_LINES:
        return list(lines)
    keep = MAX_NOTE_LINES - 1
    while keep > 1 and lines[keep].startswith(CONTINUATION):
        keep -= 1
    omitted = sum(1 for line in lines[keep:] if not line.startswith(CONTINUATION))
    return [*lines[:keep], more.replace("{count}", str(omitted))]
