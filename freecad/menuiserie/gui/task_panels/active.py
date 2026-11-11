# SPDX-License-Identifier: LGPL-2.1-or-later
"""Panneau de tâche de l'atelier en cours (ADR 0046, « Sélection et tâche en cours »).

``Gui.Control.activeTaskDialog()`` ne rend pas le panneau Python : le panneau affiché s'inscrit
ici (:func:`register`) et s'en retire à sa fermeture. Cache explicite et réinitialisable
(:func:`reset`), pas un singleton : il sert à reconnaître un panneau de l'atelier (par
opposition à une tâche d'un autre atelier) et à lui demander si elle a des modifications.
"""

from __future__ import annotations

from typing import Protocol

__all__ = ["ActivePanel", "current", "register", "reset", "unregister"]


class ActivePanel(Protocol):
    """Ce que le reste de l'atelier demande au panneau en cours."""

    @property
    def closed(self) -> bool:
        """Vrai une fois le panneau fermé."""

    @property
    def creating(self) -> bool:
        """Vrai pour un panneau de création (rien n'existe sans lui)."""

    def has_changes(self) -> bool:
        """Vrai si la tâche a modifié le document depuis son ouverture."""

    def accept(self) -> bool:
        """Valide la tâche (« OK »)."""

    def reject(self) -> bool:
        """Abandonne la tâche (« Annuler »)."""


_ACTIVE: list[ActivePanel] = []


def register(panel: ActivePanel) -> None:
    """Le panneau ``panel`` est affiché : il devient le panneau en cours."""
    _ACTIVE[:] = [panel]


def unregister(panel: ActivePanel) -> None:
    """Le panneau ``panel`` est fermé (sans effet si un autre l'a remplacé)."""
    if panel in _ACTIVE:
        _ACTIVE.clear()


def current() -> ActivePanel | None:
    """Panneau de l'atelier ouvert, ``None`` s'il n'y en a pas."""
    if _ACTIVE and not _ACTIVE[0].closed:
        return _ACTIVE[0]
    _ACTIVE.clear()
    return None


def reset() -> None:
    """Oublie le panneau en cours (tests)."""
    _ACTIVE.clear()
