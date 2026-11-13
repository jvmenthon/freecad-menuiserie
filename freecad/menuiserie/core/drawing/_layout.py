# SPDX-License-Identifier: LGPL-2.1-or-later
"""Mise en page du plan de l'ouvrage : échelle normalisée et place des vues sur la feuille.

Disposition européenne (premier dièdre) : dessus sous la face, vue de gauche à droite de la face,
perspective à droite. Le groupe de vues est centré dans la place libre au-dessus du cartouche, qui
occupe le coin bas droit. Toutes les
longueurs sont en millimètres ; l'origine de la feuille est son coin bas gauche et la place d'une
vue est celle de son centre, comme dans TechDraw.
"""

from __future__ import annotations

import math
import textwrap
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Final

from freecad.menuiserie.core.drawing._machining import CONTINUATION
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP, TemplatedError

# Formats ISO 216, grand côté puis petit côté.
PAGE_FORMATS: Final = {
    "A4": (297.0, 210.0),
    "A3": (420.0, 297.0),
    "A2": (594.0, 420.0),
    "A1": (841.0, 594.0),
    "A0": (1189.0, 841.0),
}
DEFAULT_FORMAT: Final = "A3"
# Échelles ISO 5455, de la plus grande à la plus petite.
SCALES: Final = (5.0, 2.0, 1.0, 0.5, 0.2, 0.1, 0.05, 0.02, 0.01)
MARGIN_MM: Final = 20.0  # bord de la feuille, cadre du gabarit compris
GAP_MM: Final = 30.0  # entre deux vues : la place des cotes
TITLE_BLOCK_MM: Final = (190.0, 65.0)  # cartouche ISO 7200 (180 mm de large) et sa marge
MAX_SIZE_MM: Final = 1_000_000.0  # un kilomètre : au-delà, la saisie est une erreur
# Encombrement de la projection isométrique (direction 1, -1, 1) d'une boîte l x p x h :
# largeur (l + p) / √2, hauteur (l + p) / √6 + h * √(2/3).
_ISO_ACROSS: Final = 1.0 / math.sqrt(2.0)
_ISO_RISE: Final = 1.0 / math.sqrt(6.0)
_ISO_UP: Final = math.sqrt(2.0 / 3.0)

_BAD_SIZE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Plan impossible : l'ouvrage à dessiner n'a pas de volume."
)
_BAD_FORMAT: Final = QT_TRANSLATE_NOOP("Menuiserie", "Format de page inconnu : {format}.")


class Orientation(Enum):
    """Sens de la feuille."""

    LANDSCAPE = "Landscape"
    PORTRAIT = "Portrait"


@dataclass(frozen=True)
class PageSize:
    """Feuille : largeur et hauteur en millimètres."""

    width: float
    height: float


@dataclass(frozen=True)
class Spot:
    """Centre d'une vue sur la feuille."""

    x: float
    y: float


@dataclass(frozen=True)
class OverallLayout:
    """Échelle commune et place des quatre vues du plan de l'ouvrage. ``top`` (sous la face) et
    ``side`` (à droite) reçoivent la coupe horizontale et la coupe verticale, de même encombrement
    que les vues de dessus et de gauche. ``fits`` est faux quand même la plus petite échelle
    déborde de la feuille."""

    scale: float
    front: Spot
    top: Spot
    side: Spot
    iso: Spot
    fits: bool


def page_size(fmt: str, orientation: Orientation = Orientation.LANDSCAPE) -> PageSize:
    """Feuille du format ``fmt`` (« A3 »…) dans le sens ``orientation``."""
    try:
        long_side, short_side = PAGE_FORMATS[fmt.strip().upper()]
    except KeyError:
        raise TemplatedError(_BAD_FORMAT, {"format": fmt}) from None
    if orientation is Orientation.PORTRAIT:
        return PageSize(short_side, long_side)
    return PageSize(long_side, short_side)


def scale_text(scale: float) -> str:
    """Échelle écrite comme au cartouche : « 1 : 10 », « 2 : 1 »."""
    if scale >= 1.0:
        return f"{scale:g} : 1"
    return f"1 : {1.0 / scale:g}"


def _extent(sizes: tuple[float, float, float], scale: float) -> tuple[float, float, float]:
    """Largeur et hauteur de la face, profondeur, à l'échelle."""
    width, depth, height = (value * scale for value in sizes)
    return width, height, depth


def _iso(width: float, height: float, depth: float, iso: bool) -> tuple[float, float, float]:
    """Largeur et hauteur de la perspective et place qu'elle prend à droite (écart compris) ;
    rien sans perspective."""
    if not iso:
        return 0.0, 0.0, 0.0
    iso_width = (width + depth) * _ISO_ACROSS
    return iso_width, (width + depth) * _ISO_RISE + height * _ISO_UP, GAP_MM + iso_width


