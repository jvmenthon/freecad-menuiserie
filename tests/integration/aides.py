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
