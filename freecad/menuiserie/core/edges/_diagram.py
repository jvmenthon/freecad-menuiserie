# SPDX-License-Identifier: LGPL-2.1-or-later
"""Dessins cliquables d'une boîte pour choisir ses arêtes (issue #5) : patron déplié en croix et
boîte en perspective, et ce qu'un clic y désigne.

Module privé, sans Qt : le panneau peint et teste les clics avec ces calculs, en pixels (``y``
vers le bas). Un clic désigne une arête (un côté de face du patron, un trait de la boîte) ou une
face (son intérieur). Patron : la face avant au centre, dessus au-dessus, dessous au-dessous,
gauche, droite et arrière de part et d'autre (les côtés voisins sont la même arête, comme une
fois replié). Boîte : vue de l'avant, de la droite et du dessus ; les faces cachées (dessous,
arrière, gauche) sont dessinées écartées de la boîte pour rester cliquables, leurs arêtes en
pointillés à leur vraie place.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final

from freecad.menuiserie.core.edges._ids import EdgeId, all_edges, parse_face
from freecad.menuiserie.core.edges._layout import face_sides
from freecad.menuiserie.core.edges._pick import edge_ends
from freecad.menuiserie.core.geometry import Axis, Vec3
from freecad.menuiserie.core.part_model import Dimensions
from freecad.menuiserie.core.vectors import dot

__all__ = [
    "HIDDEN_FACES",
    "NET_CELLS",
    "BoxView",
    "Cell",
    "DrawnEdge",
    "DrawnFace",
    "Hit",
    "box_hit",
    "box_view",
    "face_corners",
    "face_ring_codes",
    "net_cells",
    "net_hit",
]

Point = tuple[float, float]

# Patron en croix : face → (colonne, ligne) dans une grille de 4 x 3 cases.
NET_CELLS: Final = {
    "Z+": (1, 0),
    "X-": (0, 1),
    "Y-": (1, 1),
    "X+": (2, 1),
    "Y+": (3, 1),
    "Z-": (1, 2),
}
HIDDEN_FACES: Final = ("Z-", "Y+", "X-")  # cachées dans la boîte vue de l'avant, droite, dessus
_MIN_RATIO: Final = 0.3  # une cote dessinée vaut au moins cette part de la plus grande
_GHOST_GAP: Final = 0.35  # écart des faces cachées, part de la plus grande cote dessinée
_SIDE_RATIO: Final = 0.22  # bande cliquable d'un côté de case du patron, part de la case
_VIEW: Final = Vec3(1.0, -1.0, 1.0)  # vers l'observateur
_RIGHT: Final = Vec3(1.0, 1.0, 0.0).scaled(1 / math.sqrt(2.0))
_UP: Final = Vec3(-1.0, 1.0, 2.0).scaled(1 / math.sqrt(6.0))


@dataclass(frozen=True)
class Hit:
    """Ce qu'un clic désigne : ``kind`` vaut ``"edge"`` (``code`` d'arête, ``"Z+Y-"``) ou
    ``"face"`` (``code`` de face, ``"Z+"``)."""

    kind: str
    code: str


@dataclass(frozen=True)
class Cell:
    """Case carrée d'une face du patron : coin haut gauche et côté, en pixels."""

    face: str
    x: float
    y: float
    size: float

    def sides(self) -> dict[str, tuple[Point, Point]]:
        """Segments des quatre côtés (haut, gauche, droite, bas)."""
        left, top, right, bottom = self.x, self.y, self.x + self.size, self.y + self.size
        return {
            "top": ((left, top), (right, top)),
            "left": ((left, top), (left, bottom)),
            "right": ((right, top), (right, bottom)),
            "bottom": ((left, bottom), (right, bottom)),
        }


