# SPDX-License-Identifier: LGPL-2.1-or-later
"""Arbre Qt du panneau « Structure » (ADR 0046) : remplissage, état déplié et sélection.

Fonctions sur un ``QTreeWidget`` seulement, sans FreeCAD : le panneau (``structure_panel``) et
la synchronisation (``structure_sync``) s'en servent. Chaque ligne garde la clé de son objet
(nom dans le document) et son identité de chemin ; aucune ligne n'écrit dans le document.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping

from PySide import QtCore, QtGui

from freecad.menuiserie.core.structure_sync import expanded_after_refresh, node_id
from freecad.menuiserie.core.structure_tree import StructureNode

__all__ = [
    "ID_ROLE",
    "KEY_ROLE",
    "expansion_of",
    "fill_tree",
    "item_for",
    "select_keys",
    "selected_keys",
]

KEY_ROLE = QtCore.Qt.UserRole  # nom de l'objet du document ("" : ligne sans objet)
ID_ROLE = QtCore.Qt.UserRole + 1  # chemin de la ligne, stable d'un rafraîchissement à l'autre
_ROW_FLAGS = QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable


def _add_node(
    parent: QtGui.QTreeWidget | QtGui.QTreeWidgetItem,
    node: StructureNode,
    parent_id: str,
    previous: Mapping[str, bool],
) -> None:
    """Ajoute ``node`` et ses descendants sous ``parent``."""
    item = QtGui.QTreeWidgetItem(parent)
    ident = node_id(parent_id, node)
    item.setText(0, node.label)
    item.setData(0, KEY_ROLE, node.key)
    item.setData(0, ID_ROLE, ident)
    # Seules les lignes qui ont un objet se sélectionnent ; le nœud « Assemblages » se déplie.
    item.setFlags(_ROW_FLAGS if node.key else QtCore.Qt.ItemIsEnabled)
    for child in node.children:
        _add_node(item, child, ident, previous)
    item.setExpanded(expanded_after_refresh(node.expanded, ident, previous))


def fill_tree(
    tree: QtGui.QTreeWidget,
    nodes: tuple[StructureNode, ...],
    message: str,
    previous: Mapping[str, bool] | None = None,
) -> None:
    """Remplace le contenu de ``tree`` par ``nodes`` ; ``message`` s'affiche s'il n'y en a pas.
    ``previous`` (:func:`expansion_of`) rend aux lignes leur état déplié."""
    tree.clear()
    for node in nodes:
        _add_node(tree, node, "", previous or {})
    if not nodes:
        placeholder = QtGui.QTreeWidgetItem(tree)
        placeholder.setText(0, message)
        placeholder.setFlags(QtCore.Qt.NoItemFlags)


def _items(tree: QtGui.QTreeWidget) -> Iterator[QtGui.QTreeWidgetItem]:
    iterator = QtGui.QTreeWidgetItemIterator(tree)
    while iterator.value():
        yield iterator.value()
        iterator += 1


def expansion_of(tree: QtGui.QTreeWidget) -> dict[str, bool]:
    """État déplié de chaque ligne, par identité de chemin."""
    return {
        str(item.data(0, ID_ROLE)): item.isExpanded() for item in _items(tree) if item.childCount()
    }


def item_for(tree: QtGui.QTreeWidget, key: str) -> QtGui.QTreeWidgetItem | None:
    """Ligne de l'objet ``key`` (la première), ``None`` s'il n'y en a pas."""
    return next((item for item in _items(tree) if item.data(0, KEY_ROLE) == key and key), None)


def selected_keys(tree: QtGui.QTreeWidget) -> list[str]:
    """Clé de chaque ligne sélectionnée (vide pour une ligne sans objet)."""
    return [str(item.data(0, KEY_ROLE) or "") for item in tree.selectedItems()]


def select_keys(tree: QtGui.QTreeWidget, keys: list[str]) -> None:
    """Sélectionne exactement les lignes de ``keys`` et déplie le chemin de la première pour
    qu'elle se voie. Les signaux de l'arbre sont bloqués : c'est à l'appelant de se garder des
    échos."""
    blocked = tree.blockSignals(True)
    try:
        tree.clearSelection()
        first = None
        for key in keys:
            item = item_for(tree, key)
            if item is None:
                continue
            item.setSelected(True)
            first = first or item
        _reveal(tree, first)
    finally:
        tree.blockSignals(blocked)


def _reveal(tree: QtGui.QTreeWidget, item: QtGui.QTreeWidgetItem | None) -> None:
    if item is None:
        return
    ancestor = item.parent()
    while ancestor is not None:
        ancestor.setExpanded(True)
        ancestor = ancestor.parent()
    tree.scrollToItem(item)
