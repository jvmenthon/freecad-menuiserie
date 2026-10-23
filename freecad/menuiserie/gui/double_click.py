# SPDX-License-Identifier: LGPL-2.1-or-later
"""Double-clic dans la vue 3D sur un objet de l'atelier : son panneau de tâche (issue #76,
ADR 0018).

FreeCAD n'appelle ``doubleClicked`` du ViewProvider que depuis l'arbre : dans la vue 3D, le
style de navigation absorbe le second clic. Un filtre d'évènements Qt est donc posé sur la zone
d'affichage de chaque vue 3D **tant que l'atelier est actif** (ADR 0007, § 3 : rien de permanent),
puis retiré. Il ne réagit qu'au double-clic gauche, ne regarde que l'objet sous le curseur, et
ne consomme l'évènement que si cet objet est de l'atelier et que son panneau s'est ouvert : tout
autre double-clic suit son cours habituel (autres ateliers, sélection, navigation).
"""

from __future__ import annotations

import contextlib
from typing import Any, Final

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui

from freecad.menuiserie.gui.view_providers.wood_part import PanelEditing

__all__ = ["install", "open_under_cursor", "uninstall", "viewports_3d"]

View = Any
VIEW_3D: Final = "Gui::View3DInventor"


def open_under_cursor(view: View) -> bool:
    """Ouvre le panneau de l'objet de l'atelier sous le curseur dans ``view`` ; ``False`` si la
    vue n'est pas une vue 3D, s'il n'y a rien sous le curseur, si l'objet n'est pas de l'atelier
    ou si son panneau est refusé (un autre panneau est ouvert)."""
    if not hasattr(view, "getObjectInfo"):
        return False
    info = view.getObjectInfo(view.getCursorPos())
    if not info:
        return False
    doc = App.listDocuments().get(info.get("Document", ""))
    obj = doc.getObject(info.get("Object", "")) if doc is not None else None
    vobj = getattr(obj, "ViewObject", None)
    proxy = getattr(vobj, "Proxy", None)
    if not isinstance(proxy, PanelEditing):
        return False
    return bool(proxy.doubleClicked(vobj))


class _DoubleClickFilter(QtCore.QObject):  # type: ignore[misc]
    """Filtre posé sur la zone d'affichage des vues 3D : double-clic gauche seulement."""

    def eventFilter(self, watched: QtCore.QObject, event: QtCore.QEvent) -> bool:
        """Vrai (évènement consommé) seulement si le panneau d'un objet de l'atelier s'ouvre."""
        del watched
        if event.type() != QtCore.QEvent.MouseButtonDblClick:
            return False
        if event.button() != QtCore.Qt.LeftButton:
            return False
        return open_under_cursor(Gui.activeView())


class _Installation:
    """Filtre unique, posé pendant que l'atelier est actif.

    Les zones d'affichage sont relues dans les sous-fenêtres de la zone MDI à chaque pose et au
    retrait, jamais gardées. (``graphicsView()`` de la vue n'est pas utilisé : la zone
    d'affichage obtenue par lui est déjà détruite pour PySide 6.) Poser deux fois le filtre sur un
    widget ne le double pas (Qt le déplace en tête)."""

    def __init__(self) -> None:
        self.filter: _DoubleClickFilter | None = None
        self.mdi_area: QtGui.QMdiArea | None = None

    def install(self) -> None:
        if self.filter is not None:
            return
        self.filter = _DoubleClickFilter()
        window = Gui.getMainWindow()
        self.mdi_area = window.findChild(QtGui.QMdiArea) if window is not None else None
        if self.mdi_area is None:
            return
        self.mdi_area.subWindowActivated.connect(self.on_view_activated)
        self.on_view_activated()

    def on_view_activated(self, *_args: object) -> None:
        """Vues ouvertes, nouvelles comprises (document ouvert pendant que l'atelier est actif)."""
        if self.filter is not None and self.mdi_area is not None:
            for viewport in viewports_3d(self.mdi_area):
                viewport.installEventFilter(self.filter)

    def uninstall(self) -> None:
        if self.filter is None:
            return
        if self.mdi_area is not None:
            # Fenêtre détruite ou signal déjà déconnecté.
            with contextlib.suppress(RuntimeError, TypeError):
                self.mdi_area.subWindowActivated.disconnect(self.on_view_activated)
            for viewport in viewports_3d(self.mdi_area):
                viewport.removeEventFilter(self.filter)
        self.mdi_area = None
        # Dernière référence : le filtre détruit, Qt le retire aussi des vues oubliées.
        self.filter = None


def viewports_3d(mdi_area: QtGui.QMdiArea, current_only: bool = False) -> list[QtGui.QWidget]:
    """Zones d'affichage des vues 3D de la zone MDI (``current_only`` : de la sous-fenêtre
    courante seulement), lues à l'instant."""
    windows = [mdi_area.currentSubWindow()] if current_only else mdi_area.subWindowList()
    viewports = []
    for window in windows:
        view = window.widget() if window is not None else None
        if view is None or view.metaObject().className() != VIEW_3D:
            continue
        viewports += [graphics.viewport() for graphics in view.findChildren(QtGui.QGraphicsView)]
    return viewports


_INSTALLATION: Final = _Installation()


def install() -> None:
    """Pose le filtre sur les vues 3D ouvertes et sur celles qui s'ouvriront (atelier activé)."""
    _INSTALLATION.install()


def uninstall() -> None:
    """Retire le filtre de toutes les vues (atelier désactivé)."""
    _INSTALLATION.uninstall()