def net_cells(width: float, height: float, margin: float = 4.0) -> tuple[Cell, ...]:
    """Les six cases du patron, centrées dans ``width`` x ``height`` pixels."""
    size = max(1.0, min((width - 2 * margin) / 4, (height - 2 * margin) / 3))
    left, top = (width - 4 * size) / 2, (height - 3 * size) / 2
    return tuple(
        Cell(face, left + column * size, top + row * size, size)
        for face, (column, row) in NET_CELLS.items()
    )


def net_hit(cells: tuple[Cell, ...], x: float, y: float) -> Hit | None:
    """Arête (bande de bord d'une case, le bord le plus proche) ou face (intérieur) sous le
    point ``(x, y)`` du patron ; ``None`` hors des cases."""
    for cell in cells:
        dx, dy = x - cell.x, y - cell.y
        if not (0 <= dx <= cell.size and 0 <= dy <= cell.size):
            continue
        distances = {"top": dy, "bottom": cell.size - dy, "left": dx, "right": cell.size - dx}
        side = min(distances, key=lambda name: distances[name])
        if distances[side] <= cell.size * _SIDE_RATIO:
            edge = next(e for s, _n, e in face_sides(cell.face) if s == side)
            return Hit("edge", edge.code)
        return Hit("face", cell.face)
    return None


def face_corners(dimensions: Dimensions, face: str) -> tuple[Vec3, Vec3, Vec3, Vec3]:
    """Les quatre coins de la face ``face`` (``"Z+"``) de la boîte, dans l'ordre du contour
    (repère local, mm)."""
    axis = parse_face(face)
    sizes = (dimensions.length, dimensions.width, dimensions.thickness)
    fixed = sizes[axis.index] if axis.sign > 0 else 0.0
    one, two = (index for index in range(3) if index != axis.index)
    corners = []
    for a, b in ((0.0, 0.0), (sizes[one], 0.0), (sizes[one], sizes[two]), (0.0, sizes[two])):
        values = [0.0, 0.0, 0.0]
        values[axis.index], values[one], values[two] = fixed, a, b
        corners.append(Vec3.of(values))
    return corners[0], corners[1], corners[2], corners[3]


@dataclass(frozen=True)
class DrawnEdge:
    """Arête de la boîte dessinée : code, deux bouts (pixels), cachée ou non."""

    code: str
    start: Point
    end: Point
    hidden: bool


@dataclass(frozen=True)
class DrawnFace:
    """Face dessinée : code, contour (pixels) ; une face cachée est écartée de la boîte."""

    code: str
    outline: tuple[Point, ...]
    hidden: bool


@dataclass(frozen=True)
class BoxView:
    """Boîte en perspective : faces cachées écartées, faces visibles, arêtes."""

    faces: tuple[DrawnFace, ...]
    edges: tuple[DrawnEdge, ...]


def _drawn_sizes(dimensions: Dimensions) -> Dimensions:
    """Cotes dessinées : une planche fine reste lisible (cote minimale relevée)."""
    sizes = (dimensions.length, dimensions.width, dimensions.thickness)
    floor = max(sizes) * _MIN_RATIO
    return Dimensions(*(max(size, floor) for size in sizes))


def _project(point: Vec3) -> Point:
    return dot(point, _RIGHT), -dot(point, _UP)


