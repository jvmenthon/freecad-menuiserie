# SPDX-License-Identifier: LGPL-2.1-or-later
"""Aides partagées par les tests d'intégration (sans import de FreeCAD)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

# Fabrique de pièces de bois de la fixture ``board`` (``conftest.py``).
Board = Callable[..., Any]


def touched_names(doc: Any) -> list[str]:
    """Noms des objets du document marqués « Touched »."""
    return [obj.Name for obj in doc.Objects if "Touched" in obj.State]


def detach_one_copy(copy: Any) -> None:
    """Détache la seule copie ``copy`` de sa répétition, qui garde ses autres copies : c'est ce
    que fait la suppression de la pièce d'origine d'une répétition à plusieurs sources
    (``repeat_links.detach_copies``). « Dissocier la répétition » (``api.dissociate``) détache
    toutes les copies d'un coup et supprime la répétition (demande de jv, 2026-11-23)."""
    from freecad.menuiserie.features import repeat_links  # FreeCAD n'est chargé qu'ici

    copy.Document.recompute()  # les valeurs gardées sont celles de la source à jour
    repeat_links.unlink_copy(copy)
    copy.Document.recompute()
