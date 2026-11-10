# SPDX-License-Identifier: LGPL-2.1-or-later
"""Dernière forme affectée à un objet, pour ne pas la réaffecter quand rien n'a changé.

Affecter ``Shape`` coûte cher (FreeCAD, puis la vue 3D qui retesselle) : une pièce usinée ou un
assemblage qui a seulement été déplacé (pas de répétition changé) garde sa forme, dont le
``Placement`` suffit à suivre le déplacement.
"""

from __future__ import annotations

from collections.abc import Hashable
from typing import Any

from freecad.menuiserie.features.freecad_types import DocumentObject

__all__ = ["AssignedShape"]


class AssignedShape:
    """Forme affectée en dernier à un objet et la clé de ce qui l'a produite. La forme actuelle
    de l'objet doit être celle qui a été affectée (même solide OCC, ou deux formes vides) : une
    annulation ou un script qui l'a changée force la réaffectation."""

    def __init__(self) -> None:
        self._key: Hashable | None = None
        self._shape: Any = None

    def is_current(self, obj: DocumentObject, key: Hashable | None) -> bool:
        """Vrai si la forme de ``obj`` est déjà celle que produit ``key`` (``None`` : inconnu)."""
        if key is None or key != self._key or self._shape is None:
            return False
        shape = obj.Shape
        if shape.isNull() or self._shape.isNull():
            return bool(shape.isNull() and self._shape.isNull())
        return bool(shape.isPartner(self._shape))

    def remember(self, key: Hashable | None, shape: Any) -> None:
        """Retient la forme qui vient d'être affectée avec la clé ``key``."""
        self._key, self._shape = key, shape
