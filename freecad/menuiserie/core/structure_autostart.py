# SPDX-License-Identifier: LGPL-2.1-or-later
"""Ouverture automatique du panneau « Structure » (ADR 0046), sans FreeCAD ni Qt."""

from __future__ import annotations

__all__ = ["should_open_by_default"]


def should_open_by_default(*, closed_by_user: bool, exists: bool) -> bool:
    """Vrai si le panneau doit s'ouvrir seul à l'activation de l'atelier : ni fermé volontairement
    par l'utilisateur (réglage mémorisé), ni déjà créé (ouvert, ou masqué par lui : pas de
    doublon)."""
    return not closed_by_user and not exists
