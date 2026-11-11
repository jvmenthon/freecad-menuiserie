# SPDX-License-Identifier: LGPL-2.1-or-later
"""Panneau ancré « Structure » : arbre simplifié du document actif (ADR 0046, lots 1 à 3).

Le panneau montre l'arbre calculé par ``features/structure_source`` et ne crée, ne masque ni ne
modifie aucun objet de lui-même ; l'arbre natif de FreeCAD reste intact. Le rafraîchissement, la
sélection synchronisée et le double-clic sont dans ``structure_sync`` ; le menu contextuel et le
glisser-déposer, qui passent par l'api de l'atelier, dans ``structure_actions``. Les observateurs
ne sont posés que tant que le panneau est visible.
"""

from __future__ import annotations

from functools import partial
from typing import Final

import FreeCADGui as Gui
from PySide import QtCore, QtGui

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.structure_autostart import should_open_by_default
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.gui.structure_actions import StructureActions
from freecad.menuiserie.gui.structure_dnd import DropTree
from freecad.menuiserie.gui.structure_preferences import closed_by_user, remember_closed
from freecad.menuiserie.gui.structure_sync import StructureSync
from freecad.menuiserie.gui.structure_tree_widget import fill_tree

__all__ = [
    "DOCK_NAME",
    "TREE_NAME",
    "fill_tree",
    "open_by_default",
    "open_by_default_later",
    "show_panel",
]

DOCK_NAME: Final = "MenuiserieStructureDock"
TREE_NAME: Final = "MenuiserieStructureTree"
COMBO_VIEW: Final = "Combo View"
_TITLE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Structure")


class _StructureDock(QtGui.QDockWidget):  # type: ignore[misc]
    """Dock du panneau : le fermer (croix) est un choix de l'utilisateur, mémorisé dans les
    préférences de l'atelier pour qu'il ne se rouvre pas seul."""

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        remember_closed(True)
        super().closeEvent(event)


def _create_dock(window: QtGui.QMainWindow) -> QtGui.QDockWidget:
    dock = _StructureDock(translated(_TITLE), window)
    dock.setObjectName(DOCK_NAME)
    tree = DropTree(dock)
    tree.setObjectName(TREE_NAME)
    tree.setHeaderHidden(True)
    tree.setSelectionMode(QtGui.QAbstractItemView.ExtendedSelection)
    tree.setEditTriggers(QtGui.QAbstractItemView.NoEditTriggers)
    dock.setWidget(tree)
    sync = StructureSync(tree, dock)
    StructureActions(tree, partial(sync.refresh_now, force=True), dock)

    def visibility_changed(visible: bool) -> None:
        if visible:
            sync.attach()
        else:
            sync.detach()

    dock.visibilityChanged.connect(visibility_changed)
    # Le retrait passe par un objet Python ordinaire : le contrôleur (enfant du dock) peut être
    # détruit avant que ``destroyed`` n'arrive.
    observers = sync.observers
    dock.destroyed.connect(observers.detach)
    QtCore.QCoreApplication.instance().aboutToQuit.connect(observers.detach)
    window.addDockWidget(QtCore.Qt.LeftDockWidgetArea, dock)
    combo = window.findChild(QtGui.QDockWidget, COMBO_VIEW)
    if combo is not None:
        window.tabifyDockWidget(combo, dock)  # en onglet avec la vue combinée
        combo.raise_()  # qui reste au premier plan tant qu'on n'ouvre pas l'onglet
    return dock


def show_panel(*, activate: bool = True) -> None:
    """Ouvre le panneau « Structure » ; il se remplit à l'affichage et suit ensuite le document et
    la sélection. Chemin unique de la commande et de l'ouverture par défaut. ``activate`` : le met
    au premier plan et note que l'utilisateur le veut ; sans lui (ouverture par défaut), il ne
    vole ni le premier plan ni le focus."""
    window = Gui.getMainWindow()
    if window is None:
        return
    dock = window.findChild(QtGui.QDockWidget, DOCK_NAME) or _create_dock(window)
    if activate:
        remember_closed(False)
    dock.show()
    if activate:
        dock.raise_()
    sync = dock.findChild(StructureSync)
    if sync is not None:
        sync.attach()  # sans effet si les observateurs sont posés : met le panneau à jour


def open_by_default() -> None:
    """Ouverture par défaut, à l'activation de l'atelier (après le démarrage de l'interface) : sans
    effet si l'utilisateur a fermé le panneau ou si le panneau existe déjà (``core``)."""
    window = Gui.getMainWindow()
    if window is None:
        return
    exists = window.findChild(QtGui.QDockWidget, DOCK_NAME) is not None
    if should_open_by_default(closed_by_user=closed_by_user(), exists=exists):
        show_panel(activate=False)


def open_by_default_later() -> None:
    """:func:`open_by_default` une fois la boucle d'événements libre (l'activation peut avoir lieu
    pendant la construction de la fenêtre)."""
    QtCore.QTimer.singleShot(0, open_by_default)
