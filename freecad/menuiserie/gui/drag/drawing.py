# SPDX-License-Identifier: LGPL-2.1-or-later
"""Dessin pur du glissement dans la vue 3D (SM-c) : disposition des flèches et des poignées, cibles
en pixels, dessin à poser (traits, points, étiquettes), cadence de recalcul. Le rayon de la
souris, la tolérance de l'aimant et le point des poignées sont dans ``core/magnet`` (ADR 0021,
point 2). Aucun import de FreeCAD, de Qt ni de pivy : ``view.py`` fournit les projections,
``overlay.py`` pose le dessin.

Une cote a **une étiquette** (ADR 0068, maquette K) : son nom à la couleur de son axe et sa
valeur, reliée par un trait au rond de la face tournée vers la caméra ; la face d'en face n'a
qu'un rond de la même couleur. Chaque rond porte la flèche de son axe et se tient hors du tracé
des flèches de déplacement (``handle_point``). Au survol, la face qui bouge s'allume. Une cote
impossible est grise, avec un cadenas ; elle se survole (infobulle : :func:`tooltip_html`) mais
ne se tire pas.
"""

from __future__ import annotations

import html
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from enum import Enum
from itertools import combinations, product
from typing import Final

from freecad.menuiserie.core.geometry import Box, Vec3
from freecad.menuiserie.core.magnet import (
    Arrow,
    Blocker,
    Guide,
    GuideKind,
    Handle,
    PixelTarget,
    Ray,
    arrows,
    handle_at,
    handle_point,
)
from freecad.menuiserie.core.rotation import Ring
from freecad.menuiserie.core.snap import Frame
from freecad.menuiserie.core.text import mm_text
from freecad.menuiserie.gui.drag.badge_place import (
    BADGE_H_PX,
    BADGE_REACH,
    KNOB_HOT_PX,
    Rect,
    Slot,
    badge_width_px,
    facing_ends,
    point_rect,
    screen_angle,
    segment_rects,
    spread,
)
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
    "Cues",
    "Dots",
    "Drawing",
    "Knob",
    "Label",
    "Layout",
    "Solid",
    "Stroke",
    "Throttle",
    "arrow_key",
    "build_drawing",
    "build_layout",
    "guide_outline",
    "guides_drawing",
    "handle_key",
    "is_locked_key",
    "key_at",
    "locked_blocker",
    "locked_key",
    "on_screen",
    "parse_key",
    "pixel_targets",
    "size_text",
    "target_line",
    "tooltip_html",
]

ARROW_PX: Final = 80.0  # longueur des flèches à l'écran
HEAD_RATIO: Final = 0.15  # barbes de la pointe, part de la longueur
HANDLE_RATIO: Final = 0.3  # unité de longueur des poignées, part des flèches
MAX_SIZE_CHARS: Final = 9  # cote écrite sur une étiquette : au plus 9 caractères
ARROW_CLEAR_PX: Final = 5.0  # demi-largeur d'une flèche qu'une étiquette évite (pixels)
LINK_PX: Final = 2.0  # trait de l'étiquette à sa face (pixels), survolé ensuite
LINK_HOT_PX: Final = 3.0
FACE_TRANSPARENCY: Final = 0.7  # face survolée d'une poignée, à la couleur de son axe
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


