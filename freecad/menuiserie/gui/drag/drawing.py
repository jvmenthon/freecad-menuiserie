# SPDX-License-Identifier: LGPL-2.1-or-later
"""Dessin pur du glissement dans la vue 3D (SM-c) : disposition des flèches et des poignées, cibles
en pixels, dessin à poser (traits, points, étiquettes), cadence de recalcul. Le rayon de la
souris, la tolérance de l'aimant et le point des poignées sont dans ``core/magnet`` (ADR 0021,
point 2). Aucun import de FreeCAD, de Qt ni de pivy : ``view.py`` fournit les projections,
``overlay.py`` pose le dessin.

Une poignée est une **étiquette de cote** (ADR 0068) : pastille ↔ et valeur de la cote qu'elle
change, reliée au milieu de sa face par un trait. Une poignée impossible est dessinée grisée, avec
un cadenas ; elle se survole (infobulle : :func:`tooltip_html`) mais ne se tire pas.
"""

from __future__ import annotations

import html
import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from itertools import combinations, product
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
    handle_point,
)
from freecad.menuiserie.core.rotation import Ring
from freecad.menuiserie.core.snap import Frame
from freecad.menuiserie.gui.drag.rings import (
    RING_SEGMENTS,
    Sweep,
    angle_label,
    circle,
    ring_key,
    sector,
)

__all__ = [
    "ARROW_PX",
    "REFUSAL_COLOR",
    "Badge",
    "BadgeState",
    "Blocker",
    "Cues",
    "Dots",
    "Drawing",
    "Label",
    "Layout",
    "Solid",
    "Stroke",
    "Throttle",
    "arrow_key",
    "badge_angles",
    "build_drawing",
    "build_layout",
    "guide_outline",
    "guides_drawing",
    "handle_key",
    "is_locked_key",
    "locked_blocker",
    "locked_key",
    "parse_key",
    "pixel_targets",
    "size_text",
    "target_line",
    "tooltip_html",
]

ARROW_PX: Final = 80.0  # longueur des flèches à l'écran
HEAD_RATIO: Final = 0.15  # barbes de la pointe, part de la longueur
HANDLE_RATIO: Final = 0.3  # unité de longueur des poignées, part des flèches
BADGE_REACH: Final = 1.9  # centre de l'étiquette : distance à la face, en unités de poignée
BADGE_W_PX: Final = 66.0  # étiquette d'une poignée : largeur et hauteur à l'écran (pixels logiques)
BADGE_H_PX: Final = 24.0
MAX_SIZE_CHARS: Final = 9  # cote écrite sur une étiquette : au plus 9 caractères
ANGLE_STEP: Final = 5.0  # pas des angles des étiquettes (degrés) : images gardées, moins de dessins
MAX_RATE: Final = 30  # recalculs de la brute par seconde (poignée)
AXIS_COLORS: Final = ((0.86, 0.15, 0.15), (0.15, 0.65, 0.15), (0.2, 0.3, 0.9))  # X, Y, Z
HANDLE_COLOR: Final = (1.0, 0.55, 0.0)
LOCKED_COLOR: Final = (0.6, 0.64, 0.68)  # trait d'une poignée impossible
HOVER_COLOR: Final = (1.0, 0.85, 0.1)
GUIDE_COLOR: Final = (1.0, 0.1, 0.8)
GHOST_COLOR: Final = (0.2, 0.75, 1.0)  # fantôme de la copie par glissement
GHOST_TRANSPARENCY: Final = 0.7
SECTOR_TRANSPARENCY: Final = 0.6  # secteur parcouru par un anneau tiré
BOX_COLOR: Final = (0.3, 0.5, 0.9)  # boîte d'un ensemble sélectionné
BOX_TRANSPARENCY: Final = 0.85
REFUSAL_COLOR: Final = (0.9, 0.1, 0.1)  # cote et message d'un refus près de la souris
Color = tuple[float, float, float]
Project = Callable[[Vec3], tuple[float, float]]
Blocker = tuple[str, str, str]  # raison d'une poignée impossible : titre, explication, piste


class BadgeState:
    """État d'une étiquette de poignée."""

    NORMAL: Final = "normal"
    HOVER: Final = "hover"
    LOCKED: Final = "locked"
    LOCKED_HOVER: Final = "locked-hover"