def _fits(
    sizes: tuple[float, float, float],
    scale: float,
    page: PageSize,
    reserve: float | None = None,
    iso: bool = True,
) -> bool:
    width, height, depth = _extent(sizes, scale)
    _, iso_height, iso_room = _iso(width, height, depth, iso)
    used_width = 2 * MARGIN_MM + width + GAP_MM + depth + iso_room
    block_width, block_height = TITLE_BLOCK_MM
    block_height += reserve or 0.0
    # Le dessus, sous la face, ne monte au-dessus du cartouche que s'il passe dessous en largeur.
    under_block = reserve is not None or MARGIN_MM + width > page.width - block_width
    bottom = block_height if under_block else MARGIN_MM
    used_height = MARGIN_MM + max(height + GAP_MM + depth, iso_height) + bottom
    # La vue de gauche et la perspective restent au-dessus du cartouche.
    right_height = MARGIN_MM + max(height, iso_height) + block_height
    return used_width <= page.width and max(used_height, right_height) <= page.height


def overall_layout(
    width: float,
    depth: float,
    height: float,
    page: PageSize,
    *,
    reserve: float | None = None,
    iso: bool = True,
) -> OverallLayout:
    """Mise en page du plan d'un ouvrage de ``width`` x ``depth`` x ``height`` (X, Y, Z) sur
    ``page`` : la plus grande échelle normalisée où les quatre vues et leurs cotes tiennent.
    ``reserve`` (plan de pièce, voir :func:`notes_band`) : les vues restent toutes au-dessus du
    cartouche et de ``reserve`` millimètres de plus, pour laisser libre la place du tableau des
    usinages. ``iso`` faux : pas de perspective (sa place ``iso`` est alors à droite de la vue
    de gauche, sans largeur). ``TemplatedError`` pour une cote nulle, négative, non finie ou
    démesurée."""
    sizes = (width, depth, height)
    if not all(math.isfinite(value) and 0.0 < value <= MAX_SIZE_MM for value in sizes):
        raise TemplatedError(_BAD_SIZE, {})
    scale = next((value for value in SCALES if _fits(sizes, value, page, reserve, iso)), None)
    fits = scale is not None
    scale = SCALES[-1] if scale is None else scale
    face_width, face_height, face_depth = _extent(sizes, scale)
    iso_width, iso_height, iso_room = _iso(face_width, face_height, face_depth, iso)
    left, top_y = _group_origin(
        (face_width + GAP_MM + face_depth + iso_room, face_width),
        (max(face_height + GAP_MM + face_depth, iso_height), max(face_height, iso_height)),
        page,
        reserve or 0.0,
    )
    front = Spot(left + face_width / 2, top_y - face_height / 2)
    top = Spot(front.x, top_y - face_height - GAP_MM - face_depth / 2)
    side_x = left + face_width + GAP_MM + face_depth / 2
    side = Spot(side_x, front.y)
    iso_spot = Spot(side_x + face_depth / 2 + GAP_MM + iso_width / 2, top_y - iso_height / 2)
    return OverallLayout(scale, front, top, side, iso_spot, fits)


def _group_origin(
    widths: tuple[float, float],
    heights: tuple[float, float],
    page: PageSize,
    reserve: float = 0.0,
) -> tuple[float, float]:
    """Coin haut gauche du groupe de vues, centré dans la place libre au-dessus du cartouche.

    ``widths`` : largeur du groupe et de la colonne de gauche (face et dessus) ; ``heights`` :
    hauteur du groupe et de la rangée du haut (face, vue de gauche, perspective). Quand le groupe
    est trop haut pour passer au-dessus du cartouche, il reste calé en haut et la colonne de
    gauche ne glisse pas sous le cartouche."""
    group_width, left_width = widths
    group_height, row_height = heights
    block_width, block_height = TITLE_BLOCK_MM
    free_top = page.height - MARGIN_MM
    free_height = free_top - block_height - reserve
    if group_height <= free_height:
        top_y = free_top - (free_height - group_height) / 2
        right_limit = page.width - MARGIN_MM
    else:
        top_y = free_top - max(0.0, (free_height - row_height) / 2)
        right_limit = page.width - block_width
    left = MARGIN_MM + max(0.0, (page.width - 2 * MARGIN_MM - group_width) / 2)
    if group_height > free_height:
        left = min(left, max(MARGIN_MM, right_limit - left_width))
    return left, top_y


NOTES_MIN_WIDTH_MM: Final = 120.0  # bande à gauche du cartouche assez large pour le tableau
NOTES_HEIGHT_MM: Final = 50.0  # tableau posé au-dessus du cartouche, faute de place à sa gauche


