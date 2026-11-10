# SPDX-License-Identifier: LGPL-2.1-or-later
"""Panneau ancré « Structure » : arbre simplifié du document actif (ADR 0046, lots 1 et 2).

Lecture seule du modèle : le panneau montre l'arbre calculé par ``features/structure_source`` et
ne crée, ne masque ni ne modifie aucun objet ; l'arbre natif de FreeCAD reste intact. Le
rafraîchissement, la sélection synchronisée et le double-clic sont dans ``structure_sync`` ; le
menu contextuel et le glisser-déposer sont le lot suivant. Les observateurs ne sont posés que
tant que le panneau est visible.
"""

from __future__ import annotations

from typing import Final

import FreeCADGui as Gui
from PySide import QtCore, QtGui

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.gui.structure_sync import StructureSync
from freecad.menuiserie.gui.structure_tree_widget import fill_tree

__all__ = ["DOCK_NAME", "TREE_NAME", "fill_tree", "show_panel"]

DOCK_NAME: Final = "MenuiserieStructureDock"
TREE_NAME: Final = "MenuiserieStructureTree"
_TITLE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Structure")


def _create_dock(window: QtGui.QMainWindow) -> QtGui.QDockWidget:
    dock = QtGui.QDockWidget(translated(_TITLE), window)
    dock.setObjectName(DOCK_NAME)
    tree = QtGui.QTreeWidget(dock)
    tree.setObjectName(TREE_NAME)
    tree.setHeaderHidden(True)
    tree.setSelectionMode(QtGui.QAbstractItemView.ExtendedSelection)
    tree.setEditTriggers(QtGui.QAbstractItemView.NoEditTriggers)
    dock.setWidget(tree)
    sync = StructureSync(tree, dock)
    dock.visibilityChanged.connect(lambda visible: sync.attach() if visible else sync.detach())
    dock.destroyed.connect(sync.detach)
    window.addDockWidget(QtCore.Qt.LeftDockWidgetArea, dock)
    return dock


def show_panel() -> None:
    """Ouvre le panneau « Structure » (ou le met au premier plan) ; il se remplit à l'affichage
    et suit ensuite le document et la sélection."""
    window = Gui.getMainWindow()
    if window is None:
        return
    dock = window.findChild(QtGui.QDockWidget, DOCK_NAME) or _create_dock(window)
    dock.show()
    dock.raise_()
    sync = dock.findChild(StructureSync)
    if sync is not None:
        sync.attach()  # sans effet si les observateurs sont posés : met le panneau à jour