class BadgeState(Enum):
    """État d'une étiquette de poignée."""

    NORMAL = "normal"
    HOVER = "hover"
    LOCKED = "locked"
    LOCKED_HOVER = "locked-hover"

    @property
    def locked(self) -> bool:
        """Vrai pour une poignée impossible (cadenas à la place de la double flèche)."""
        return self in (BadgeState.LOCKED, BadgeState.LOCKED_HOVER)


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

    ``locked`` : poignées impossibles (poignée, centre de sa face, raison) ; ``axis_names`` :
    nom court de chaque cote, écrit sur son étiquette. Trois champs dépendent de la vue et sont
    remplis ensemble par :func:`on_screen` : ``badge_scale``, rapport de pixels de l'écran
    (étiquettes à la même taille sur un écran haute définition), ``badge_ends``, axes dont
    l'étiquette est sur la face de fin (l'autre sinon), et ``badge_reach``, recul de chaque
    étiquette écartée d'une autre (par clé ; :data:`BADGE_REACH` sinon) ; ``axis_angles``,
    direction de chaque axe à l'écran (:func:`screen_angle`), celle de la flèche de ses ronds,
    l'est aussi. Un ensemble (EN-c)
    dessine sa boîte en transparence (``shows_box``)."""

    frame: Frame
    box: Box
    arrows: tuple[Arrow, ...]
    handles: tuple[tuple[Handle, Vec3], ...]
    handle_mm: float = 0.0
    rings: tuple[Ring, ...] = ()
    shows_box: bool = False
    locked: tuple[tuple[Handle, Vec3, Blocker], ...] = ()
    axis_names: tuple[str, str, str] = ("", "", "")
    badge_scale: float = 1.0
    badge_ends: frozenset[int] = frozenset({0, 1, 2})
    badge_reach: tuple[tuple[str, float], ...] = ()
    axis_angles: tuple[float | None, float | None, float | None] = (None, None, None)


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


def _badge_center(
    layout: Layout, key: str, handle: Handle, point: Vec3, reach: float | None = None
) -> Vec3:
    """Centre de l'étiquette de la poignée ``handle`` (clé ``key``) : devant sa face
    (``point``), vers l'extérieur de la boîte, à distance constante à l'écran (``reach`` unités
    de poignée ; celle de ``layout.badge_reach`` sinon)."""
    axes = (layout.frame.x, layout.frame.y, layout.frame.z)
    if reach is None:
        reach = dict(layout.badge_reach).get(key, BADGE_REACH)
    # ``handle_mm`` vient d'une longueur en pixels physiques (ARROW_PX) ; l'image de l'étiquette
    # est agrandie du rapport de l'écran, sa distance aussi.
    length = reach * layout.handle_mm * layout.badge_scale
    return point + axes[handle.axis].scaled(length if handle.at_end else -length)


def _labelled(layout: Layout, handle: Handle) -> bool:
    """Vrai si la poignée ``handle`` porte l'étiquette de sa cote (face tournée vers la caméra) ;
    l'autre n'a qu'un rond."""
    return handle.at_end == (handle.axis in layout.badge_ends)


def _badge_size(layout: Layout, key: str, handle: Handle) -> tuple[float, float]:
    """Largeur et hauteur à l'écran (pixels de FreeCAD) de l'étiquette de ``handle``."""
    text = size_text(layout.box, handle.axis)
    _, width = badge_width_px(layout.axis_names[handle.axis], text, is_locked_key(key))
    return width * layout.badge_scale, BADGE_H_PX * layout.badge_scale


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
    text = mm_text(box.hi(axis) - box.lo(axis))
    return text if len(text) <= MAX_SIZE_CHARS else "?"


def pixel_targets(layout: Layout, project: Project) -> list[PixelTarget]:
    """Cibles saisissables en pixels, dans l'ordre qui départage une égalité : rond de la face
    de chaque poignée (étiquetées d'abord ; seul le rond de la face d'en face), flèches,
    puis étiquette de chaque cote (un segment horizontal, tolérance de sa demi-hauteur) et trait
    qui la relie à sa face. Une étiquette qui chevauche une flèche ne la cache donc pas : la plus
    proche l'emporte, la flèche à égalité.

    Les pixels sont ceux de FreeCAD (physiques : rapport de l'écran appliqué) ; l'étiquette y a
    la taille de son image (:func:`badge_width_px` fois ``layout.badge_scale``)."""
    handles = _all_handles(layout)
    # Milieu des faces étiquetées d'abord : vue de bout, les deux faces d'un axe tombent sur le
    # même pixel ; celle qui porte l'étiquette (et que le survol allume) l'emporte.
    faces = sorted(handles, key=lambda item: not _labelled(layout, item[1]))
    targets = [PixelTarget(key, project(p)) for key, _, p in faces]
    for arrow in layout.arrows:
        targets.append(PixelTarget(arrow_key(arrow.axis), project(arrow.start), project(arrow.end)))
    for key, handle, point in handles:
        if not _labelled(layout, handle):
            continue
        width, height = _badge_size(layout, key, handle)
        x, y = project(_badge_center(layout, key, handle, point))
        half_w = max(0.0, width / 2 - height / 2)
        targets.append(PixelTarget(key, (x - half_w, y), (x + half_w, y), height / 2))
        targets.append(PixelTarget(key, project(point), (x, y)))
    return targets