def arrow_key(axis: int) -> str:
    """Clé de la flèche de l'axe ``axis`` (0, 1 ou 2)."""
    return f"arrow{axis}"


def handle_key(handle: Handle) -> str:
    """Clé de la poignée ``handle``."""
    return f"handle{handle.axis}{'e' if handle.at_end else 's'}"


def locked_key(handle: Handle) -> str:
    """Clé de la poignée impossible ``handle`` : survolable, jamais saisie (:func:`parse_key`
    la refuse)."""
    return f"locked{handle.axis}{'e' if handle.at_end else 's'}"


def is_locked_key(key: str) -> bool:
    """Vrai pour la clé d'une poignée impossible (:func:`locked_key`)."""
    return key.startswith("locked")


def parse_key(key: str) -> int | Handle:
    """Axe d'une flèche (``int``) ou poignée (:class:`Handle`) désignée par ``key``."""
    if key.startswith("arrow") and key[5:] in ("0", "1", "2"):
        return int(key[5:])
    if key.startswith("handle") and key[6:7] in ("0", "1", "2") and key[7:] in ("s", "e"):
        return Handle(int(key[6]), key[7] == "e")
    raise ValueError(f"clé de flèche ou de poignée inconnue : {key!r}")


@dataclass(frozen=True)
class Layout:
    """Ce qui est dessiné et saisissable sur la pièce : repère global, boîte (repère de la pièce),
    flèches des axes libres, poignées (poignée, centre de sa face en coordonnées globales),
    longueur en mm de la tige (et zone de saisie) dessinée sur chaque poignée et anneaux de
    rotation (aucun si une expression pilote le placement, D6).

    ``locked`` : poignées impossibles (poignée, centre de sa face, raison) ; ``badge_scale`` :
    rapport de pixels de l'écran (étiquettes à la même taille sur un écran haute définition) ;
    ``badge_angles`` : direction à l'écran de chaque poignée (:func:`badge_angles`, 0° si
    absente), qui oriente la double flèche de son étiquette. Un ensemble (EN-c) dessine sa boîte
    en transparence (``shows_box``)."""

    frame: Frame
    box: Box
    arrows: tuple[Arrow, ...]
    handles: tuple[tuple[Handle, Vec3], ...]
    handle_mm: float = 0.0
    rings: tuple[Ring, ...] = ()
    shows_box: bool = False
    locked: tuple[tuple[Handle, Vec3, Blocker], ...] = ()
    badge_scale: float = 1.0
    badge_angles: tuple[float, ...] = ()


def build_layout(
    frame: Frame,
    box: Box,
    size_mm: float,
    fixed_axes: frozenset[int],
    resizable_axes: frozenset[int],
    locked_sizes: Sequence[tuple[int, Blocker]] = (),
) -> Layout:
    """Flèches (hors axes pilotés par une formule), poignées (axes redimensionnables : les deux
    faces de bout) et poignées impossibles (``locked_sizes`` : axe et raison) d'une pièce de
    repère ``frame`` et de boîte ``box``."""
    free = tuple(a for a in arrows(frame, box, size_mm) if a.axis not in fixed_axes)
    to_global = frame.to_transform()
    handles = tuple(
        (handle, to_global.apply(handle_point(box, handle)))
        for axis in sorted(resizable_axes)
        for handle in (Handle(axis, False), Handle(axis, True))
    )
    locked = tuple(
        (handle, to_global.apply(handle_point(box, handle)), blocker)
        for axis, blocker in sorted(locked_sizes)
        if axis not in resizable_axes
        for handle in (Handle(axis, False), Handle(axis, True))
    )
    return Layout(frame, box, free, handles, HANDLE_RATIO * size_mm, locked=locked)


def _badge_center(layout: Layout, handle: Handle, point: Vec3) -> Vec3:
    """Centre de l'étiquette de la poignée ``handle`` : devant sa face (``point``), vers
    l'extérieur de la boîte, à distance constante à l'écran."""
    axes = (layout.frame.x, layout.frame.y, layout.frame.z)
    reach = BADGE_REACH * layout.handle_mm * layout.badge_scale
    return point + axes[handle.axis].scaled(reach if handle.at_end else -reach)


