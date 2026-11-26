# SPDX-License-Identifier: LGPL-2.1-or-later
"""Réglages de l'atelier dans le panneau « Finition des chants » (ADR 0069).

Les réglages ne donnent que la famille et la cote A ; la cote B (bec-de-corbin, doucine) prend la
valeur de A, jamais 0 : une cote B nulle serait refusée pour ces familles.
"""

from __future__ import annotations

from typing import NamedTuple

from freecad.menuiserie.core.edges import EdgeFamily
from freecad.menuiserie.features.edge_settings import proposed_profile

__all__ = ["Proposal", "proposal"]


class Proposal(NamedTuple):
    """Profil proposé à l'ouverture : famille et cotes A et B (mm)."""

    family: EdgeFamily
    size_a: float
    size_b: float


def proposal() -> Proposal:
    """Profil proposé d'après les réglages de l'atelier (quart de rond de 1 mm par défaut)."""
    family, size_a = proposed_profile()
    return Proposal(family, size_a, size_a)
