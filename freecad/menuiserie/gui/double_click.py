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

__all__ = ["install", "open_under_cursor", "uninstall"]

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

    Aucune zone d'affichage n'est gardée : une enveloppe Python gardée après la fermeture de sa
    vue serait rendue par PySide pour un nouveau widget créé à la même adresse, déjà « détruite ».
    Les vues ouvertes sont relues au retrait ; celles qui ont été fermées n'ont plus rien à
    retirer. Poser deux fois le filtre sur un widget ne le double pas (Qt le déplace en tête)."""

    def __init__(self) -> None:
        self.filter: _DoubleClickFilter | None = None
        self.mdi_area: QtGui.QMdiArea | None = None

    def install(self) -> None:
        if self.filter is not None:
            return
        self.filter = _DoubleClickFilter()
        for viewport in _open_viewports():
            viewport.installEventFilter(self.filter)
        window = Gui.getMainWindow()
        self.mdi_area = window.findChild(QtGui.QMdiArea) if window is not None else None
        if self.mdi_area is not None:
            self.mdi_area.subWindowActivated.connect(self.on_view_activated)

    def on_view_activated(self, *_args: object) -> None:
        """Nouvelle vue (document ouvert ou créé pendant que l'atelier est actif)."""
        viewport = _viewport(Gui.activeView())
        if self.filter is not None and viewport is not None:
            viewport.installEventFilter(self.filter)

    def uninstall(self) -> None:
        if self.filter is None:
            return
        if self.mdi_area is not None:
            # Fenêtre détruite ou signal déjà déconnecté.
            with contextlib.suppress(RuntimeError, TypeError):
                self.mdi_area.subWindowActivated.disconnect(self.on_view_activated)
        for viewport in _open_viewports():
            viewport.removeEventFilter(self.filter)
        self.mdi_area = None
        # Dernière référence : le filtre détruit, Qt le retire aussi des vues oubliées.
        self.filter = None


def _viewport(view: View) -> QtGui.QWidget | None:
    """Zone d'affichage d'une vue 3D, lue à l'instant ; ``None`` pour une autre vue."""
    graphics_view = getattr(view, "graphicsView", None)
    if graphics_view is None:
        return None
    try:
        return graphics_view().viewport()
    except RuntimeError:  # vue en cours de fermeture
        return None


def _open_viewports() -> list[QtGui.QWidget]:
    """Zones d'affichage des vues 3D de tous les documents ouverts."""
    viewports = []
    for name in App.listDocuments():
        for view in Gui.getDocument(name).mdiViewsOfType(VIEW_3D):
            viewport = _viewport(view)
            if viewport is not None:
                viewports.append(viewport)
    return viewports


_INSTALLATION: Final = _Installation()


def install() -> None:
    """Pose le filtre sur les vues 3D ouvertes et sur celles qui s'ouvriront (atelier activé)."""
    _INSTALLATION.install()


def uninstall() -> None:
    """Retire le filtre de toutes les vues (atelier désactivé)."""
    _INSTALLATION.uninstall()