def _all_handles(layout: Layout) -> list[tuple[str, Handle, Vec3]]:
    """Clé, poignée et point de chaque poignée, possibles puis impossibles."""
    active = [(handle_key(h), h, p) for h, p in layout.handles]
    return [*active, *((locked_key(h), h, p) for h, p, _ in layout.locked)]


def locked_blocker(layout: Layout, key: str | None) -> Blocker | None:
    """Raison de la poignée impossible ``key``, ``None`` si ``key`` n'en est pas une."""
    return next((b for h, _, b in layout.locked if locked_key(h) == key), None)


def tooltip_html(blocker: Blocker) -> str:
    """Infobulle d'une poignée impossible : titre en gras, explication, piste en italique (texte
    échappé : il peut venir d'une traduction)."""
    title, detail, hint = (html.escape(part) for part in blocker)
    return f"<b>{title}</b><br>{detail}<br><i>{hint}</i>"


def size_text(box: Box, axis: int) -> str:
    """Cote de ``box`` sur ``axis``, écrite sur l'étiquette : au millimètre, au dixième sinon ;
    « ? » si elle n'est pas finie ou trop longue à écrire (document retouché)."""
    value = round(box.hi(axis) - box.lo(axis), 1)
    if not math.isfinite(value):
        return "?"
    text = f"{value:.0f}" if value == int(value) else f"{value:.1f}"
    return text if len(text) <= MAX_SIZE_CHARS else "?"


def pixel_targets(layout: Layout, project: Project) -> list[PixelTarget]:
    """Cibles saisissables en pixels : poignées d'abord (elles l'emportent à égalité), possibles
    puis impossibles, chacune par le milieu de sa face, par son étiquette (un segment horizontal,
    tolérance de la demi-hauteur) et par le trait qui les relie ; puis flèches."""
    handles = _all_handles(layout)
    targets = [PixelTarget(key, project(p)) for key, _, p in handles]
    half_h = BADGE_H_PX / 2 * layout.badge_scale
    half_w = BADGE_W_PX / 2 * layout.badge_scale - half_h
    for key, handle, point in handles:
        x, y = project(_badge_center(layout, handle, point))
        targets.append(PixelTarget(key, (x - half_w, y), (x + half_w, y), half_h))
        targets.append(PixelTarget(key, project(point), (x, y)))
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
    transparency: float = 0.0


@dataclass(frozen=True)
class Label:
    """Texte d'une couleur écrit à côté du point ``position`` (taille fixe à l'écran)."""

    color: Color
    text: str
    position: Vec3


@dataclass(frozen=True)
class Badge:
    """Étiquette d'une poignée centrée sur ``position`` (taille fixe à l'écran) : ``text`` (la
    cote), ``state`` (:class:`BadgeState`) et ``angle`` de l'axe à l'écran (degrés, sens direct,
    0 = vers la droite), qui oriente la double flèche."""

    position: Vec3
    text: str
    state: str
    angle: float = 0.0
    scale: float = 1.0


@dataclass(frozen=True)
class Drawing:
    """Tout ce que l'incrustation affiche."""

    strokes: tuple[Stroke, ...] = ()
    dots: tuple[Dots, ...] = ()
    solids: tuple[Solid, ...] = ()
    labels: tuple[Label, ...] = ()
    badges: tuple[Badge, ...] = ()


def _arrow_lines(arrow: Arrow, frame: Frame) -> tuple[tuple[Vec3, ...], ...]:
    """Tige et quatre barbes de la pointe (le long des deux autres axes de la pièce)."""
    axes = (frame.x, frame.y, frame.z)
    span = arrow.end - arrow.start
    length = (span.x**2 + span.y**2 + span.z**2) ** 0.5
    back = arrow.end + axes[arrow.axis].scaled(-HEAD_RATIO * length)
    barbs = [
        (arrow.end, back + axes[other].scaled(sign * HEAD_RATIO * length / 2))
        for other in range(3)
        if other != arrow.axis
        for sign in (1.0, -1.0)
    ]
    return ((arrow.start, arrow.end), *barbs)


def _corner_key(bits: tuple[int, int], axis: int, side: int) -> tuple[int, ...]:
    """Clé du coin : ``bits`` complétés par ``side`` à la place de l'axe ``axis``."""
    key = list(bits)
    key.insert(axis, side)
    return tuple(key)