def box_view(dimensions: Dimensions, width: float, height: float, margin: float = 6.0) -> BoxView:
    """Boîte de proportions ``dimensions`` dessinée dans ``width`` x ``height`` pixels."""
    drawn = _drawn_sizes(dimensions)
    gap = max(drawn.length, drawn.width, drawn.thickness) * _GHOST_GAP
    raw_faces: list[tuple[str, tuple[Point, ...], bool]] = []
    for face in ("Z-", "Y+", "X-", "Y-", "X+", "Z+"):
        hidden = face in HIDDEN_FACES
        shift = parse_face(face).unit().scaled(gap if hidden else 0.0)
        corners = face_corners(drawn, face)
        raw_faces.append((face, tuple(_project(c + shift) for c in corners), hidden))
    raw_edges: list[tuple[str, Point, Point, bool]] = []
    for edge in all_edges():
        start, end = edge_ends(drawn, edge)
        raw_edges.append((edge.code, _project(start), _project(end), _is_hidden(edge)))
    points = [p for _, outline, _ in raw_faces for p in outline]
    low_x, high_x = min(p[0] for p in points), max(p[0] for p in points)
    low_y, high_y = min(p[1] for p in points), max(p[1] for p in points)
    scale = min(
        (width - 2 * margin) / max(high_x - low_x, 1e-9),
        (height - 2 * margin) / max(high_y - low_y, 1e-9),
    )
    off_x = (width - (high_x - low_x) * scale) / 2 - low_x * scale
    off_y = (height - (high_y - low_y) * scale) / 2 - low_y * scale

    def place(point: Point) -> Point:
        return point[0] * scale + off_x, point[1] * scale + off_y

    return BoxView(
        tuple(DrawnFace(code, tuple(map(place, line)), hidden) for code, line, hidden in raw_faces),
        tuple(DrawnEdge(code, place(a), place(b), hidden) for code, a, b, hidden in raw_edges),
    )


def _is_hidden(edge: EdgeId) -> bool:
    return all(face.value[1] + face.value[0] in HIDDEN_FACES for face in (edge.first, edge.second))


def _segment_distance(point: Point, start: Point, end: Point) -> float:
    (px, py), (ax, ay), (bx, by) = point, start, end
    vx, vy = bx - ax, by - ay
    length = vx * vx + vy * vy
    t = 0.0 if length == 0 else max(0.0, min(1.0, ((px - ax) * vx + (py - ay) * vy) / length))
    return math.hypot(px - (ax + t * vx), py - (ay + t * vy))


def _inside(point: Point, outline: tuple[Point, ...]) -> bool:
    x, y = point
    inside = False
    for (ax, ay), (bx, by) in zip(outline, outline[1:] + outline[:1], strict=True):
        if (ay > y) != (by > y) and x < ax + (y - ay) * (bx - ax) / (by - ay):
            inside = not inside
    return inside


def box_hit(view: BoxView, x: float, y: float, tolerance: float = 6.0) -> Hit | None:
    """Arête (trait le plus proche à moins de ``tolerance`` pixels, visible d'abord, puis côté
    d'une face cachée écartée) ou face (intérieur d'une face) sous ``(x, y)`` ; ``None``
    ailleurs."""
    point = (x, y)
    for hidden in (False, True):
        near = [
            (_segment_distance(point, e.start, e.end), e.code)
            for e in view.edges
            if e.hidden == hidden
        ]
        if near and min(near)[0] <= tolerance:
            return Hit("edge", min(near)[1])
    for face in view.faces:
        if not face.hidden:
            continue
        outline = face.outline
        sides = zip(outline, outline[1:] + outline[:1], strict=True)
        for (start, end), code in zip(sides, face_ring_codes(face.code), strict=True):
            if _segment_distance(point, start, end) <= tolerance:
                return Hit("edge", code)
    for face in reversed(view.faces):  # les faces visibles, dessinées en dernier, d'abord
        if _inside(point, face.outline):
            return Hit("face", face.code)
    return None


def face_ring_codes(face: str) -> tuple[str, ...]:
    """Codes des arêtes le long du contour de :func:`face_corners`, côté par côté."""
    axis = parse_face(face)
    one, two = (index for index in range(3) if index != axis.index)
    # contour : (0,0) → (a,0) [le long de ``one``, à ``two`` = 0] → (a,b) [``one`` = max] →
    # (0,b) [``two`` = max] → (0,0) [``one`` = 0]
    neighbours = (
        Axis.of(two, -1),
        Axis.of(one, +1),
        Axis.of(two, +1),
        Axis.of(one, -1),
    )
    return tuple(EdgeId.between(axis, neighbour).code for neighbour in neighbours)