def key_at(
    layout: Layout, project: Project, point: tuple[float, float], *, locked: bool
) -> str | None:
    """Clé de la flèche ou de la poignée sous le pixel ``point`` parmi les cibles possibles
    (``locked`` faux) ou parmi les poignées impossibles seules (``locked`` vrai). Une poignée
    impossible ne se tire pas : elle ne prend jamais la place d'une flèche, d'une poignée ou d'un
    anneau qu'elle chevauche, on ne la cherche qu'après eux."""
    targets = [t for t in pixel_targets(layout, project) if is_locked_key(t.key) == locked]
    return handle_at(targets, point)


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
    """Étiquette d'une cote centrée sur ``position`` (taille fixe à l'écran) : ``name`` (nom
    court de la cote, sur une pastille à la couleur de l'axe ``axis``), ``text`` (sa valeur),
    ``state`` (:class:`BadgeState`) et ``scale`` (rapport de pixels de l'écran)."""

    position: Vec3
    name: str
    text: str
    state: BadgeState
    axis: int = 0
    scale: float = 1.0


@dataclass(frozen=True)
class Knob:
    """Rond d'une face de poignée, centré sur ``position`` (taille fixe à l'écran) : même
    couleur que l'étiquette de sa cote (axe ``axis``, gris si ``locked``), plus gros et avec un
    halo si ``hot``, à l'échelle ``scale`` (rapport de pixels de l'écran), avec une petite
    flèche dans la direction de l'axe à l'écran (``angle``) si la cote se tire."""

    position: Vec3
    axis: int
    locked: bool = False
    hot: bool = False
    scale: float = 1.0
    angle: float | None = None  # flèche de l'axe à l'écran (degrés) ; aucune si ``None``