def _box_drawing(layout: Layout) -> tuple[Stroke, Solid]:
    """Boîte de l'ensemble : six faces en transparence et douze arêtes, en coordonnées globales."""
    to_global = layout.frame.to_transform()
    box = layout.box
    corners = {
        bits: to_global.apply(Vec3.of([(box.lo(i), box.hi(i))[bits[i]] for i in range(3)]))
        for bits in product((0, 1), repeat=3)
    }
    edges = tuple(
        (corners[a], corners[b])
        for a, b in combinations(corners, 2)
        if sum(x != y for x, y in zip(a, b, strict=True)) == 1
    )
    faces = tuple(
        tuple(corners[_corner_key(bits, axis, side)] for bits in ((0, 0), (1, 0), (1, 1), (0, 1)))
        for axis in range(3)
        for side in (0, 1)
    )
    return Stroke(BOX_COLOR, 1.5, edges), Solid(BOX_COLOR, faces, BOX_TRANSPARENCY)


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


def _ring_drawing(layout: Layout, hover: str | None, sweep: Sweep | None) -> Drawing:
    """Anneaux (couleur de leur axe, épaissis et en surbrillance sous la souris ou tirés) et, durant
    un geste, secteur parcouru en transparence et angle écrit près de la souris."""
    strokes = []
    for ring in layout.rings:
        hot = hover == ring_key(ring.axis)
        color = HOVER_COLOR if hot else AXIS_COLORS[ring.axis]
        strokes.append(Stroke(color, 5.0 if hot else 2.5, (circle(ring, RING_SEGMENTS),)))
    if sweep is None:
        return Drawing(strokes=tuple(strokes))
    color = AXIS_COLORS[sweep.ring.axis]
    faces = sector(sweep)
    solids = (Solid(color, faces, SECTOR_TRANSPARENCY),) if faces else ()
    return Drawing(
        tuple(strokes),
        solids=solids,
        labels=(Label(color, angle_label(sweep.angle), sweep.anchor),),
    )


def _ghost_drawing(layout: Layout, offset: Vec3) -> tuple[Stroke, Solid]:
    """Boîte de la pièce décalée de ``offset`` (repère de la pièce) : contour et faces
    translucides, portés dans le repère global."""
    to_global = layout.frame.to_transform()
    box = layout.box

    def corner(index: int) -> Vec3:
        values = [
            (box.lo, box.hi)[(index >> axis) & 1](axis) + offset.component(axis)
            for axis in range(3)
        ]
        return to_global.apply(Vec3.of(values))

    corners = [corner(index) for index in range(8)]
    edges = tuple(
        (corners[a], corners[b])
        for a in range(8)
        for b in range(a + 1, 8)
        if bin(a ^ b).count("1") == 1
    )
    faces = tuple(
        tuple(corners[i] for i in ring)
        for ring in (
            (0, 1, 3, 2),
            (4, 5, 7, 6),
            (0, 1, 5, 4),
            (2, 3, 7, 6),
            (0, 2, 6, 4),
            (1, 3, 7, 5),
        )
    )
    return Stroke(GHOST_COLOR, 2.5, edges), Solid(GHOST_COLOR, faces, GHOST_TRANSPARENCY)


def guides_drawing(
    guides: Sequence[Guide], frame: Frame
) -> tuple[tuple[Stroke, ...], tuple[Dots, ...]]:
    """Contours des ``guides`` (lus dans ``frame``) portés dans le repère global, en magenta :
    gros points pour un sommet, trait pour une droite ou un plan (aimant et coplanarité)."""
    to_global = frame.to_transform()
    strokes = []
    dots = []
    for guide in guides:
        outline = tuple(to_global.apply(p) for p in guide_outline(guide))
        if guide.kind is GuideKind.POINT:
            dots.append(Dots(GUIDE_COLOR, 12.0, outline))
        else:
            strokes.append(Stroke(GUIDE_COLOR, 3.0, (outline,)))
    return tuple(strokes), tuple(dots)


@dataclass(frozen=True)
class Cues:
    """Indications d'un geste à dessiner en plus de la disposition : ``ghost``, décalage du
    fantôme de la copie (repère de la pièce), et ``note``, texte près de la souris."""

    ghost: Vec3 | None = None
    note: Label | None = None


