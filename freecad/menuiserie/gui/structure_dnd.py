# SPDX-License-Identifier: LGPL-2.1-or-later
"""Arbre du panneau « Structure » avec glisser-déposer (ADR 0046, lot 3).

:class:`DropTree` ne change jamais ses lignes : pendant le survol il demande à ``judge`` si le
dépôt est permis (curseur interdit et raison en infobulle sinon), au dépôt il prévient
``on_drop`` avec les clés glissées et l'ensemble visé, et c'est le rafraîchissement du panneau
qui redessine l'arbre. Aucune écriture dans le document ici.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide import QtCore, QtGui

from freecad.menuiserie.core.structure_actions import drop_blocked, drop_target, plain_tooltip
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.gui.structure_tree_widget import draggable_keys, row_path

__all__ = ["DropTree"]

Judge = Callable[[list[str], str | None], str]  # clés, ensemble visé -> raison du refus ("" : ok)
Dropped = Callable[[list[str], str | None], None]


def _point(event: Any) -> Any:
    """Position d'un événement de glisser-déposer dans la zone d'affichage (Qt 5 et Qt 6)."""
    return event.position().toPoint() if hasattr(event, "position") else event.pos()


class DropTree(QtGui.QTreeWidget):  # type: ignore[misc]
    """``QTreeWidget`` dont les pièces et les ensembles se glissent sur un ensemble (les ranger
    dedans) ou sur le vide / une pièce hors ensemble (les sortir de leur ensemble)."""

    def __init__(self, parent: QtGui.QWidget | None = None) -> None:
        super().__init__(parent)
        self.judge: Judge | None = None
        self.on_drop: Dropped | None = None
        self.on_drag_start: Callable[[], None] | None = None
        self._dragged: list[str] = []
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QtGui.QAbstractItemView.DragDrop)
        self.setDefaultDropAction(QtCore.Qt.MoveAction)

    def target_at(self, point: Any) -> str | None:
        """Ensemble visé par un dépôt en ``point`` : celui de la ligne (ou de son ensemble), sinon
        ``None`` (hors ensemble)."""
        return drop_target(row_path(self.itemAt(point)))

    def blocked_reason(self, point: Any) -> str:
        """Raison (traduite) pour laquelle la ligne en ``point`` ne reçoit rien : répétition et
        ses copies, liste de débit, autres objets. Vide si le dépôt y est jugé par ``judge``."""
        template = drop_blocked(row_path(self.itemAt(point)))
        return translated(template) if template else ""

    def dragEnterEvent(self, event: Any) -> None:
        """Accepte seulement le glissement de lignes de ce panneau (jamais un fichier ni un
        objet d'un autre panneau) ; mémorise les lignes glissées."""
        self._dragged = draggable_keys(self) if event.source() is self else []
        if not self._dragged:
            event.ignore()
            return
        if self.on_drag_start is not None:
            self.on_drag_start()
        event.acceptProposedAction()

    def dragMoveEvent(self, event: Any) -> None:
        """Curseur permis ou interdit selon la décision ; la raison du refus s'affiche."""
        point = _point(event)
        super().dragMoveEvent(event)  # défilement automatique et repère de dépôt
        reason = self.blocked_reason(point) or self._reason(self.target_at(point))
        if reason:
            event.ignore()
            QtGui.QToolTip.showText(self.viewport().mapToGlobal(point), plain_tooltip(reason), self)
        else:
            event.acceptProposedAction()
            QtGui.QToolTip.hideText()

    def dragLeaveEvent(self, event: Any) -> None:
        """Le glissement quitte l'arbre : plus d'infobulle."""
        QtGui.QToolTip.hideText()
        super().dragLeaveEvent(event)

    def dropEvent(self, event: Any) -> None:
        """Prévient ``on_drop`` sans déplacer la moindre ligne. L'action « copie » évite que Qt
        retire lui-même les lignes sources après un « déplacement » : l'arbre est redessiné
        par le rafraîchissement du panneau."""
        QtGui.QToolTip.hideText()
        point = _point(event)
        target = self.target_at(point)
        keys, self._dragged = self._dragged, []
        event.setDropAction(QtCore.Qt.CopyAction)
        event.accept()
        if keys and self.on_drop is not None and not self.blocked_reason(point):
            self.on_drop(keys, target)

    def _reason(self, target: str | None) -> str:
        return self.judge(self._dragged, target) if self.judge is not None else ""
