# SPDX-License-Identifier: LGPL-2.1-or-later
"""Place des étiquettes de cote à l'écran (ADR 0068, maquette K « une étiquette par cote »).

Une seule étiquette par cote, sur la face tournée vers la caméra (:func:`facing_ends`) ; la face
d'en face n'a qu'un rond. Deux étiquettes qui se touchent à l'écran sont écartées : la seconde
recule le long de son axe, d'un pas à la fois (:func:`spread`). Calcul pur, en pixels ; aucun
import de FreeCAD, de Qt ni de pivy.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from freecad.menuiserie.core.geometry import Vec3
from freecad.menuiserie.core.vectors import dot

__all__ = [
    "BADGE_H_PX",
    "BADGE_REACH",
    "Slot",
    "badge_width_px",
    "facing_ends",
    "spread",
]

BADGE_REACH: Final = 1.9  # centre de l'étiquette : distance à la face, en unités de poignée
REACH_STEP: Final = 0.8  # recul d'une étiquette qui en touche une autre, en unités de poignée
MAX_PUSHES: Final = 6
GAP_PX: Final = 4.0  # écart minimal entre deux étiquettes (pixels logiques)
BADGE_H_PX: Final = 24.0
NAME_PAD_PX: Final = 16.0  # marges du nom (pastille colorée)
NAME_CHAR_PX: Final = 7.2  # largeur d'un caractère du nom, police de 11,5 px en gras
VALUE_PAD_PX: Final = 14.0
VALUE_CHAR_PX: Final = 8.0  # largeur d'un chiffre de la cote, police de 13 px en gras
LOCK_PX: Final = 16.0  # place du cadenas d'une cote figée


def badge_width_px(name: str, text: str, locked: bool) -> tuple[float, float]:
    """Largeur du nom (pastille colorée) et largeur totale d'une étiquette, en pixels logiques :
    la même mesure sert au dessin (``badges.py``) et à la saisie (``drawing.py``)."""
    name_w = NAME_PAD_PX + NAME_CHAR_PX * len(name)
    total = name_w + VALUE_PAD_PX + VALUE_CHAR_PX * len(text) + (LOCK_PX if locked else 0.0)
    return name_w, total


def facing_ends(axes: Sequence[Vec3], view: Vec3) -> frozenset[int]:
    """Axes dont la face de fin (côté positif) regarde la caméra ; ``view`` est la direction de
    la vue (de la caméra vers la scène). Une face vue par la tranche compte comme visible."""
    return frozenset(i for i, axis in enumerate(axes) if dot(axis, view) <= 0.0)


@dataclass(frozen=True)
class Slot:
    """Étiquette à poser : clé de sa poignée, pixel du milieu de sa face, déplacement à l'écran
    pour une unité de recul (pixels), largeur et hauteur (pixels)."""

    key: str
    face: tuple[float, float]
    step: tuple[float, float]
    width: float
    height: float

    def rect(self, reach: float) -> tuple[float, float, float, float]:
        """Rectangle (gauche, bas, droite, haut) de l'étiquette posée à ``reach`` unités."""
        x = self.face[0] + self.step[0] * reach
        y = self.face[1] + self.step[1] * reach
        return (x - self.width / 2, y - self.height / 2, x + self.width / 2, y + self.height / 2)


def _overlap(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
    return not (
        a[2] + GAP_PX <= b[0]
        or b[2] + GAP_PX <= a[0]
        or a[3] + GAP_PX <= b[1]
        or b[3] + GAP_PX <= a[1]
    )


def spread(slots: Sequence[Slot], base: float = BADGE_REACH) -> tuple[tuple[str, float], ...]:
    """Recul de chaque étiquette (clé, unités de poignée) : ``base``, plus un pas tant qu'elle
    touche une étiquette déjà posée (au plus :data:`MAX_PUSHES` pas : une étiquette vue de bout ne
    s'écarte pas en reculant)."""
    placed: list[tuple[float, float, float, float]] = []
    reaches = []
    for slot in slots:
        reach = base
        for _ in range(MAX_PUSHES):
            if not any(_overlap(slot.rect(reach), other) for other in placed):
                break
            reach += REACH_STEP
        placed.append(slot.rect(reach))
        reaches.append((slot.key, reach))
    return tuple(reaches)