def build_drawing(
    layout: Layout,
    hover: str | None = None,
    guides: Sequence[Guide] = (),
    guides_frame: Frame | None = None,
    sweep: Sweep | None = None,
    cues: Cues | None = None,
) -> Drawing:
    """Dessin des flèches (couleur de leur axe), des poignées (étiquette de cote reliée au milieu
    de sa face ; grisée avec un cadenas si la cote ne se tire pas), des anneaux de rotation (et,
    pendant un geste, de ``sweep``), de la cible survolée en surbrillance et des ``guides``
    aimantés, portés dans le repère global.

    Les guides sont lus dans le repère de la pièce **au début du glissement** : ``guides_frame``
    est ce repère de départ (celui de ``layout`` s'il est absent). La pièce bouge pendant le
    glissement, pas les guides : les porter dans le repère courant les décalerait de son
    déplacement. ``cues`` : le fantôme de la copie par glissement (``ghost``, décalage dans le
    repère de la pièce, sa boîte translucide) et la ``note`` (cote et message de refus) écrite près
    de la souris.

    Pour un ensemble : boîte en transparence."""
    strokes = []
    solids = []
    if layout.shows_box:
        edges, faces = _box_drawing(layout)
        strokes.append(edges)
        solids.append(faces)
    for arrow in layout.arrows:
        hot = hover == arrow_key(arrow.axis)
        color = HOVER_COLOR if hot else AXIS_COLORS[arrow.axis]
        strokes.append(Stroke(color, 4.0 if hot else 2.0, _arrow_lines(arrow, layout.frame)))
    dots: list[Dots] = []
    badges = _badges(layout, hover, strokes, dots)
    guide_strokes, guide_dots = guides_drawing(guides, guides_frame or layout.frame)
    strokes.extend(guide_strokes)
    dots.extend(guide_dots)
    rings = _ring_drawing(layout, hover, sweep)
    cues = cues or Cues()
    if cues.ghost is not None:
        ghost_lines, ghost_faces = _ghost_drawing(layout, cues.ghost)
        strokes.append(ghost_lines)
        solids.append(ghost_faces)
    labels = rings.labels if cues.note is None else (*rings.labels, cues.note)
    return Drawing(
        (*strokes, *rings.strokes), tuple(dots), (*solids, *rings.solids), labels, badges
    )


def _badge_state(locked: bool, hot: bool) -> str:
    if locked:
        return BadgeState.LOCKED_HOVER if hot else BadgeState.LOCKED
    return BadgeState.HOVER if hot else BadgeState.NORMAL


def _badges(
    layout: Layout,
    hover: str | None,
    strokes: list[Stroke],
    dots: list[Dots],
) -> tuple[Badge, ...]:
    """Étiquettes des poignées ; leur trait et le point du milieu de leur face sont ajoutés à
    ``strokes`` et ``dots``."""
    badges = []
    for index, (key, handle, point) in enumerate(_all_handles(layout)):
        locked, hot = is_locked_key(key), hover == key
        color = LOCKED_COLOR if locked else (HOVER_COLOR if hot else HANDLE_COLOR)
        center = _badge_center(layout, handle, point)
        strokes.append(Stroke(color, 2.0, ((point, center),)))
        dots.append(Dots(color, 6.0, (point,)))
        angles = layout.badge_angles
        angle = angles[index] if index < len(angles) else 0.0
        state = _badge_state(locked, hot)
        text = size_text(layout.box, handle.axis)
        badges.append(Badge(center, text, state, angle, layout.badge_scale))
    return tuple(badges)


def badge_angles(layout: Layout, project: Project) -> tuple[float, ...]:
    """Direction à l'écran (degrés, sens direct, arrondie à :data:`ANGLE_STEP`) de l'axe de
    chaque poignée, dans l'ordre des étiquettes ; un axe vu de bout donne 0°."""
    angles = []
    for _, handle, point in _all_handles(layout):
        (x0, y0), (x1, y1) = project(point), project(_badge_center(layout, handle, point))
        if math.hypot(x1 - x0, y1 - y0) < 1.0:
            angles.append(0.0)
            continue
        angle = math.degrees(math.atan2(y1 - y0, x1 - x0))  # pixels de FreeCAD : y vers le haut
        angles.append((round(angle / ANGLE_STEP) * ANGLE_STEP) % 360.0)
    return tuple(angles)


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
