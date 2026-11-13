# SPDX-License-Identifier: LGPL-2.1-or-later
"""Pièces concernées du panneau « Finition des chants » (issue #5) : une carte par pièce.

Chaque carte porte la couleur de sa pièce (pastille, liseré, arêtes choisies, et la mise en
valeur dans la vue 3D), son nom, le nombre d'arêtes choisies, « Toutes », « Aucune », une croix
pour retirer la pièce et le dessin cliquable de ses arêtes. Le dessin est le patron déplié ou la
boîte en perspective, au choix ; le choix est mémorisé dans les préférences de l'atelier, jamais
dans le document. Tant qu'aucune pièce n'est désignée, une consigne s'affiche.

Les arêtes choisies de chaque pièce sont l'état du panneau ; ``changed`` est appelé à chaque
changement.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from functools import partial
from typing import Final

import FreeCAD as App
from PySide import QtCore, QtGui

from freecad.menuiserie.core.edges import all_edges, face_edges, parse_face
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.features.library import PARAM_PATH
from freecad.menuiserie.features.wood_part_record import dimensions_of
from freecad.menuiserie.gui.task_panels.base import Widget, connect
from freecad.menuiserie.gui.task_panels.edge_diagram import BOX, NET, VIEWS, EdgeDiagram

__all__ = ["PALETTE", "VIEW_KEY", "PieceCard", "PieceList"]

PALETTE: Final = (
    "#3465a4",
    "#4e9a06",
    "#f57900",
    "#75507b",
    "#cc0000",
    "#c4a000",
    "#06989a",
    "#8f5902",
)
VIEW_KEY: Final = "EdgeFinishView"  # dessin préféré, dans les préférences de l'atelier
_LIST: Final = QT_TRANSLATE_NOOP("Menuiserie", "Pièces concernées ({count})")
_HINT: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Cliquez dans la vue 3D une pièce, une face ou une arête à profiler. Chaque pièce cliquée "
    "s'ajoute à la liste.",
)
_MORE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Cliquez une autre pièce dans la vue 3D pour l'ajouter."
)
_VIEW: Final = QT_TRANSLATE_NOOP("Menuiserie", "Dessin")
_VIEW_LABELS: Final = {
    NET: QT_TRANSLATE_NOOP("Menuiserie", "Patron déplié"),
    BOX: QT_TRANSLATE_NOOP("Menuiserie", "Boîte en perspective"),
}
_COUNT: Final = QT_TRANSLATE_NOOP("Menuiserie", "{count} arête(s)")
_ALL: Final = QT_TRANSLATE_NOOP("Menuiserie", "Toutes")
_NONE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Aucune")
_CROSS: Final = QT_TRANSLATE_NOOP("Menuiserie", "✕")
_REMOVE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Retirer cette pièce (ses arêtes ne changent pas)")


def preferred_view() -> str:
    """Dessin mémorisé (patron déplié par défaut)."""
    view = str(App.ParamGet(PARAM_PATH).GetString(VIEW_KEY, NET))
    return view if view in VIEWS else NET


def remember_view(view: str) -> None:
    """Mémorise le dessin choisi."""
    App.ParamGet(PARAM_PATH).SetString(VIEW_KEY, view)


class PieceCard(QtGui.QFrame):  # type: ignore[misc]
    """Carte d'une pièce : arêtes choisies (état), dessin cliquable ; ``changed()`` après
    chaque changement, ``removed(card)`` à la croix."""

    def __init__(
        self,
        part: DocumentObject,
        color: str,
        view: str,
        changed: Callable[[], None],
        removed: Callable[[PieceCard], None] | None,
    ) -> None:
        super().__init__()
        self.part = part
        self.color = color
        self._changed = changed
        self._codes: set[str] = set()
        self.setObjectName(f"piece_{part.Name}")
        self.setFrameShape(QtGui.QFrame.Shape.StyledPanel)
        self.setStyleSheet(
            f"QFrame#piece_{part.Name} {{ border: 1px solid #c8c8c8; "
            f"border-left: 6px solid {color}; border-radius: 4px; }}"
        )
        layout = QtGui.QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 4, 4)
        layout.addLayout(self._header(removed))
        self.diagram = EdgeDiagram(dimensions_of(part), color, view, self.toggle, self.toggle_face)
        layout.addWidget(self.diagram)
        self.refresh()

    def _header(self, removed: Callable[[PieceCard], None] | None) -> Widget:
        row = QtGui.QHBoxLayout()
        dot = QtGui.QLabel()
        dot.setFixedSize(12, 12)
        dot.setStyleSheet(f"background: {self.color}; border-radius: 6px;")
        row.addWidget(dot)
        name = QtGui.QLabel(self.part.Label)
        name.setObjectName("name")
        name.setTextFormat(QtCore.Qt.TextFormat.PlainText)
        font = name.font()
        font.setBold(True)
        name.setFont(font)
        row.addWidget(name)
        row.addStretch()
        self._count = QtGui.QLabel()
        self._count.setObjectName("count")
        row.addWidget(self._count)
        for text, key in ((_ALL, "all"), (_NONE, "none")):
            button = QtGui.QToolButton()
            button.setObjectName(f"shortcut_{key}")
            button.setText(translated(text))
            connect(
                button, "clicked()", partial(self.set_codes, all_codes() if key == "all" else ())
            )
            row.addWidget(button)
        if removed is not None:
            cross = QtGui.QToolButton()
            cross.setObjectName("remove_piece")
            cross.setText(translated(_CROSS))
            cross.setToolTip(translated(_REMOVE))
            connect(cross, "clicked()", partial(removed, self))
            row.addWidget(cross)
        return row

    def codes(self) -> list[str]:
        """Codes des arêtes choisies, dans l'ordre des douze arêtes."""
        return [edge.code for edge in all_edges() if edge.code in self._codes]

    def toggle(self, code: str) -> None:
        """L'arête ``code`` change d'état."""
        self._codes ^= {code}
        self._update()

    def toggle_face(self, face: str) -> None:
        """Les quatre arêtes de la face ``face`` : toutes choisies si l'une ne l'est pas, sinon
        toutes retirées."""
        codes = {edge.code for edge in face_edges(parse_face(face))}
        self._codes = self._codes - codes if codes <= self._codes else self._codes | codes
        self._update()

    def check(self, codes: Iterable[str]) -> None:
        """Arêtes ``codes`` ajoutées (les autres ne changent pas)."""
        self._codes |= set(codes) & set(all_codes())
        self._update()

    def set_codes(self, codes: Iterable[str], *, silently: bool = False) -> None:
        """Arêtes choisies remplacées par ``codes`` ; ``silently`` : sans ``changed``."""
        self._codes = set(codes) & set(all_codes())
        if silently:
            self.refresh()
        else:
            self._update()

    def set_view(self, view: str) -> None:
        """Dessin : patron déplié ou boîte."""
        self.diagram.set_view(view)

    def refresh(self) -> None:
        """Dessin et compte remis d'après les arêtes choisies."""
        self.diagram.show_checked(self._codes)
        self._count.setText(translated(_COUNT, {"count": str(len(self._codes))}))

    def _update(self) -> None:
        self.refresh()
        self._changed()


