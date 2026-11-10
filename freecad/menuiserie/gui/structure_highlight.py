# SPDX-License-Identifier: LGPL-2.1-or-later
"""Transparence de sélection du panneau « Structure » (ADR 0046, « Sélection et tâche en cours »).

Les lignes sélectionnées rendent leurs objets affichés transparents et teintés (calque
« sélection » de ``display_layers``), d'une autre teinte que l'édition. Seul l'affichage change :
le calque est retiré à la désélection, quand le panneau est masqué ou détruit, et rend alors
l'affichage d'origine (jamais enregistré dans le document).
"""

from __future__ import annotations

from typing import Any

import FreeCAD as App
from PySide import QtGui

from freecad.menuiserie.core.display_layers import SELECTION_LOOK
from freecad.menuiserie.core.structure_highlight import scope_of
from freecad.menuiserie.features.highlight_targets import highlighted_objects
from freecad.menuiserie.gui.display_layers import DISPLAY, DisplayLayers
from freecad.menuiserie.gui.structure_tree_widget import KEY_ROLE, KIND_ROLE

__all__ = ["RowHighlight"]


class RowHighlight:
    """Calque de sélection des lignes de ``tree``. Objet Python ordinaire (pas un QObject) : il
    peut être retiré quand le dock est déjà détruit."""

    def __init__(self, tree: QtGui.QTreeWidget, layers: DisplayLayers = DISPLAY) -> None:
        self._tree = tree
        self._layers = layers

    def sync(self) -> None:
        """Objets des lignes sélectionnées rendus transparents, les autres rétablis."""
        self._layers.show(self, self._objects(), SELECTION_LOOK)

    def clear(self) -> None:
        """Calque retiré : l'affichage d'origine revient."""
        self._layers.release(self)

    def _objects(self) -> list[Any]:
        doc = App.ActiveDocument
        if doc is None:
            return []
        found: list[Any] = []
        for item in self._tree.selectedItems():
            scope = scope_of(str(item.data(0, KIND_ROLE) or ""))
            key = item.data(0, KEY_ROLE)
            obj = doc.getObject(key) if scope is not None and key else None
            if obj is not None and scope is not None:
                found.extend(highlighted_objects(obj, scope))
        return found
