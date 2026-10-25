# SPDX-License-Identifier: LGPL-2.1-or-later
"""Évènements du glissement : filtre d'application et observateur de sélection (ADR 0021).

Comme le double-clic (ADR 0018), le filtre est posé sur l'application **tant que l'atelier est
actif** (ADR 0007) puis retiré, avec l'observateur de sélection qui dessine ou enlève les flèches.
Le filtre ne consomme que le clic gauche enfoncé sur une flèche ou une poignée (testé en pixels
par ``handle_at``) et, pendant le glissement, les mouvements, le relâchement et Échap : tout le
reste, molette, autres boutons, clic ailleurs, est rendu à FreeCAD sans y toucher.
"""

from __future__ import annotations

import traceback
from collections.abc import Callable
from typing import Any, Final

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui

from freecad.menuiserie.gui.double_click import is_viewport_3d, view_point, viewports_3d
from freecad.menuiserie.gui.drag.session import DragSession

__all__ = ["current_session", "install", "installed", "uninstall"]

_QEvent = QtCore.QEvent
_KEYS: Final = (_QEvent.KeyPress, _QEvent.KeyRelease, _QEvent.ShortcutOverride)
_MOUSE: Final = (
    _QEvent.MouseButtonPress,
    _QEvent.MouseMove,
    _QEvent.MouseButtonRelease,
    _QEvent.Wheel,
)
ZOOM_DELAY_MS: Final = 50  # la molette a fini de zoomer : flèches à la bonne taille


def _guarded(session: DragSession, action: Callable[..., bool], *args: Any) -> bool:
    """Exécute ``action`` ; une erreur annule le glissement, est écrite dans la vue rapport et
    l'évènement est rendu à FreeCAD."""
    try:
        return action(*args)
    except Exception:  # pylint: disable=broad-exception-caught
        App.Console.PrintError(traceback.format_exc())
        session.abort()
        return False


class _DragFilter(QtCore.QObject):  # type: ignore[misc]
    """Filtre d'application du glissement (voir le module). Tout évènement étranger est rendu
    aussitôt (une comparaison de type)."""

    def __init__(self, session: DragSession) -> None:
        super().__init__()
        self._session = session

    def eventFilter(self, watched: QtCore.QObject, event: QtCore.QEvent) -> bool:
        """Vrai (consommé) seulement pour la saisie d'une flèche ou d'une poignée et pour le
        glissement qui s'en suit. Une erreur annule le glissement et rend l'évènement."""
        try:
            return self._filter(watched, event)
        except Exception:  # pylint: disable=broad-exception-caught
            App.Console.PrintError(traceback.format_exc())
            self._session.abort()
            return False

    def _filter(self, watched: QtCore.QObject, event: QtCore.QEvent) -> bool:
        kind = event.type()
        if kind in _KEYS:
            return self._key(kind, event)
        if kind not in _MOUSE or not self._session.active or not is_viewport_3d(watched):
            return False
        if not self._in_current_view(watched):
            return False
        if kind == _QEvent.Wheel:
            QtCore.QTimer.singleShot(ZOOM_DELAY_MS, self._session.sync)
            return False
        return self._mouse(kind, watched, event)

    def _key(self, kind: QtCore.QEvent.Type, event: QtCore.QEvent) -> bool:
        session = self._session
        if event.key() == QtCore.Qt.Key_Shift and kind != _QEvent.ShortcutOverride:
            if session.dragging:
                _guarded(session, _shift, session, kind == _QEvent.KeyPress)
            return False
        if event.key() == QtCore.Qt.Key_Escape and session.dragging:
            return kind != _QEvent.KeyRelease and _guarded(session, session.escape)
        return False

    @staticmethod
    def _in_current_view(viewport: QtGui.QWidget) -> bool:
        mdi = Gui.getMainWindow().findChild(QtGui.QMdiArea)
        return mdi is not None and any(v == viewport for v in viewports_3d(mdi, current_only=True))

    def _mouse(self, kind: QtCore.QEvent.Type, viewport: QtGui.QWidget, event: Any) -> bool:
        session = self._session
        position = event.position() if hasattr(event, "position") else event.pos()  # Qt 6, Qt 5
        point = view_point(viewport, position.x(), position.y())
        modifiers = event.modifiers()
        shift = modifiers == QtCore.Qt.ShiftModifier
        if kind == _QEvent.MouseButtonPress:
            plain = shift or modifiers == QtCore.Qt.NoModifier
            if event.button() != QtCore.Qt.LeftButton or not plain:
                return False
            return _guarded(session, session.press, point, shift)
        if kind == _QEvent.MouseMove:
            moving = event.buttons() == QtCore.Qt.NoButton
            if not moving and not session.dragging and not session.swallow_release:
                return False  # navigation en cours : rien à voir
            return _guarded(session, session.move, point, shift)
        if event.button() != QtCore.Qt.LeftButton:
            return False
        return _guarded(session, session.release, point)