def all_codes() -> tuple[str, ...]:
    """Les douze codes d'arête."""
    return tuple(edge.code for edge in all_edges())


class PieceList:
    """Les pièces concernées et leurs arêtes ; ``changed()`` après chaque changement."""

    def __init__(self, layout: Widget, changed: Callable[[], None]) -> None:
        self._changed = changed
        self._cards: list[PieceCard] = []
        self.hint = QtGui.QLabel(translated(_HINT))
        self.hint.setObjectName("hint")
        self.hint.setWordWrap(True)
        layout.addWidget(self.hint)
        self._view = preferred_view()
        layout.addWidget(self._view_row())
        self._group = QtGui.QGroupBox()
        self._group.setObjectName("piece_list")
        self._rows = QtGui.QVBoxLayout(self._group)
        layout.addWidget(self._group)
        self._more = QtGui.QLabel(translated(_MORE))
        self._more.setObjectName("more_hint")
        self._more.setWordWrap(True)
        layout.addWidget(self._more)
        self._refresh()

    def _view_row(self) -> Widget:
        """Bascule entre le patron déplié et la boîte en perspective."""
        widget = QtGui.QWidget()
        widget.setObjectName("view_row")
        row = QtGui.QHBoxLayout(widget)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(QtGui.QLabel(translated(_VIEW)))
        self._view_buttons: dict[str, Widget] = {}
        group = QtGui.QButtonGroup(widget)
        group.setExclusive(True)
        for view in VIEWS:
            button = QtGui.QToolButton()
            button.setObjectName(f"view_{view}")
            button.setText(translated(_VIEW_LABELS[view]))
            button.setCheckable(True)
            button.setChecked(view == self._view)
            group.addButton(button)
            connect(button, "clicked()", partial(self.set_view, view))
            row.addWidget(button)
            self._view_buttons[view] = button
        self._button_group = group
        row.addStretch()
        self._view_widget = widget
        return widget

    @property
    def view(self) -> str:
        """Dessin montré par les cartes."""
        return self._view

    def set_view(self, view: str) -> None:
        """Toutes les cartes passent au dessin ``view`` ; le choix est mémorisé."""
        if view not in VIEWS:
            return
        self._view = view
        remember_view(view)
        self._view_buttons[view].setChecked(True)
        for card in self._cards:
            card.set_view(view)

    def cards(self) -> tuple[PieceCard, ...]:
        """Les cartes, dans l'ordre d'ajout."""
        return tuple(self._cards)

    def card_of(self, part: DocumentObject) -> PieceCard | None:
        """Carte de la pièce ``part``, ``None`` si elle n'est pas dans la liste."""
        return next((card for card in self._cards if card.part == part), None)

    def add(self, part: DocumentObject, *, removable: bool = True) -> PieceCard:
        """Carte de ``part`` (créée à la fin de la liste si besoin, couleur suivante)."""
        card = self.card_of(part)
        if card is not None:
            return card
        used = {card.color for card in self._cards}  # une carte retirée libère sa couleur
        free = [color for color in PALETTE if color not in used]
        color = free[0] if free else PALETTE[len(self._cards) % len(PALETTE)]
        card = PieceCard(part, color, self._view, self._changed, self.remove if removable else None)
        self._cards.append(card)
        self._rows.addWidget(card)
        self._refresh()
        return card

    def remove(self, card: PieceCard) -> None:
        """Croix d'une carte : la pièce quitte la liste (ses arêtes de ce panneau aussi)."""
        if card not in self._cards:
            return
        self._cards.remove(card)
        card.hide()
        card.deleteLater()
        self._refresh()
        self._changed()

    def entries(self) -> list[tuple[DocumentObject, list[str]]]:
        """Pièces de la liste et leurs arêtes choisies."""
        return [(card.part, card.codes()) for card in self._cards]

    def parts(self) -> Sequence[DocumentObject]:
        """Pièces de la liste."""
        return [card.part for card in self._cards]

    def _refresh(self) -> None:
        empty = not self._cards
        self.hint.setVisible(empty)
        self._group.setVisible(not empty)
        self._view_widget.setVisible(not empty)
        self._more.setVisible(not empty)
        self._group.setTitle(translated(_LIST, {"count": str(len(self._cards))}))
