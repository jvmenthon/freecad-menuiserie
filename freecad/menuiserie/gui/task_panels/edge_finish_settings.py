# SPDX-License-Identifier: LGPL-2.1-or-later
"""Réglages de l'atelier dans le panneau « Finition des chants » (ADR 0069).

Les réglages ne donnent que la famille et la cote A ; la cote B (bec-de-corbin, doucine) prend la
valeur de A, jamais 0 : une cote B nulle serait refusée pour ces familles.
"""

from __future__ import annotations

from typing import NamedTuple

from freecad.menuiserie.core.edges import EdgeFamily
from freecad.menuiserie.features.edge_settings import proposed_profile, record_profile_used

__all__ = ["Proposal", "default_size_b", "proposal", "record_accepted"]


class Proposal(NamedTuple):
    """Profil proposé à l'ouverture : famille et cotes A et B (mm)."""

    family: EdgeFamily
    size_a: float
    size_b: float


def default_size_b(size_a: float) -> float:
    """Cote B par défaut d'un profil : celle de la cote A."""
    return size_a


def proposal() -> Proposal:
    """Profil proposé d'après les réglages de l'atelier (quart de rond de 1 mm par défaut)."""
    family, size_a = proposed_profile()
    return Proposal(family, size_a, default_size_b(size_a))


def record_accepted(family: str, size_a: float) -> None:
    """« Dernier utilisé » : profil et cote A validés à la création."""
    record_profile_used(family, size_a)
