# SPDX-License-Identifier: LGPL-2.1-or-later
"""Géométrie pure du glissement dans la vue 3D (SM-c) : flèches et poignées saisissables, rayon de
la souris, dessin à poser (traits et points), cadence de recalcul. Aucun import de FreeCAD, de Qt
ni de pivy : ``view.py`` fournit les projections, ``overlay.py`` pose le dessin.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Final

from freecad.menuiserie.core.geometry import Box, Vec3
from freecad.menuiserie.core.magnet import (
    THICKNESS_AXIS,
    Arrow,
    Guide,
    GuideKind,
    Handle,
    PixelTarget,
    Ray,
    arrows,
)
from freecad.menuiserie.core.snap import Frame

__all__ = [
    "ARROW_PX",
    "MAGNET_PX",
    "Dots",
    "Drawing",
    "Layout",
    "Solid",
    "Stroke",
    "Throttle",
    "arrow_key",
    "build_drawing",
    "build_layout",
    "guide_outline",
    "handle_key",
    "mouse_ray",
    "parse_key",
    "pixel_targets",
    "target_line",
]

ARROW_PX: Final = 80.0  # longueur des flèches à l'écran
HEAD_RATIO: Final = 0.15  # barbes de la pointe, part de la longueur
HANDLE_RATIO: Final = 0.3  # longueur de la tige d'une poignée (zone de saisie), part des flèches
CUBE_RATIO: Final = 0.25  # demi-côté du cube au bout de la tige, part de la longueur de la tige
MAGNET_PX: Final = 10.0  # tolérance de l'aimant à l'écran
MAX_RATE: Final = 30  # recalculs de la brute par seconde (poignée)
AXIS_COLORS: Final = ((0.86, 0.15, 0.15), (0.15, 0.65, 0.15), (0.2, 0.3, 0.9))  # X, Y, Z
HANDLE_COLOR: Final = (1.0, 0.55, 0.0)
HOVER_COLOR: Final = (1.0, 0.85, 0.1)
GUIDE_COLOR: Final = (1.0, 0.1, 0.8)
Color = tuple[float, float, float]
Project = Callable[[Vec3], tuple[float, float]]


def arrow_key(axis: int) -> str:
    """Clé de la flèche de l'axe ``axis`` (0, 1 ou 2)."""
    return f"arrow{axis}"


def handle_key(handle: Handle) -> str:
    """Clé de la poignée ``handle``."""
    return f"handle{handle.axis}{'e' if handle.at_end else 's'}"


def parse_key(key: str) -> int | Handle:
    """Axe d'une flèche (``int``) ou poignée (:class:`Handle`) désignée par ``key``."""
    if key.startswith("arrow") and key[5:] in ("0", "1", "2"):
        return int(key[5:])
    if key.startswith("handle") and key[6:7] in ("0", "1", "2") and key[7:] in ("s", "e"):
        return Handle(int(key[6]), key[7] == "e")
    raise ValueError(f"clé de flèche ou de poignée inconnue : {key!r}")


def mouse_ray(focal: Vec3, direction: Vec3, camera: Vec3 | None) -> Ray:
    """Rayon de la souris : ``focal`` est le point du plan focal sous le curseur ; caméra
    orthogonale (``camera`` absent) : direction de vue ; perspective : caméra vers ``focal``."""
    if camera is None:
        return Ray(focal, direction)
    return Ray(camera, Vec3(focal.x - camera.x, focal.y - camera.y, focal.z - camera.z))


@dataclass(frozen=True)
class Layout:
    """Ce qui est dessiné et saisissable sur la pièce : repère global, boîte (repère de la pièce),
    flèches des axes libres, poignées (poignée, centre de sa face en coordonnées globales) et
    longueur en mm de la tige (et zone de saisie) dessinée sur chaque poignée."""

    frame: Frame
    box: Box
    arrows: tuple[Arrow, ...]
    handles: tuple[tuple[Handle, Vec3], ...]
    handle_mm: float = 0.0


def _face_center(box: Box, handle: Handle) -> Vec3:
    """Point de la poignée : milieu de sa face ; les poignées d'épaisseur, que le départ des
    flèches cacherait, sont décalées d'un quart de longueur, l'une vers chaque bout."""
    values = [box.center(i) for i in range(3)]
    values[handle.axis] = box.hi(handle.axis) if handle.at_end else box.lo(handle.axis)
    if handle.axis == THICKNESS_AXIS:
        quarter = (box.hi(0) - box.lo(0)) / 4
        values[0] += -quarter if handle.at_end else quarter
    return Vec3.of(values)


