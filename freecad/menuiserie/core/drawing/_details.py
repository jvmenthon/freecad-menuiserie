# SPDX-License-Identifier: LGPL-2.1-or-later
"""Cotes de détail et angles de la face du plan de l'ouvrage (retour de jv du 2026-11-13).

Sous les cotes hors tout, une chaîne de cotes donne les positions où commence ou finit chaque
pièce, en largeur et en hauteur : épaisseur d'un plateau, débord d'une pièce, étendue d'une
pièce en biais. Un point dont la cote ne trouve pas de place lisible est retiré. Une pièce en
biais sur la face porte son angle avec l'horizontale.
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Callable, Iterable, Sequence
from typing import Final

__all__ = ["ChainLabel", "chain_labels", "chain_segments", "slant_angle", "text_width_mm"]

MIN_SLANT_DEG: Final = 0.5  # en deçà (ou au-delà de 90 - ce seuil), la pièce est d'équerre
_SAME_MM: Final = 0.05


def chain_segments(points: Iterable[float], min_gap: float) -> list[tuple[float, float]]:
    """Segments successifs d'une chaîne de cotes passant par ``points`` (mm réels) : points triés,
    ceux à moins de ``min_gap`` du précédent gardé fusionnés (le dernier point, l'extrémité, est
    toujours gardé), valeurs non finies ignorées. Vide s'il n'y a qu'un segment : la cote hors
    tout le donne déjà."""
    ordered = sorted({round(value, 3) for value in points if math.isfinite(value)})
    if len(ordered) < 2:
        return []
    gap = max(min_gap, _SAME_MM)  # deux points plus proches que _SAME_MM sont confondus
    kept = [ordered[0]]
    for value in ordered[1:-1]:
        if value - kept[-1] >= gap and ordered[-1] - value >= gap:
            kept.append(value)
    kept.append(ordered[-1])
    segments = [(a, b) for a, b in itertools.pairwise(kept) if b - a > _SAME_MM]
    return segments if len(segments) > 1 else []


ChainLabel = tuple[float, float, float]  # début, fin, milieu du texte (mm de la feuille)
_LABEL_GAP_MM: Final = 1.5
# Largeur d'un chiffre des cotes de TechDraw (police osifont) rapportée à sa hauteur, mesurée
# sur les captures : plus large que le texte courant (CHAR_WIDTH_RATIO).
DIMENSION_CHAR_RATIO: Final = 0.85  # entre deux textes de cote voisins


def text_width_mm(value: float, font: float) -> float:
    """Largeur sur la feuille du texte d'une cote de ``value`` mm écrite par TechDraw (deux
    décimales au plus, zéros de fin retirés) en caractères de ``font`` mm."""
    chars = len(f"{value:.2f}".rstrip("0").rstrip("."))
    return chars * DIMENSION_CHAR_RATIO * font


def chain_labels(
    segments: Sequence[tuple[float, float]], width: Callable[[float, float], float]
) -> list[ChainLabel]:
    """Cotes lisibles d'une chaîne de ``segments`` (mm de la feuille, bout à bout) : chaque
    texte (``width(début, fin)`` de large) se place dans son segment, sinon juste avant (juste
    après pour la dernière cote, au bout de la chaîne), sans chevaucher le précédent. Un point
    dont la cote ne trouve pas de place est retiré (les deux segments voisins n'en font qu'un).
    Vide s'il ne reste qu'une cote : la cote hors tout la donne déjà."""
    if len(segments) < 2:
        return []
    first, last = segments[0][0], segments[-1][1]
    labels: list[ChainLabel] = []
    for _, end in segments:
        while True:
            start = labels[-1][1] if labels else first
            right = labels[-1][2] + width(*labels[-1][:2]) / 2 if labels else -math.inf
            spot = _label_spot((start, end), width(start, end), right, end == last)
            if spot is not None or end != last or not labels:
                break
            labels.pop()  # la dernière cote ne tient pas : le point précédent est retiré
        if spot is None and end == last:
            spot = end + _LABEL_GAP_MM + width(start, end) / 2
        if spot is not None:
            labels.append((start, end, spot))
    return labels if len(labels) > 1 else []


def _label_spot(
    segment: tuple[float, float], text: float, right: float, at_end: bool
) -> float | None:
    """Milieu du texte d'une cote sur ``segment`` qui ne déborde pas sur ``right`` (fin du
    texte précédent) : dans le segment, sinon juste avant ou juste après (après d'abord au bout
    de la chaîne) ; ``None`` s'il n'y a pas de place."""
    low, high = segment
    before = low - _LABEL_GAP_MM - text / 2
    after = high + _LABEL_GAP_MM + text / 2
    inside = (low + high) / 2 if high - low >= text + _LABEL_GAP_MM else None
    for middle in (inside, *((after, before) if at_end else (before, after))):
        if middle is not None and middle - text / 2 >= right + _LABEL_GAP_MM:
            return middle
    return None


def slant_angle(horizontal: float, vertical: float) -> float | None:
    """Angle (degrés, de 0 à 90) avec l'horizontale de la feuille d'une direction vue de
    composantes ``horizontal`` et ``vertical`` ; ``None`` si elle est d'équerre (horizontale,
    verticale) ou perpendiculaire à la feuille."""
    if math.hypot(horizontal, vertical) < 1e-6:
        return None
    angle = math.degrees(math.atan2(abs(vertical), abs(horizontal)))
    if angle < MIN_SLANT_DEG or angle > 90.0 - MIN_SLANT_DEG:
        return None
    return angle
