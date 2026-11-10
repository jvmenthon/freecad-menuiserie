# SPDX-License-Identifier: LGPL-2.1-or-later
"""Transparence de sélection du panneau « Structure » (ADR 0046, « Sélection et tâche en cours »).

Les lignes que l'utilisateur choisit rendent leurs objets affichés transparents et teintés
(calque « sélection » de ``display_layers``), d'une autre teinte que l'édition. Seul l'affichage
change : le calque est retiré à la désélection, quand la sélection du panneau n'est plus ce que
l'utilisateur a choisi (sélection reprise de FreeCAD), quand le panneau est masqué ou détruit, et
rend alors l'affichage d'origine (jamais enregistré dans le document).
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
    """Calque de sélection des lignes **choisies par l'utilisateur** dans ``tree`` : une sélection
    venue de FreeCAD (arbre natif, 3D) ne rend rien transparent, et celle-ci cesse dès que la
    sélection du panneau n'est plus ce que l'utilisateur a choisi. Objet Python ordinaire (pas un
    QObject) : il peut être retiré quand le dock est déjà détruit."""

    def __init__(self, tree: QtGui.QTreeWidget, layers: DisplayLayers = DISPLAY) -> None:
        self._tree = tree
        self._layers = layers
        self._chosen: list[tuple[str, str]] = []

    def choose(self) -> None:
        """Les lignes sélectionnées viennent d'être choisies : leurs objets deviennent
        transparents, les autres sont rétablis."""
        self._chosen = self._rows()
        self._layers.show(self, self._objects(), SELECTION_LOOK, deferrable=True)

    def follow(self) -> None:
        """Arbre rempli ou sélection reprise de FreeCAD : le calque reste si les lignes choisies
        sont toujours les lignes sélectionnées (objets relus, une pièce usinée a pu apparaître),
        sinon il est retiré."""
        if self._chosen and self._rows() == self._chosen:
            self._layers.show(self, self._objects(), SELECTION_LOOK, deferrable=True)
        else:
            self.clear()

    def clear(self) -> None:
        """Calque retiré : l'affichage d'origine revient."""
        self._chosen = []
        self._layers.show(self, [], SELECTION_LOOK, deferrable=True)

    def _rows(self) -> list[tuple[str, str]]:
        """Genre et clé de chaque ligne sélectionnée qui a un objet."""
        rows = [
            (str(item.data(0, KIND_ROLE) or ""), str(item.data(0, KEY_ROLE) or ""))
            for item in self._tree.selectedItems()
        ]
        return [(kind, key) for kind, key in rows if key]

    def _objects(self) -> list[Any]:
        doc = App.ActiveDocument
        if doc is None:
            return []
        found: list[Any] = []
        for kind, key in self._chosen:
            scope, obj = scope_of(kind), doc.getObject(key)
            if scope is not None and obj is not None:
                found.extend(highlighted_objects(obj, scope))
        return found
