# SPDX-License-Identifier: LGPL-2.1-or-later
"""Panneau ancré « Structure » : arbre simplifié du document actif (ADR 0046, lot 1).

Lecture seule : le panneau montre l'arbre calculé par ``features/structure_source`` et ne crée,
ne masque ni ne modifie aucun objet ; l'arbre natif de FreeCAD reste intact. Le rafraîchissement
automatique, la sélection synchronisée et les actions sont les lots suivants : ici le panneau est
rempli à l'ouverture et à chaque nouvelle demande d'ouverture.
"""

from __future__ import annotations

from typing import Final

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.structure_tree import NodeKind, StructureNode
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.features.structure_source import structure_of

__all__ = ["DOCK_NAME", "TREE_NAME", "fill_tree", "show_panel"]

DOCK_NAME: Final = "MenuiserieStructureDock"
TREE_NAME: Final = "MenuiserieStructureTree"
_TITLE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Structure")
_NO_DOCUMENT: Final = QT_TRANSLATE_NOOP("Menuiserie", "Aucun document ouvert.")
_EMPTY: Final = QT_TRANSLATE_NOOP("Menuiserie", "Aucun ensemble ni aucune pièce.")


def _add_node(parent: QtGui.QTreeWidget | QtGui.QTreeWidgetItem, node: StructureNode) -> None:
    """Ajoute ``node`` et ses descendants sous ``parent`` (le nom d'objet est gardé en donnée)."""
    item = QtGui.QTreeWidgetItem(parent)
    item.setText(0, node.label)
    item.setData(0, QtCore.Qt.UserRole, node.key)
    item.setFlags(QtCore.Qt.ItemIsEnabled)  # lecture seule : ni sélection ni édition (lot 1)
    for child in node.children:
        _add_node(item, child)
    item.setExpanded(node.expanded and node.kind is not NodeKind.JOINTS)


def fill_tree(tree: QtGui.QTreeWidget, nodes: tuple[StructureNode, ...], message: str) -> None:
    """Remplace le contenu de ``tree`` par ``nodes`` ; ``message`` s'affiche s'il n'y en a pas."""
    tree.clear()
    for node in nodes:
        _add_node(tree, node)
    if not nodes:
        placeholder = QtGui.QTreeWidgetItem(tree)
        placeholder.setText(0, message)
        placeholder.setFlags(QtCore.Qt.NoItemFlags)


def _create_dock(window: QtGui.QMainWindow) -> QtGui.QDockWidget:
    dock = QtGui.QDockWidget(translated(_TITLE), window)
    dock.setObjectName(DOCK_NAME)
    tree = QtGui.QTreeWidget(dock)
    tree.setObjectName(TREE_NAME)
    tree.setHeaderHidden(True)
    dock.setWidget(tree)
    window.addDockWidget(QtCore.Qt.LeftDockWidgetArea, dock)
    return dock


def show_panel() -> None:
    """Ouvre le panneau « Structure » (ou le met au premier plan) et le remplit d'après le
    document actif."""
    window = Gui.getMainWindow()
    if window is None:
        return
    dock = window.findChild(QtGui.QDockWidget, DOCK_NAME) or _create_dock(window)
    tree = dock.widget()
    doc = App.ActiveDocument
    if doc is None:
        fill_tree(tree, (), translated(_NO_DOCUMENT))
    else:
        fill_tree(tree, structure_of(doc), translated(_EMPTY))
    dock.show()
    dock.raise_()
