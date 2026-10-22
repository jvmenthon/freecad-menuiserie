# SPDX-License-Identifier: LGPL-2.1-or-later
"""Miniature isométrique d'une pièce pour la liste de débit : projection et dessin SVG purs.

Module privé : la façade ``core.cutlist`` ré-exporte l'API publique. Aucune dépendance à FreeCAD
ni à Qt : ``features/cutlist_thumbnail.py`` discrétise la forme usinée (``Part.Shape``) en
:class:`ThumbFace` ; ce module projette en isométrie, retire les faces tournées vers l'arrière,
les trie du plus loin au plus proche (algorithme du peintre), les ombre d'après leur normale et
écrit un SVG autonome (ni script, ni police, ni ressource externe) de 120 x 80 unités, que Qt
rastérise (quatre fois plus fin) pour le tableau et le PDF.

Repère de la pièce : X = longueur, Y = largeur, Z = épaisseur ; l'observateur regarde depuis
(+X, +Y, +Z), comme les icônes de l'atelier (``tools/generer_icones.py``).
"""

from __future__ import annotations

import base64
import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Final

__all__ = [
    "DEFAULT_COLOR",
    "THUMBNAIL_HEIGHT",
    "THUMBNAIL_WIDTH",
    "Point2",
    "Point3",
    "ThumbFace",
    "box_faces",
    "isometric",
    "svg_data_uri",
    "thumbnail_svg",
]

Point2 = tuple[float, float]
Point3 = tuple[float, float, float]
Triangle = tuple[Point3, Point3, Point3]

THUMBNAIL_WIDTH: Final = 120  # taille affichée (px) ; le SVG est écrit 4 fois plus grand
THUMBNAIL_HEIGHT: Final = 80
DEFAULT_COLOR: Final = (196, 160, 112)  # bois clair, quand le matériau est inconnu
_RASTER_SCALE: Final = 4
_MARGIN: Final = 4.0  # marge autour du dessin, en unités du SVG
_COS_30: Final = math.cos(math.radians(30))
_VIEW: Final = (1.0, 1.0, 1.0)  # vers l'observateur
_LIGHT: Final = (-0.15, 0.45, 0.88)  # le dessus est le plus clair, comme les icônes
_AMBIENT: Final = 0.65
_DIRECT: Final = 0.45
_EDGE_COLOR: Final = "#2a1d12"
_EDGE_WIDTH: Final = 0.9
_MIN_NORMAL: Final = 1e-12


@dataclass(frozen=True)
class ThumbFace:
    """Face discrétisée d'une pièce : triangles d'orientation sortante (sens trigonométrique vu
    de l'extérieur de la matière) et arêtes de son contour en polylignes (repère de la pièce,
    en mm)."""

    triangles: tuple[Triangle, ...]
    edges: tuple[tuple[Point3, ...], ...] = ()


def isometric(point: Point3) -> Point2:
    """Projection isométrique : X vers la droite et le bas, Y vers la gauche et le bas, Z vers le
    haut (axe vertical de l'image orienté vers le bas, comme en SVG)."""
    x, y, z = point
    return ((x - y) * _COS_30, (x + y) * 0.5 - z)


def _depth(point: Point3) -> float:
    return point[0] + point[1] + point[2]


def _normal(triangle: Triangle) -> Point3 | None:
    """Normale unitaire d'un triangle, ``None`` s'il est dégénéré."""
    (ax, ay, az), (bx, by, bz), (cx, cy, cz) = triangle
    ux, uy, uz = bx - ax, by - ay, bz - az
    vx, vy, vz = cx - ax, cy - ay, cz - az
    nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
    length = math.sqrt(nx * nx + ny * ny + nz * nz)
    if length < _MIN_NORMAL:
        return None
    return (nx / length, ny / length, nz / length)


def _dot(first: Point3, second: Point3) -> float:
    return first[0] * second[0] + first[1] * second[1] + first[2] * second[2]


def _shade(color: tuple[int, int, int], normal: Point3) -> str:
    """Couleur ``#rrggbb`` d'une face : celle du matériau, éclairée d'après sa normale."""
    factor = _AMBIENT + _DIRECT * max(0.0, _dot(normal, _LIGHT))
    red, green, blue = (min(255, round(channel * factor)) for channel in color)
    return f"#{red:02x}{green:02x}{blue:02x}"


def _visible(face: ThumbFace) -> list[tuple[Triangle, Point3]]:
    """Triangles de ``face`` tournés vers l'observateur, avec leur normale."""
    found = []
    for triangle in face.triangles:
        normal = _normal(triangle)
        if normal is not None and _dot(normal, _VIEW) > 0.0:
            found.append((triangle, normal))
    return found


def _face_depth(triangles: Sequence[tuple[Triangle, Point3]]) -> float:
    """Profondeur moyenne des sommets : la face la plus proche est dessinée en dernier."""
    depths = [_depth(vertex) for triangle, _normal_ in triangles for vertex in triangle]
    return math.fsum(depths) / len(depths)


class _Sheet:
    """Éléments SVG projetés (en unités de la projection), mis à l'échelle à l'écriture."""

    def __init__(self) -> None:
        self.items: list[tuple[str, str, list[list[Point2]]]] = []

    def points(self) -> Iterable[Point2]:
        for _kind, _style, shapes in self.items:
            for shape in shapes:
                yield from shape