def build_layout(
    frame: Frame,
    box: Box,
    size_mm: float,
    fixed_axes: frozenset[int],
    resizable_axes: frozenset[int],
) -> Layout:
    """Flèches (hors axes pilotés par une formule) et poignées (axes redimensionnables : les
    deux faces de bout) d'une pièce de repère ``frame`` et de boîte ``box``."""
    free = tuple(a for a in arrows(frame, box, size_mm) if a.axis not in fixed_axes)
    to_global = frame.to_transform()
    handles = tuple(
        (handle, to_global.apply(_face_center(box, handle)))
        for axis in sorted(resizable_axes)
        for handle in (Handle(axis, False), Handle(axis, True))
    )
    return Layout(frame, box, free, handles, HANDLE_RATIO * size_mm)


def pixel_targets(layout: Layout, project: Project) -> list[PixelTarget]:
    """Cibles saisissables en pixels : poignées d'abord (elles l'emportent à égalité), chacune
    par son centre et par sa tige, puis flèches."""
    targets = [PixelTarget(handle_key(h), project(p)) for h, p in layout.handles]
    axes = (layout.frame.x, layout.frame.y, layout.frame.z)
    for handle, point in layout.handles:
        start = project(_plus(point, axes[handle.axis], -layout.handle_mm))
        end = project(_plus(point, axes[handle.axis], layout.handle_mm))
        targets.append(PixelTarget(handle_key(handle), start, end))
    for arrow in layout.arrows:
        targets.append(PixelTarget(arrow_key(arrow.axis), project(arrow.start), project(arrow.end)))
    return targets


def target_line(layout: Layout, key: str) -> Ray:
    """Droite que la flèche ou la poignée ``key`` fait suivre : l'axe de la pièce, orienté dans
    son sens positif ; ``ValueError`` si ``key`` n'est plus dans ``layout``."""
    target = parse_key(key)
    axes = (layout.frame.x, layout.frame.y, layout.frame.z)
    if isinstance(target, int):
        for arrow in layout.arrows:
            if arrow.axis == target:
                return arrow.line()
    else:
        for handle, point in layout.handles:
            if handle == target:
                return Ray(point, axes[handle.axis])
    raise ValueError(f"{key!r} absente de la disposition")


@dataclass(frozen=True)
class Stroke:
    """Polylignes d'une couleur et d'une épaisseur (pixels)."""

    color: Color
    width: float
    lines: tuple[tuple[Vec3, ...], ...]


@dataclass(frozen=True)
class Dots:
    """Points d'une couleur et d'une taille (pixels)."""

    color: Color
    size: float
    points: tuple[Vec3, ...]


@dataclass(frozen=True)
class Solid:
    """Faces pleines d'une couleur (polygones convexes, sommets dans l'ordre)."""

    color: Color
    faces: tuple[tuple[Vec3, ...], ...]


@dataclass(frozen=True)
class Drawing:
    """Tout ce que l'incrustation affiche."""

    strokes: tuple[Stroke, ...] = ()
    dots: tuple[Dots, ...] = ()
    solids: tuple[Solid, ...] = ()


def _plus(a: Vec3, b: Vec3, factor: float) -> Vec3:
    return Vec3(a.x + b.x * factor, a.y + b.y * factor, a.z + b.z * factor)


def _arrow_lines(arrow: Arrow, frame: Frame) -> tuple[tuple[Vec3, ...], ...]:
    """Tige et quatre barbes de la pointe (le long des deux autres axes de la pièce)."""
    axes = (frame.x, frame.y, frame.z)
    span = Vec3(
        arrow.end.x - arrow.start.x, arrow.end.y - arrow.start.y, arrow.end.z - arrow.start.z
    )
    length = (span.x**2 + span.y**2 + span.z**2) ** 0.5
    back = _plus(arrow.end, axes[arrow.axis], -HEAD_RATIO * length)
    barbs = [
        (arrow.end, _plus(back, axes[other], sign * HEAD_RATIO * length / 2))
        for other in range(3)
        if other != arrow.axis
        for sign in (1.0, -1.0)
    ]
    return ((arrow.start, arrow.end), *barbs)


def _handle_tip(layout: Layout, handle: Handle, point: Vec3) -> Vec3:
    """Bout de la tige de la poignée : à la longueur de la tige, vers l'extérieur de la pièce."""
    axes = (layout.frame.x, layout.frame.y, layout.frame.z)
    return _plus(point, axes[handle.axis], layout.handle_mm if handle.at_end else -layout.handle_mm)


def _handle_stem(layout: Layout, handle: Handle, point: Vec3) -> tuple[tuple[Vec3, ...], ...]:
    """Tige de la poignée : de ``point`` (milieu de la face) au centre du cube."""
    return ((point, _handle_tip(layout, handle, point)),)


