# SPDX-License-Identifier: LGPL-2.1-or-later
"""Réglage mémorisé du panneau « Structure » : fermé par l'utilisateur (ADR 0046).

Écrit dans les préférences de l'atelier (``App.ParamGet``), jamais dans le document.
"""

from __future__ import annotations

from typing import Final

import FreeCAD as App

from freecad.menuiserie.features.library import PARAM_PATH

__all__ = ["closed_by_user", "remember_closed"]

KEY: Final = "StructureClosedByUser"


def closed_by_user() -> bool:
    """Vrai si l'utilisateur a fermé le panneau (il ne s'ouvre plus seul)."""
    return bool(App.ParamGet(PARAM_PATH).GetBool(KEY, False))


def remember_closed(closed: bool) -> None:
    """Mémorise que l'utilisateur a fermé le panneau (``True``) ou l'a rouvert (``False``)."""
    App.ParamGet(PARAM_PATH).SetBool(KEY, closed)
