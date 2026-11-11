# SPDX-License-Identifier: LGPL-2.1-or-later
"""Règles de sélection par ensemble dans la vue 3D (ADR 0048), sans FreeCAD.

Une *chaîne* est la liste des clés des éléments qui contiennent la pièce cliquée, de l'ensemble de
plus haut niveau à la pièce elle-même (dernier élément). Une chaîne vide désigne un objet qui
n'est membre d'aucun ensemble : la sélection reste native.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TypeVar

__all__ = ["click_target", "double_click_target", "up_target"]

K = TypeVar("K")


def click_target(chain: Sequence[K], current: K | None) -> K | None:
    """Élément à sélectionner après un clic simple sur la pièce de ``chain`` quand ``current``
    est la sélection : ``current`` s'il contient la pièce (ou l'est), sinon l'ensemble de plus
    haut niveau. ``None`` : chaîne vide, sélection native."""
    if not chain:
        return None
    return current if current is not None and current in chain else chain[0]


def double_click_target(chain: Sequence[K], current: K | None) -> K | None:
    """Élément à sélectionner après un double-clic sur la pièce de ``chain`` : le niveau sous
    ``current``, ou l'ensemble de plus haut niveau si ``current`` n'est pas dans la chaîne.
    ``None`` : la pièce est déjà sélectionnée (ouvrir son panneau) ou chaîne vide."""
    if not chain:
        return None
    if current is None or current not in chain:
        return chain[0]
    index = chain.index(current)
    return chain[index + 1] if index + 1 < len(chain) else None


def up_target(chain_of_current: Sequence[K]) -> K | None:
    """Élément à sélectionner après un double-clic dans le vide : le parent de la sélection,
    ``chain_of_current`` étant sa chaîne (elle-même en dernier). ``None`` au plus haut niveau."""
    return chain_of_current[-2] if len(chain_of_current) >= 2 else None