def notes_band(page: PageSize) -> tuple[Spot, float]:
    """Place du tableau des usinages d'un plan de pièce : (centre, réserve à passer à
    :func:`overall_layout`). La bande à gauche du cartouche quand elle est assez large (réserve
    nulle), sinon une bande de toute la largeur au-dessus du cartouche."""
    block_width, block_height = TITLE_BLOCK_MM
    left_width = page.width - block_width - MARGIN_MM
    if left_width >= NOTES_MIN_WIDTH_MM:
        return Spot((MARGIN_MM + page.width - block_width) / 2, (MARGIN_MM + block_height) / 2), 0.0
    return Spot(page.width / 2, block_height + NOTES_HEIGHT_MM / 2), NOTES_HEIGHT_MM


CHAR_WIDTH_RATIO: Final = 0.6  # largeur moyenne d'un caractère rapportée à sa hauteur


def notes_layout(page: PageSize, lines: Sequence[str], size: float) -> tuple[list[str], Spot]:
    """Lignes du tableau des usinages coupées à la largeur de sa bande (suite en retrait) et
    centre du bloc de texte, calé sur le bord gauche de la bande : TechDraw place un texte par
    son centre. ``size`` : hauteur du texte en mm."""
    spot, reserve = notes_band(page)
    if reserve == 0:
        band_width = page.width - TITLE_BLOCK_MM[0] - MARGIN_MM - GAP_MM / 3
    else:
        band_width = page.width - 2 * MARGIN_MM
    char = CHAR_WIDTH_RATIO * size
    columns = max(20, int(band_width / char))
    wrapped = [
        piece
        for line in lines
        for piece in (textwrap.wrap(line, columns, subsequent_indent=CONTINUATION) or [""])
    ]
    block = max((len(line) for line in wrapped), default=0) * char
    left = spot.x - band_width / 2
    return wrapped, Spot(left + block / 2, spot.y)


EXPLODE_FACTOR: Final = 0.6  # écartement d'une pièce : part de sa distance au centre de l'ouvrage


def exploded_offset(center: Sequence[float], part_center: Sequence[float]) -> tuple[float, ...]:
    """Déplacement d'une pièce dans la vue éclatée : elle s'éloigne du centre de l'ouvrage de
    ``EXPLODE_FACTOR`` fois sa distance à ce centre, sur chaque axe."""
    return tuple(EXPLODE_FACTOR * (p - c) for p, c in zip(part_center, center, strict=True))


def single_view_layout(
    width: float, depth: float, height: float, page: PageSize
) -> tuple[float, Spot, bool]:
    """Échelle normalisée et centre d'une seule perspective (vue éclatée) d'un volume de
    ``width`` x ``depth`` x ``height``, la plus grande possible au-dessus du cartouche, et si
    elle tient (faux : la plus petite échelle, qui déborde encore)."""
    sizes = (width, depth, height)
    if not all(math.isfinite(value) and 0.0 < value <= MAX_SIZE_MM for value in sizes):
        raise TemplatedError(_BAD_SIZE, {})
    free_width = page.width - 2 * MARGIN_MM
    free_height = page.height - MARGIN_MM - TITLE_BLOCK_MM[1]

    def fits(scale: float) -> bool:
        iso_width, iso_height, _ = _iso(width * scale, height * scale, depth * scale, True)
        return iso_width <= free_width and iso_height <= free_height

    scale = next((value for value in SCALES if fits(value)), None)
    spot = Spot(page.width / 2, TITLE_BLOCK_MM[1] + free_height / 2)
    return (SCALES[-1], spot, False) if scale is None else (scale, spot, True)


MIN_CORNER_MM: Final = 30.0  # perspective d'une pièce : place minimale, sinon pas de perspective


def corner_iso_layout(
    sizes: tuple[float, float, float],
    layout: OverallLayout,
    page: PageSize,
    reserve: float = 0.0,
) -> tuple[float, Spot] | None:
    """Perspective d'une pièce de ``sizes`` (largeur, profondeur, hauteur, comme
    :func:`overall_layout`) dans le coin libre à droite de sa vue de gauche, au-dessus du
    cartouche et de ``reserve`` : échelle normalisée (au plus celle de ``layout``) et centre ;
    ``None`` s'il n'y a pas la place. Les vues cotées gardent ainsi leur grande échelle."""
    width, depth, height = sizes
    left = layout.side.x + depth * layout.scale / 2 + GAP_MM
    free_width = page.width - MARGIN_MM - left
    bottom = TITLE_BLOCK_MM[1] + reserve + GAP_MM
    free_height = page.height - MARGIN_MM - bottom
    if min(free_width, free_height) < MIN_CORNER_MM:
        return None

    def fits(scale: float) -> bool:
        iso_width, iso_height, _ = _iso(width * scale, height * scale, depth * scale, True)
        return iso_width <= free_width and iso_height <= free_height

    scale = next((value for value in SCALES if value <= layout.scale and fits(value)), None)
    if scale is None:
        return None
    return scale, Spot(left + free_width / 2, bottom + free_height / 2)
