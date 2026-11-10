# SPDX-License-Identifier: LGPL-2.1-or-later
"""Critère unique de l'assemblage « vers l'extérieur » (ADR 0026, ADR 0038, ADR 0046), sans
FreeCAD ni Qt.

Un assemblage lie ses deux pièces par des liens : FreeCAD range toute la **fermeture de liens**
d'un objet dans le Std Part où on le range (essai de l'ADR 0038, confirmé sur FreeCAD 1.1 pour le
panneau « Structure »). Ranger la pièce P dans le Std Part d'un sous-ensemble S emporterait donc
la pièce Q assemblée à elle, même si Q reste logiquement membre de l'ensemble parent A : elle se
retrouverait dans le Std Part de S sans en être membre. Un assemblage reste valide seulement si
ses deux pièces se retrouvent dans **le même ensemble** (ou toutes deux hors de tout ensemble) :
l'ensemble le plus proche de chacune est le même.

Les « chaînes » sont les noms des ensembles qui contiennent une pièce, du plus proche au plus
éloigné (vide : hors ensemble). Partagé par les décisions du panneau (``decide_drop``,
``decide_create``) et par le contrôle de l'api (``features/furniture_entry``).
"""

from __future__ import annotations

from collections.abc import Sequence

__all__ = ["keeps_assembly"]


def keeps_assembly(moved: Sequence[str], other: Sequence[str]) -> bool:
    """Vrai si un assemblage entre une pièce qui sera dans les ensembles ``moved`` (après
    l'action) et une pièce qui reste dans ``other`` garde ses deux pièces dans le même Std Part :
    même ensemble le plus proche, ou toutes deux hors de tout ensemble."""
    return list(moved[:1]) == list(other[:1])
