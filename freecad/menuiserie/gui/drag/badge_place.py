# SPDX-License-Identifier: LGPL-2.1-or-later
"""Place des étiquettes de cote à l'écran (ADR 0068, maquette K « une étiquette par cote »).

Une seule étiquette par cote, sur la face tournée vers la caméra (:func:`facing_ends`) ; la face
d'en face n'a qu'un rond. Une étiquette qui touche à l'écran une autre étiquette, un rond ou une
flèche recule le long de son axe, d'un pas à la fois (:func:`spread`). Calcul pur, en pixels ;
aucun import de FreeCAD, de Qt ni de pivy.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from freecad.menuiserie.core.geometry import Vec3
from freecad.menuiserie.core.vectors import dot, is_finite, norm

__all__ = [
    "BADGE_H_PX",
    "BADGE_REACH",
    "KNOB_HOT_PX",
    "KNOB_PX",
    "Rect",
    "Slot",
    "badge_width_px",
    "facing_ends",
    "point_rect",
    "screen_angle",
    "segment_rects",
    "spread",
]

BADGE_REACH: Final = 1.9  # centre de l'étiquette : distance à la face, en unités de poignée
REACH_STEP: Final = 0.8  # recul d'une étiquette qui en touche une autre, en unités de poignée
MAX_PUSHES: Final = 8
MIN_VIEW: Final = 1e-12  # direction de vue plus courte : caméra dégénérée
EDGE_ON: Final = 1e-6  # face vue par la tranche (bruit flottant compris) : comptée visible
GAP_PX: Final = 4.0  # écart minimal entre deux étiquettes (pixels logiques)
BADGE_H_PX: Final = 24.0
NAME_PAD_PX: Final = 16.0  # marges du nom (pastille colorée)
NAME_CHAR_PX: Final = 7.2  # largeur d'un caractère du nom, police de 11,5 px en gras
VALUE_PAD_PX: Final = 14.0
VALUE_CHAR_PX: Final = 8.0  # largeur d'un chiffre de la cote, police de 13 px en gras
LOCK_PX: Final = 16.0  # place du cadenas d'une cote figée
KNOB_PX: Final = 16.0  # diamètre du rond d'une face (pixels logiques), survolé ensuite
KNOB_HOT_PX: Final = 20.0
ANGLE_STEP: Final = 15.0  # flèche d'un rond : angle arrondi (degrés), peu d'images à garder
MIN_ARROW_PX: Final = 2.0  # axe plus court à l'écran : vu de bout, pas de flèche


Rect = tuple[float, float, float, float]  # gauche, bas, droite, haut (pixels)


def badge_width_px(name: str, text: str, locked: bool) -> tuple[float, float]:
    """Largeur du nom (pastille colorée) et largeur totale d'une étiquette, en pixels logiques :
    la même mesure sert au dessin (``badges.py``) et à la saisie (``drawing.py``)."""
    name_w = NAME_PAD_PX + NAME_CHAR_PX * len(name)
    total = name_w + VALUE_PAD_PX + VALUE_CHAR_PX * len(text) + (LOCK_PX if locked else 0.0)
    return name_w, total


def facing_ends(axes: Sequence[Vec3], view: Vec3) -> frozenset[int]:
    """Axes dont la face de fin (côté positif) regarde la caméra ; ``view`` est la direction de
    la vue (de la caméra vers la scène). Une face vue par la tranche compte comme visible ; une
    direction nulle ou non finie (caméra dégénérée) donne les trois faces de fin."""
    if not is_finite(view) or norm(view) < MIN_VIEW:
        return frozenset({0, 1, 2})
    scale = norm(view)
    return frozenset(i for i, axis in enumerate(axes) if dot(axis, view) <= EDGE_ON * scale)


def screen_angle(start: tuple[float, float], end: tuple[float, float]) -> float | None:
    """Angle à l'écran (degrés, sens trigonométrique, pixels de FreeCAD : y vers le haut) de la
    direction de ``start`` vers ``end``, sans sens (de 0 à 180 exclu), arrondi à
    :data:`ANGLE_STEP` ; ``None`` si elle est vue de bout ou si la projection a raté."""
    dx, dy = end[0] - start[0], end[1] - start[1]
    if not (math.isfinite(dx) and math.isfinite(dy)) or math.hypot(dx, dy) < MIN_ARROW_PX:
        return None
    angle = round(math.degrees(math.atan2(dy, dx)) / ANGLE_STEP) * ANGLE_STEP
    return angle % 180.0


@dataclass(frozen=True)
class Slot:
    """Étiquette à poser : clé de sa poignée, pixel du rond de sa face, déplacement à l'écran
    pour une unité de recul (pixels), largeur et hauteur (pixels)."""

    key: str
    face: tuple[float, float]
    step: tuple[float, float]
    width: float
    height: float

    def rect(self, reach: float) -> Rect:
        """Rectangle (gauche, bas, droite, haut) de l'étiquette posée à ``reach`` unités."""
        x = self.face[0] + self.step[0] * reach
        y = self.face[1] + self.step[1] * reach
        return (x - self.width / 2, y - self.height / 2, x + self.width / 2, y + self.height / 2)