def _project(
    face: ThumbFace,
    triangles: Sequence[tuple[Triangle, Point3]],
    color: tuple[int, int, int],
    sheet: _Sheet,
) -> None:
    by_fill: dict[str, list[list[Point2]]] = {}
    for triangle, normal in triangles:
        by_fill.setdefault(_shade(color, normal), []).append([isometric(p) for p in triangle])
    for fill, shapes in by_fill.items():
        sheet.items.append(("fill", fill, shapes))
    if face.edges:
        sheet.items.append(("edge", _EDGE_COLOR, [[isometric(p) for p in e] for e in face.edges]))


def _path(shapes: Iterable[Sequence[Point2]], scale: float, origin: Point2, *, closed: bool) -> str:
    ox, oy = origin
    parts = []
    for shape in shapes:
        points = " L".join(f"{ox + scale * x:.2f},{oy + scale * y:.2f}" for x, y in shape)
        parts.append(f"M{points}{' Z' if closed else ''}")
    return " ".join(parts)


def _document(width: int, height: int, body: Sequence[str]) -> str:
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{width * _RASTER_SCALE}" height="{height * _RASTER_SCALE}" '
        f'viewBox="0 0 {width} {height}">\n' + "\n".join(body) + "\n</svg>\n"
    )


def thumbnail_svg(faces: Iterable[ThumbFace], color: tuple[int, int, int] = DEFAULT_COLOR) -> str:
    """SVG de la pièce faite de ``faces``, en isométrie : faces visibles remplies de ``color``
    ombrée selon leur normale, arêtes visibles en trait sombre, dessin centré et mis à
    l'échelle dans 120 x 80 unités. Un SVG vide (aucune face visible) ne contient que le cadre.
    """
    visible = [(face, _visible(face)) for face in faces]
    ordered = sorted((pair for pair in visible if pair[1]), key=lambda pair: _face_depth(pair[1]))
    sheet = _Sheet()
    for face, triangles in ordered:
        _project(face, triangles, color, sheet)
    points = list(sheet.points())
    if not points:
        return _document(THUMBNAIL_WIDTH, THUMBNAIL_HEIGHT, [])
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    span_x, span_y = max(max(xs) - min(xs), 1e-9), max(max(ys) - min(ys), 1e-9)
    scale = min((THUMBNAIL_WIDTH - 2 * _MARGIN) / span_x, (THUMBNAIL_HEIGHT - 2 * _MARGIN) / span_y)
    origin = (
        THUMBNAIL_WIDTH / 2 - scale * (max(xs) + min(xs)) / 2,
        THUMBNAIL_HEIGHT / 2 - scale * (max(ys) + min(ys)) / 2,
    )
    body = []
    for kind, style, shapes in sheet.items:
        if kind == "fill":
            body.append(
                f'<path d="{_path(shapes, scale, origin, closed=True)}" fill="{style}" '
                f'stroke="{style}" stroke-width="0.6" stroke-linejoin="round"/>'
            )
        else:
            body.append(
                f'<path d="{_path(shapes, scale, origin, closed=False)}" fill="none" '
                f'stroke="{style}" stroke-width="{_EDGE_WIDTH}" stroke-linecap="round" '
                'stroke-linejoin="round"/>'
            )
    return _document(THUMBNAIL_WIDTH, THUMBNAIL_HEIGHT, body)


def box_faces(length: float, width: float, thickness: float) -> tuple[ThumbFace, ...]:
    """Six faces d'une boîte L x l x e (repli de la miniature : boîte de débit), orientées vers
    l'extérieur ; ``ValueError`` si une cote n'est pas un nombre fini strictement positif."""
    sizes = (length, width, thickness)
    if not all(math.isfinite(size) and size > 0 for size in sizes):
        raise ValueError(f"cotes de boîte invalides : {sizes!r}")
    x, y, z = sizes
    quads: tuple[tuple[Point3, Point3, Point3, Point3], ...] = (
        ((0, 0, 0), (0, y, 0), (x, y, 0), (x, 0, 0)),  # dessous (Z-)
        ((0, 0, z), (x, 0, z), (x, y, z), (0, y, z)),  # dessus (Z+)
        ((0, 0, 0), (x, 0, 0), (x, 0, z), (0, 0, z)),  # Y-
        ((0, y, 0), (0, y, z), (x, y, z), (x, y, 0)),  # Y+
        ((0, 0, 0), (0, 0, z), (0, y, z), (0, y, 0)),  # X-
        ((x, 0, 0), (x, y, 0), (x, y, z), (x, 0, z)),  # X+
    )
    return tuple(ThumbFace(((a, b, c), (a, c, d)), ((a, b, c, d, a),)) for a, b, c, d in quads)


def svg_data_uri(svg: str) -> str:
    """URI ``data:`` d'un SVG : la miniature voyage dans le HTML sans fichier ni ressource
    externe. ``ValueError`` si le texte n'est pas un document SVG."""
    if not svg.lstrip().startswith("<svg"):
        raise ValueError("miniature : document SVG attendu")
    encoded = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"
