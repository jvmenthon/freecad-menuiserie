# SPDX-License-Identifier: LGPL-2.1-or-later
"""Répartition régulière de pièces rapportées (tourillons, mortaises) le long d'un contact."""

from __future__ import annotations

import math
from typing import Final

from freecad.menuiserie.core.joints._base import MAX_COUNT

__all__ = ["MAX_DOWEL_COUNT", "positions", "spaced_count", "spacing_of"]

MAX_DOWEL_COUNT: Final = MAX_COUNT  # nombre calculé, 50 au plus
_MARGIN: Final = 1e-9  # arrondi de la division


def spaced_count(span: float, ceiling: float, min_gap: float) -> int:
    """Nombre de pièces réparties sur ``span`` (du premier au dernier centre) : au moins 2,
    entraxe de ``ceiling`` au plus, ``MAX_DOWEL_COUNT`` au plus (l'entraxe dépasse alors
    ``ceiling`` sur un très long contact). 1 au milieu si ``span`` ne dépasse pas ``min_gap`` ;
    le nombre diminue tant que l'entraxe resterait inférieur ou égal à ``min_gap``."""
    if span <= min_gap:
        return 1
    count = min(MAX_DOWEL_COUNT, max(2, math.ceil(span / ceiling - _MARGIN) + 1))
    while count > 1 and span / (count - 1) <= min_gap:
        count -= 1
    return count


def positions(width: float, edge: float, count: int) -> tuple[float, ...]:
    """Positions régulières de ``count`` pièces de ``edge`` à ``width - edge`` (milieu pour une
    seule)."""
    if count == 1:
        return (width / 2,)
    step = (width - 2 * edge) / (count - 1)
    return tuple(edge + index * step for index in range(count))


def spacing_of(places: tuple[float, ...]) -> float:
    """Écart entre deux centres voisins de ``places`` (0 pour un seul)."""
    return places[1] - places[0] if len(places) > 1 else 0.0
