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
    flèches des axes libres et poignées (poignée, centre de sa face en coordonnées globales)."""

    frame: Frame
    box: Box
    arrows: tuple[Arrow, ...]
    handles: tuple[tuple[Handle, Vec3], ...]


def _face_center(box: Box, handle: Handle) -> Vec3:
    values = [box.center(i) for i in range(3)]
    values[handle.axis] = box.hi(handle.axis) if handle.at_end else box.lo(handle.axis)
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
    return Layout(frame, box, free, handles)


def pixel_targets(layout: Layout, project: Project) -> list[PixelTarget]:
    """Cibles saisissables en pixels : poignées d'abord (elles l'emportent à égalité), flèches."""
    targets = [PixelTarget(handle_key(h), project(p)) for h, p in layout.handles]
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
class Drawing:
    """Tout ce que l'incrustation affiche."""

    strokes: tuple[Stroke, ...] = ()
    dots: tuple[Dots, ...] = ()


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
    layout: Layout, hover: str | None = None, guides: Sequence[Guide] = ()
) -> Drawing:
    """Dessin des flèches (couleur de leur axe), des poignées, de la cible survolée en surbrillance
    et des ``guides`` aimantés (repère de la pièce, portés dans le repère global)."""
    strokes = []
    for arrow in layout.arrows:
        hot = hover == arrow_key(arrow.axis)
        color = HOVER_COLOR if hot else AXIS_COLORS[arrow.axis]
        strokes.append(Stroke(color, 4.0 if hot else 2.0, _arrow_lines(arrow, layout.frame)))
    dots = [
        Dots(HOVER_COLOR if hover == handle_key(h) else HANDLE_COLOR, 11.0, (point,))
        for h, point in layout.handles
    ]
    to_global = layout.frame.to_transform()
    for guide in guides:
        outline = tuple(to_global.apply(p) for p in guide_outline(guide))
        if guide.kind is GuideKind.POINT:
            dots.append(Dots(GUIDE_COLOR, 12.0, outline))
        else:
            strokes.append(Stroke(GUIDE_COLOR, 3.0, (outline,)))
    return Drawing(tuple(strokes), tuple(dots))


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