@dataclass(frozen=True)
class Drawing:
    """Tout ce que l'incrustation affiche."""

    strokes: tuple[Stroke, ...] = ()
    dots: tuple[Dots, ...] = ()
    solids: tuple[Solid, ...] = ()
    labels: tuple[Label, ...] = ()
    badges: tuple[Badge, ...] = ()
    knobs: tuple[Knob, ...] = ()


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
    """Dessin des flèches (couleur de leur axe), des poignées (étiquette de cote reliée au rond
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
    solids.extend(_hover_face(layout, hover))
    knobs: list[Knob] = []
    badges = _badges(layout, hover, strokes, knobs)
    guide_strokes, dots = guides_drawing(guides, guides_frame or layout.frame)
    strokes.extend(guide_strokes)
    rings = _ring_drawing(layout, hover, sweep)
    cues = cues or Cues()
    if cues.ghost is not None:
        ghost_lines, ghost_faces = _ghost_drawing(layout, cues.ghost)
        strokes.append(ghost_lines)
        solids.append(ghost_faces)
    labels = rings.labels if cues.note is None else (*rings.labels, cues.note)
    return Drawing(
        (*strokes, *rings.strokes),
        dots,
        (*solids, *rings.solids),
        labels,
        badges,
        tuple(knobs),
    )


def _badge_state(locked: bool, hot: bool) -> BadgeState:
    if locked:
        return BadgeState.LOCKED_HOVER if hot else BadgeState.LOCKED
    return BadgeState.HOVER if hot else BadgeState.NORMAL


def _handle_color(handle: Handle, locked: bool) -> Color:
    return LOCKED_COLOR if locked else AXIS_COLORS[handle.axis]


def _badges(
    layout: Layout,
    hover: str | None,
    strokes: list[Stroke],
    knobs: list[Knob],
) -> tuple[Badge, ...]:
    """Étiquettes des cotes ; leur trait et le rond de chaque face (couleur de l'axe,
    gris si la cote est figée, plus gros survolé) sont ajoutés à ``strokes`` et ``knobs``."""
    badges = []
    for key, handle, point in _all_handles(layout):
        locked, hot = is_locked_key(key), hover == key
        color = _handle_color(handle, locked)
        angle = None if locked else layout.axis_angles[handle.axis]
        knobs.append(Knob(point, handle.axis, locked, hot, layout.badge_scale, angle))
        if not _labelled(layout, handle):
            continue
        center = _badge_center(layout, key, handle, point)
        strokes.append(Stroke(color, LINK_HOT_PX if hot else LINK_PX, ((point, center),)))
        name, text = layout.axis_names[handle.axis], size_text(layout.box, handle.axis)
        state = _badge_state(locked, hot)
        badges.append(Badge(center, name, text, state, handle.axis, layout.badge_scale))
    return tuple(badges)


def _hover_face(layout: Layout, hover: str | None) -> tuple[Solid, ...]:
    """Face qui bouge sous la poignée survolée, à la couleur de son axe (grise si figée)."""
    found = next(((k, h) for k, h, _ in _all_handles(layout) if k == hover), None)
    if found is None:
        return ()
    key, handle = found
    box, axis = layout.box, handle.axis
    level = box.hi(axis) if handle.at_end else box.lo(axis)
    u, v = (i for i in range(3) if i != axis)
    corners = []
    for cu, cv in ((0, 0), (1, 0), (1, 1), (0, 1)):
        point = Vec3(0.0, 0.0, 0.0).with_component(axis, level)
        point = point.with_component(u, (box.lo(u), box.hi(u))[cu])
        corners.append(point.with_component(v, (box.lo(v), box.hi(v))[cv]))
    to_global = layout.frame.to_transform()
    face = tuple(to_global.apply(c) for c in corners)
    color = _handle_color(handle, is_locked_key(key))
    return (Solid(color, (face,), FACE_TRANSPARENCY),)


def _axis_angles(
    layout: Layout, project: Project
) -> tuple[float | None, float | None, float | None]:
    """Direction de chaque axe à l'écran (:func:`screen_angle`), mesurée depuis le centre de la
    boîte : en perspective forte, elle peut s'écarter un peu de celle vue depuis un rond, ce que
    l'arrondi à 15° couvre."""
    box = layout.box
    center = layout.frame.to_transform().apply(Vec3.of([box.center(i) for i in range(3)]))
    origin = project(center)
    step = max(layout.handle_mm, 1e-9)
    x, y, z = (
        screen_angle(origin, project(center + axis.scaled(step)))
        for axis in (layout.frame.x, layout.frame.y, layout.frame.z)
    )
    return x, y, z


def on_screen(layout: Layout, scale: float, project: Project, view: Vec3) -> Layout:
    """``layout`` posée dans la vue : rapport de pixels ``scale`` de l'écran, direction de chaque
    axe à l'écran (flèche des ronds), étiquette de chaque cote sur la face tournée vers la caméra
    (``view`` : direction de la vue), puis étiquettes écartées l'une de l'autre, des ronds et
    des flèches à l'écran (:func:`spread`)."""
    axes = (layout.frame.x, layout.frame.y, layout.frame.z)
    angles = _axis_angles(layout, project)
    placed = replace(
        layout, badge_scale=scale, badge_ends=facing_ends(axes, view), axis_angles=angles
    )
    slots = []
    for key, handle, point in _all_handles(placed):
        if not _labelled(placed, handle):
            continue
        face = project(point)
        x, y = project(_badge_center(placed, key, handle, point, 1.0))
        width, height = _badge_size(placed, key, handle)
        slots.append(Slot(key, face, (x - face[0], y - face[1]), width, height))
    obstacles = _obstacles(placed, project, scale)
    return replace(placed, badge_reach=spread(slots, scale=scale, obstacles=obstacles))


def _obstacles(layout: Layout, project: Project, scale: float) -> list[Rect]:
    """Ce qu'une étiquette ne doit pas couvrir à l'écran : les ronds (survolés : leur plus grande
    taille) et les flèches de déplacement."""
    knob = KNOB_HOT_PX / 2 * scale
    rects = [point_rect(project(point), knob) for _, _, point in _all_handles(layout)]
    for arrow in layout.arrows:
        rects.extend(
            segment_rects(project(arrow.start), project(arrow.end), ARROW_CLEAR_PX * scale)
        )
    return rects


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
