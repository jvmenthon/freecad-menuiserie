# SPDX-License-Identifier: LGPL-2.1-or-later
"""Réglages de l'atelier pour la finition des chants : profil et cote proposés (ADR 0069).

Un réglage ne sert que de valeur proposée à l'ouverture du panneau ; un profil existant garde ses
valeurs. « Dernier utilisé » retient le profil et la cote validés.
"""

from __future__ import annotations

from freecad.menuiserie.core.edges import EdgeFamily
from freecad.menuiserie.features import settings as config

__all__ = ["proposed_profile", "record_profile_used"]


def proposed_profile() -> tuple[EdgeFamily, float]:
    """Famille et cote A (mm) proposées à l'ouverture de la finition des chants : quart de rond
    de 1 mm tant que les réglages ne sont pas modifiés."""
    values = config.settings()
    size = float(values.value(config.EDGE_PROFILE_SIZE))
    return EdgeFamily(str(values.value(config.EDGE_PROFILE))), size


def record_profile_used(family: str, size: float) -> None:
    """« Dernier utilisé » : profil (valeur de ``EdgeFamily``) et cote validés."""
    values = config.settings()
    values.record_used(config.EDGE_PROFILE, family)
    values.record_used(config.EDGE_PROFILE_SIZE, size)