def _handle_cube(layout: Layout, handle: Handle, point: Vec3) -> tuple[tuple[Vec3, ...], ...]:
    """Six faces du cube plein au bout de la tige, alignées sur les axes de la pièce ; son côté
    est proportionnel à la tige, donc constant à l'écran comme les flèches."""
    center = _handle_tip(layout, handle, point)
    axes = (layout.frame.x, layout.frame.y, layout.frame.z)
    half = CUBE_RATIO * layout.handle_mm
    faces = []
    for axis in range(3):
        first, second = (axes[i] for i in range(3) if i != axis)
        for sign in (1.0, -1.0):
            middle = _plus(center, axes[axis], sign * half)
            faces.append(
                tuple(
                    _plus(_plus(middle, first, a * half), second, b * half)
                    for a, b in ((-1.0, -1.0), (1.0, -1.0), (1.0, 1.0), (-1.0, 1.0))
                )
            )
    return tuple(faces)


def guide_outline(guide: Guide) -> tuple[Vec3, ...]:
    """Contour du guide dans le repère de la pièce : rectangle fermé (plan), segment (droite) ou
    un point (sommet)."""
    box = guide.extent
    if guide.kind is GuideKind.POINT:
        return (box.min,)
    if guide.kind is GuideKind.LINE:
        return (box.min, box.max)
    first, second = (i for i in range(3) if i != guide.axis)
    corners = []
    for a, b in ((0, 0), (1, 0), (1, 1), (0, 1), (0, 0)):
        values = [box.lo(i) for i in range(3)]
        values[first] = (box.lo(first), box.hi(first))[a]
        values[second] = (box.lo(second), box.hi(second))[b]
        corners.append(Vec3.of(values))
    return tuple(corners)


def build_drawing(
    layout: Layout,
    hover: str | None = None,
    guides: Sequence[Guide] = (),
    guides_frame: Frame | None = None,
) -> Drawing:
    """Dessin des flèches (couleur de leur axe), des poignées (tige dans l'axe de la cote, cube
    plein au bout et point de saisie au pied), de la cible survolée en surbrillance et des
    ``guides`` aimantés, portés dans le repère global.

    Les guides sont lus dans le repère de la pièce **au début du glissement** : ``guides_frame``
    est ce repère de départ (celui de ``layout`` s'il est absent). La pièce bouge pendant le
    glissement, pas les guides : les porter dans le repère courant les décalerait de son
    déplacement."""
    strokes = []
    for arrow in layout.arrows:
        hot = hover == arrow_key(arrow.axis)
        color = HOVER_COLOR if hot else AXIS_COLORS[arrow.axis]
        strokes.append(Stroke(color, 4.0 if hot else 2.0, _arrow_lines(arrow, layout.frame)))
    dots = []
    solids = []
    for handle, point in layout.handles:
        hot = hover == handle_key(handle)
        color = HOVER_COLOR if hot else HANDLE_COLOR
        strokes.append(Stroke(color, 4.0 if hot else 3.0, _handle_stem(layout, handle, point)))
        solids.append(Solid(color, _handle_cube(layout, handle, point)))
        dots.append(Dots(color, 7.0, (point,)))
    to_global = (guides_frame or layout.frame).to_transform()
    for guide in guides:
        outline = tuple(to_global.apply(p) for p in guide_outline(guide))
        if guide.kind is GuideKind.POINT:
            dots.append(Dots(GUIDE_COLOR, 12.0, outline))
        else:
            strokes.append(Stroke(GUIDE_COLOR, 3.0, (outline,)))
    return Drawing(tuple(strokes), tuple(dots), tuple(solids))


class Throttle:
    """Cadence : au plus ``rate`` applications par seconde. :meth:`ready` dit s'il est temps
    d'appliquer (à l'instant ``now``, en secondes) et le note ; :meth:`wait` donne le délai
    restant avant la prochaine."""

    def __init__(self, rate: int = MAX_RATE) -> None:
        if rate <= 0:
            raise ValueError("Throttle.rate : valeur strictement positive attendue")
        self._interval = 1.0 / rate
        self._last: float | None = None

    def ready(self, now: float) -> bool:
        """Vrai (et l'instant est noté) si la dernière application date d'au moins un intervalle."""
        if self._last is not None and now - self._last < self._interval:
            return False
        self._last = now
        return True

    def wait(self, now: float) -> float:
        """Secondes à attendre avant la prochaine application (0 si l'on peut déjà appliquer)."""
        if self._last is None:
            return 0.0
        return max(0.0, self._interval - (now - self._last))
