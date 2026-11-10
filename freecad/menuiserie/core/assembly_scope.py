# SPDX-License-Identifier: LGPL-2.1-or-later
"""Critère unique de l'assemblage « vers l'extérieur » (ADR 0026, ADR 0046), sans FreeCAD ni Qt.

Un assemblage est rangé sous l'ensemble le plus proche qui contient ses deux pièces
(``common_furniture``). Quand une pièce change d'ensemble (déplacée, sortie, ou emportée dans un
nouvel ensemble), l'assemblage reste valide tant que ses deux pièces gardent un ensemble commun :
ranger l'une dans un sous-ensemble de l'ensemble qui contient aussi l'autre ne le sépare pas.
Il est séparé quand elles n'ont plus d'ensemble commun, sauf si elles sont toutes deux hors de
tout ensemble.

Les « chaînes » sont les noms des ensembles qui contiennent une pièce, du plus proche au plus
éloigné (vide : hors ensemble). Partagé par les décisions du panneau (``decide_drop``,
``decide_create``) et par le contrôle de l'api (``features/furniture_entry``).
"""

from __future__ import annotations

from collections.abc import Sequence

__all__ = ["keeps_assembly", "nearest_common"]


def nearest_common(first: Sequence[str], second: Sequence[str]) -> str | None:
    """Ensemble le plus proche de ``first`` qui est aussi dans ``second`` (``None`` : aucun)."""
    others = set(second)
    return next((name for name in first if name in others), None)


def keeps_assembly(moved: Sequence[str], other: Sequence[str]) -> bool:
    """Vrai si un assemblage entre une pièce qui sera dans les ensembles ``moved`` (après
    l'action) et une pièce qui reste dans ``other`` garde un ensemble commun, ou si les deux
    sont hors de tout ensemble."""
    if nearest_common(moved, other) is not None:
        return True
    return not moved and not other