def _shift(session: DragSession, pressed: bool) -> bool:
    session.shift_changed(pressed)
    return False


class _SelectionObserver:
    """Observateur de sélection : ne fait que dessiner ou enlever les flèches. Les rafales
    (une notification par élément) sont fondues en un seul rafraîchissement."""

    def __init__(self, session: DragSession) -> None:
        self._session = session
        self._pending = False

    def _changed(self, *_args: object) -> None:
        if not self._pending:
            self._pending = True
            QtCore.QTimer.singleShot(0, self._refresh)

    def _refresh(self) -> None:
        self._pending = False
        _guarded(self._session, _refresh, self._session)

    addSelection = removeSelection = setSelection = clearSelection = _changed


class _DocumentObserver:
    """Observateur de documents : un document fermé emporte ses flèches avec sa vue."""

    def __init__(self, session: DragSession) -> None:
        self._session = session

    def slotDeletedDocument(self, doc: Any) -> None:
        _guarded(self._session, _forget, self._session, doc.Name)


def _forget(session: DragSession, document: str) -> bool:
    session.forget(document)
    return False


def _refresh(session: DragSession) -> bool:
    session.refresh()
    return False


class _Installation:
    """Filtre, observateur et session uniques, posés pendant que l'atelier est actif."""

    def __init__(self) -> None:
        self.session: DragSession | None = None
        self.filter: _DragFilter | None = None
        self.observer: _SelectionObserver | None = None
        self.documents: _DocumentObserver | None = None

    def install(self) -> None:
        application = QtGui.QApplication.instance()
        if self.filter is not None or application is None:
            return
        self.session = DragSession()
        self.filter = _DragFilter(self.session)
        self.observer = _SelectionObserver(self.session)
        application.installEventFilter(self.filter)
        self.documents = _DocumentObserver(self.session)
        Gui.Selection.addObserver(self.observer)
        App.addDocumentObserver(self.documents)
        self.session.refresh()

    def uninstall(self) -> None:
        """Chaque retrait est tenté même si un autre échoue ; la session est toujours close."""
        if self.filter is None:
            return
        application = QtGui.QApplication.instance()
        try:
            if application is not None:
                application.removeEventFilter(self.filter)
        finally:
            try:
                Gui.Selection.removeObserver(self.observer)
            finally:
                try:
                    if self.documents is not None:
                        App.removeDocumentObserver(self.documents)
                finally:
                    session = self.session
                    self.session = self.filter = self.observer = self.documents = None
                    if session is not None:
                        session.shutdown()


_INSTALLATION: Final = _Installation()


def install() -> None:
    """Pose le filtre et l'observateur (atelier activé)."""
    _INSTALLATION.install()


def installed() -> bool:
    """Vrai si le filtre et l'observateur sont posés (atelier actif)."""
    return _INSTALLATION.filter is not None and _INSTALLATION.observer is not None


def uninstall() -> None:
    """Retire le filtre et l'observateur, enlève les flèches (atelier désactivé)."""
    _INSTALLATION.uninstall()


def current_session() -> DragSession | None:
    """Session du glissement, ``None`` tant que l'atelier n'est pas actif."""
    return _INSTALLATION.session