def point_rect(point: tuple[float, float], half: float) -> Rect:
    """Carré de demi-côté ``half`` centré sur ``point``."""
    return (point[0] - half, point[1] - half, point[0] + half, point[1] + half)


def segment_rects(
    start: tuple[float, float], end: tuple[float, float], half: float
) -> tuple[Rect, ...]:
    """Carrés de demi-côté ``half`` qui couvrent le segment de ``start`` à ``end`` (un tous les
    ``half`` pixels, au plus 64) ; aucun si un bout n'est pas fini."""
    if not all(math.isfinite(v) for v in (*start, *end, half)) or half <= 0:
        return ()
    count = min(64, max(1, math.ceil(math.dist(start, end) / half)))
    return tuple(
        point_rect(
            (
                start[0] + (end[0] - start[0]) * i / count,
                start[1] + (end[1] - start[1]) * i / count,
            ),
            half,
        )
        for i in range(count + 1)
    )


def _overlap(a: Rect, b: Rect, gap: float) -> bool:
    return not (
        a[2] + gap <= b[0] or b[2] + gap <= a[0] or a[3] + gap <= b[1] or b[3] + gap <= a[1]
    )


def spread(
    slots: Sequence[Slot],
    base: float = BADGE_REACH,
    scale: float = 1.0,
    obstacles: Sequence[Rect] = (),
) -> tuple[tuple[str, float], ...]:
    """Recul de chaque étiquette (clé, unités de poignée) : ``base``, plus un pas tant qu'elle
    touche une étiquette déjà posée ou un des ``obstacles`` (ronds, flèches), à moins de
    :data:`GAP_PX` fois ``scale`` (rapport de pixels de l'écran) ; au plus :data:`MAX_PUSHES`
    pas : si rien n'est libre (étiquette vue de bout), le recul qui touche le moins."""
    gap = GAP_PX * scale
    placed: list[Rect] = [r for r in obstacles if all(math.isfinite(v) for v in r)]
    reaches = []
    for slot in slots:
        if not all(math.isfinite(v) for v in (*slot.face, *slot.step, slot.width, slot.height)):
            continue  # projection ratée : recul par défaut, jamais un NaN dans la disposition
        best, fewest = base, -1
        for push in range(MAX_PUSHES + 1):
            reach = base + push * REACH_STEP
            rect = slot.rect(reach)
            hits = sum(_overlap(rect, other, gap) for other in placed)
            if fewest < 0 or hits < fewest:
                best, fewest = reach, hits
            if hits == 0:
                break
        placed.append(slot.rect(best))
        reaches.append((slot.key, best))
    return tuple(reaches)
