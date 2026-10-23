# SPDX-License-Identifier: LGPL-2.1-or-later
"""Double-clic dans la vue 3D sur un objet de l'atelier : son panneau de tâche (issue #76,
ADR 0018).

FreeCAD n'appelle ``doubleClicked`` du ViewProvider que depuis l'arbre : dans la vue 3D, le
style de navigation absorbe le second clic. Un filtre d'évènements Qt est donc posé sur
l'application **tant que l'atelier est actif** (ADR 0007, § 3 : rien de permanent), puis
retiré. Il ne réagit qu'au double-clic gauche dans la zone d'affichage d'une vue 3D, ne regarde
que l'objet sous le clic, et
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

__all__ = [
    "install",
    "installed",
    "is_viewport_3d",
    "open_at",
    "uninstall",
    "view_point",
    "viewports_3d",
]

View = Any
VIEW_3D: Final = "Gui::View3DInventor"


def open_at(view: View, point: tuple[int, int]) -> bool:
    """Ouvre le panneau de l'objet de l'atelier au point ``point`` de ``view`` (pixels de
    FreeCAD, origine en bas à gauche) ; ``False`` si la vue n'est pas une vue 3D, s'il n'y a rien
    à ce point, si l'objet n'est pas de l'atelier ou si son panneau est refusé (un autre panneau
    est ouvert)."""
    if not hasattr(view, "getObjectInfo"):
        return False
    info = view.getObjectInfo(point)
    if not info:
        return False
    doc = App.listDocuments().get(info.get("Document", ""))
    obj = doc.getObject(info.get("Object", "")) if doc is not None else None
    vobj = getattr(obj, "ViewObject", None)
    proxy = getattr(vobj, "Proxy", None)
    if not isinstance(proxy, PanelEditing):
        return False
    return bool(proxy.doubleClicked(vobj))


def view_point(viewport: QtGui.QWidget, x: float, y: float) -> tuple[int, int]:
    """Point Qt ``(x, y)`` de la zone d'affichage en pixels de FreeCAD (rapport de pixels de
    l'écran appliqué, origine en bas à gauche), comme ``View3DInventorViewer::fromQPoint``."""
    ratio = viewport.devicePixelRatioF()
    height = round(viewport.height() * ratio)
    return round(x * ratio), height - round(y * ratio) - 1


class _DoubleClickFilter(QtCore.QObject):  # type: ignore[misc]
    """Filtre d'application : double-clic gauche sur la zone d'affichage d'une vue 3D seulement.

    Posé sur l'application et non sur chaque vue : les filtres d'application passent avant ceux
    des widgets, dont celui de Quarter (la vue 3D de FreeCAD), posé sur la zone d'affichage après
    le nôtre et qui traiterait le clic d'abord. Tout autre évènement est rendu aussitôt (une
    comparaison de type)."""

    def eventFilter(self, watched: QtCore.QObject, event: QtCore.QEvent) -> bool:
        """Vrai (évènement consommé) seulement si le panneau d'un objet de l'atelier s'ouvre."""
        if event.type() != QtCore.QEvent.MouseButtonDblClick:
            return False
        if event.button() != QtCore.Qt.LeftButton or not is_viewport_3d(watched):
            return False
        position = event.position() if hasattr(event, "position") else event.pos()  # Qt 6, Qt 5
        return open_at(Gui.activeView(), view_point(watched, position.x(), position.y()))


class _Installation:
    """Filtre unique, posé sur l'application pendant que l'atelier est actif."""

    def __init__(self) -> None:
        self.filter: _DoubleClickFilter | None = None

    def install(self) -> None:
        application = QtGui.QApplication.instance()
        if self.filter is not None or application is None:
            return
        self.filter = _DoubleClickFilter()
        application.installEventFilter(self.filter)

    def uninstall(self) -> None:
        application = QtGui.QApplication.instance()
        if self.filter is None:
            return
        if application is not None:
            application.removeEventFilter(self.filter)
        self.filter = None


def is_viewport_3d(widget: QtCore.QObject) -> bool:
    """Vrai si ``widget`` est la zone d'affichage d'une vue 3D (``QGraphicsView`` dans une
    ``Gui::View3DInventor``)."""
    graphics = widget.parent() if isinstance(widget, QtGui.QWidget) else None
    if not isinstance(graphics, QtGui.QGraphicsView) or graphics.viewport() != widget:
        return False
    ancestor = graphics.parent()
    while ancestor is not None:
        if ancestor.metaObject().className() == VIEW_3D:
            return True
        ancestor = ancestor.parent()
    return False


def viewports_3d(mdi_area: QtGui.QMdiArea, current_only: bool = False) -> list[QtGui.QWidget]:
    """Zones d'affichage des vues 3D de la zone MDI (``current_only`` : de la sous-fenêtre
    courante seulement), lues à l'instant."""
    windows = [mdi_area.currentSubWindow()] if current_only else mdi_area.subWindowList()
    viewports = []
    for window in windows:
        # Sous-fenêtre en cours de fermeture (signal émis pendant sa destruction) : ignorée.
        with contextlib.suppress(RuntimeError):
            view = window.widget() if window is not None else None
            if view is None or view.metaObject().className() != VIEW_3D:
                continue
            viewports += [g.viewport() for g in view.findChildren(QtGui.QGraphicsView)]
    return viewports


_INSTALLATION: Final = _Installation()


def install() -> None:
    """Pose le filtre (atelier activé)."""
    _INSTALLATION.install()


def installed() -> bool:
    """Vrai si le filtre est posé (atelier actif)."""
    return _INSTALLATION.filter is not None


def uninstall() -> None:
    """Retire le filtre (atelier désactivé)."""
    _INSTALLATION.uninstall()
