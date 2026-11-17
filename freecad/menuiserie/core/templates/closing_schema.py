# SPDX-License-Identifier: LGPL-2.1-or-later
"""Schéma isométrique du caisson fermé (ADR 0064, maquette B) : projection et clic, sans Qt.

Le widget du panneau (``gui/``) ne fait que peindre les :class:`Face` calculées ici et traduire
un clic en élément par :func:`hit_test`. Le caisson est vu de l'avant, de la droite et du dessus
(l'avant est en ``Y = 0``, au premier plan) : on voit les faces dont la normale sortante est +X,
-Y ou +Z. Les éléments se dessinent de l'arrière vers l'avant ; un clic désigne l'élément activé
le plus proche de l'observateur, puis, faute d'élément activé, un élément désactivé.
"""

from __future__ import annotations

import math
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from typing import Final

from freecad.menuiserie.core.geometry import Vec3
from freecad.menuiserie.core.templates import Layout
from freecad.menuiserie.core.templates.closing import wanted_extents

__all__ = ["Face", "centroid", "click_point", "fit", "hit_test", "project", "schema_faces"]

Point2 = tuple[float, float]
_ROOT2: Final = math.sqrt(2.0)
_ROOT6: Final = math.sqrt(6.0)


@dataclass(frozen=True)
class Face:
    """Face visible d'un élément : polygone en coordonnées d'écran (y vers le bas), élément et
    orientation (``"top"``, ``"front"`` ou ``"right"``, pour l'ombrage) ; ``depth`` ordonne les
    éléments (plus grand = plus proche de l'observateur)."""

    element: str
    side: str
    points: tuple[Point2, ...]
    depth: float

    def area(self) -> float:
        """Aire du polygone (formule des lacets)."""
        pairs = zip(self.points, (*self.points[1:], self.points[0]), strict=True)
        return abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in pairs)) / 2


def project(point: Vec3) -> Point2:
    """Projection isométrique : X vers la droite et le bas, Y (profondeur) vers la droite et le
    haut, Z vers le haut ; le point de vue est en (+X, -Y, +Z)."""
    return ((point.x + point.y) / _ROOT2, (point.x - point.y - 2 * point.z) / _ROOT6)


def _faces_of(element: str, spans: Sequence[tuple[float, float]]) -> list[Face]:
    (x0, x1), (y0, y1), (z0, z1) = spans
    depth = (x0 + x1) / 2 - (y0 + y1) / 2 + (z0 + z1) / 2
    corners = {
        "right": [(x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)],
        "front": [(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)],
        "top": [(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)],
    }
    return [
        Face(element, side, tuple(project(Vec3(*c)) for c in points), depth)
        for side, points in corners.items()
    ]


def schema_faces(layout: Layout) -> tuple[Face, ...]:
    """Faces visibles de **toutes** les pièces de ``layout`` (de l'ancre aux éléments, même ceux
    que le menuiserie désactive : on les dessine en pointillé), de l'arrière vers l'avant."""
    faces = [
        face
        for piece in layout.pieces
        for face in _faces_of(piece.key, wanted_extents(layout, piece.key))
    ]
    return tuple(sorted(faces, key=lambda face: face.depth))


def fit(
    faces: Sequence[Face], width: float, height: float, margin: float = 8.0
) -> tuple[Face, ...]:
    """Faces mises à l'échelle (même facteur sur x et y) et centrées dans ``width x height``."""
    points = [p for face in faces for p in face.points]
    if not points:
        return ()
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    span_x, span_y = max(xs) - min(xs), max(ys) - min(ys)
    room_x, room_y = max(width - 2 * margin, 1.0), max(height - 2 * margin, 1.0)
    scale = min(room_x / span_x if span_x else math.inf, room_y / span_y if span_y else math.inf)
    scale = 1.0 if math.isinf(scale) else scale
    left = margin + (room_x - span_x * scale) / 2 - min(xs) * scale
    top = margin + (room_y - span_y * scale) / 2 - min(ys) * scale
    return tuple(
        Face(
            f.element,
            f.side,
            tuple((x * scale + left, y * scale + top) for x, y in f.points),
            f.depth,
        )
        for f in faces
    )


def centroid(face: Face) -> Point2:
    """Moyenne des sommets (centre d'un parallélogramme)."""
    count = len(face.points)
    return (sum(p[0] for p in face.points) / count, sum(p[1] for p in face.points) / count)


def _inside(face: Face, point: Point2) -> bool:
    """Vrai si ``point`` est dans le polygone (lancer de rayon)."""
    x, y = point
    inside = False
    pairs = zip(face.points, (*face.points[1:], face.points[0]), strict=True)
    for (x1, y1), (x2, y2) in pairs:
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


def hit_test(faces: Sequence[Face], enabled: Collection[str], point: Point2) -> str | None:
    """Élément cliqué en ``point`` : le plus proche des éléments ``enabled``, sinon le plus proche
    des autres ; ``None`` hors du dessin. ``faces`` est dans l'ordre de :func:`schema_faces`."""
    front_first = [face for face in reversed(faces) if _inside(face, point)]
    for wanted in (True, False):
        for face in front_first:
            if (face.element in enabled) is wanted:
                return face.element
    return None


def click_point(faces: Sequence[Face], enabled: Collection[str], element: str) -> Point2 | None:
    """Point où un clic désigne ``element`` (le plus proche du centre de sa plus grande face,
    parmi les points de ses faces qu'aucun élément plus proche ne couvre) ; ``None`` si
    l'élément est entièrement caché."""
    mine = [face for face in faces if face.element == element]
    if not mine:
        return None
    center = centroid(max(mine, key=Face.area))
    steps = 24
    found: list[Point2] = []
    for face in mine:
        xs, ys = [p[0] for p in face.points], [p[1] for p in face.points]
        for i in range(steps + 1):
            for j in range(steps + 1):
                point = (
                    min(xs) + (max(xs) - min(xs)) * i / steps,
                    min(ys) + (max(ys) - min(ys)) * j / steps,
                )
                if _inside(face, point) and hit_test(faces, enabled, point) == element:
                    found.append(point)
    return min(found, key=lambda p: math.dist(p, center)) if found else None
