# SPDX-License-Identifier: LGPL-2.1-or-later
"""Carte d'une pièce dessinée dans le panneau « Finition des chants » (ADR 0063, maquette A).

Une pièce qui n'est pas une boîte n'a pas de patron : sa carte liste ses arêtes choisies, une
ligne par arête, chacune de **sa propre couleur** (pastille de la ligne et trait dans la vue 3D),
avec sa longueur, l'angle de ses faces et une **croix rouge** qui la retire seule. Une arête qui
ne peut pas recevoir de profil (courbe, rentrante…) reste grisée avec sa raison ; une arête
perdue après une modification de la pièce est en rouge, à choisir à nouveau.

Même contrat que :class:`~.edge_targets.PieceCard` : ``codes()``, ``check()``, ``set_codes()``,
``changed()`` après chaque changement. Les « codes » sont ici des noms natifs (``"Edge7"``).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from functools import partial
from typing import Any, Final

from PySide import QtCore, QtGui

from freecad.menuiserie.core.edges import EdgeFamily, frame_refusal
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.features.edge_frames import (
    MAX_NATIVE_EDGES,
    NativeEdge,
    edge_index,
    edge_label,
    native_edge,
)
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.features.shaped_part import base_shape_of
from freecad.menuiserie.gui.task_panels.base import Widget, connect

__all__ = ["EDGE_PALETTE", "NativeCard", "card_layout", "card_title", "remove_button"]

# Une couleur par arête (spécification C8), bien distinctes entre elles et lisibles sur le bois.
EDGE_PALETTE: Final = (
    "#e41a1c",
    "#377eb8",
    "#4daf4a",
    "#984ea3",
    "#ff7f00",
    "#17becf",
    "#a65628",
    "#f781bf",
    "#bcbd22",
    "#1b1b8f",
)
GREY: Final = "#b0b0b0"
_COUNT: Final = QT_TRANSLATE_NOOP("Menuiserie", "{count} arête(s)")
_EDGE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Arête {edge}")
_SIZE: Final = QT_TRANSLATE_NOOP("Menuiserie", "{length} mm · {angle}°")
_LOST: Final = QT_TRANSLATE_NOOP("Menuiserie", "perdue : cliquez-la à nouveau dans la vue 3D")
_CROSS: Final = QT_TRANSLATE_NOOP("Menuiserie", "✕")
_REMOVE_EDGE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Retirer cette arête")
_REMOVE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Retirer cette pièce (ses arêtes ne changent pas)")
_EMPTY: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Cliquez une face (tout son contour) ou une arête (avec ses arêtes tangentes ; Alt+clic : "
    "elle seule) de cette pièce dans la vue 3D.",
)


def _number(value: float) -> str:
    return f"{round(value, 1):g}".replace(".", ",")


def card_layout(card: QtGui.QFrame, part: DocumentObject, color: str) -> Widget:
    """Cadre d'une carte de pièce (liseré à la couleur de la pièce) et sa mise en page."""
    card.setObjectName(f"piece_{part.Name}")
    card.setFrameShape(QtGui.QFrame.Shape.StyledPanel)
    card.setStyleSheet(
        f"QFrame#piece_{part.Name} {{ border: 1px solid #c8c8c8; "
        f"border-left: 6px solid {color}; border-radius: 4px; }}"
    )
    layout = QtGui.QVBoxLayout(card)
    layout.setContentsMargins(8, 4, 4, 4)
    return layout


def card_title(part: DocumentObject, color: str) -> tuple[Widget, Widget]:
    """En-tête d'une carte : pastille, nom de la pièce en gras, compte (à remplir) ; rend la
    ligne et l'étiquette du compte."""
    row = QtGui.QHBoxLayout()
    dot = QtGui.QLabel()
    dot.setFixedSize(12, 12)
    dot.setStyleSheet(f"background: {color}; border-radius: 6px;")
    row.addWidget(dot)
    name = QtGui.QLabel(part.Label)
    name.setObjectName("name")
    name.setTextFormat(QtCore.Qt.TextFormat.PlainText)
    font = name.font()
    font.setBold(True)
    name.setFont(font)
    row.addWidget(name)
    row.addStretch()
    count = QtGui.QLabel()
    count.setObjectName("count")
    count.setTextFormat(QtCore.Qt.TextFormat.PlainText)
    row.addWidget(count)
    return row, count


def remove_button(removed: Callable[[Any], None], card: Any) -> Widget:
    """Croix qui retire la pièce de la liste (ses arêtes ne changent pas)."""
    cross = QtGui.QToolButton()
    cross.setObjectName("remove_piece")
    cross.setText(translated(_CROSS))
    cross.setToolTip(translated(_REMOVE))
    connect(cross, "clicked()", partial(removed, card))
    return cross


class NativeCard(QtGui.QFrame):  # type: ignore[misc]
    """Carte d'une pièce dessinée : arêtes natives choisies (état, dans l'ordre des clics),
    une ligne colorée par arête ; ``changed()`` après chaque changement, ``removed(card)`` à
    la croix de la pièce."""

    def __init__(
        self,
        part: DocumentObject,
        color: str,
        changed: Callable[[], None],
        removed: Callable[[NativeCard], None] | None,
    ) -> None:
        super().__init__()
        self.part = part
        self.part_name: str = part.Name
        self.color = color
        self._changed = changed
        self._names: list[str] = []
        self._shape: Any = base_shape_of(part)
        self._edges: dict[str, NativeEdge | None] = {}
        layout = card_layout(self, part, color)
        row, self._count = card_title(part, color)
        if removed is not None:
            row.addWidget(remove_button(removed, self))
        layout.addLayout(row)
        self._empty = QtGui.QLabel(translated(_EMPTY))
        self._empty.setObjectName("empty_hint")
        self._empty.setWordWrap(True)
        self._empty.setTextFormat(QtCore.Qt.TextFormat.PlainText)
        layout.addWidget(self._empty)
        self._rows = QtGui.QVBoxLayout()
        self._rows.setSpacing(0)
        layout.addLayout(self._rows)
        self.refresh()

    # --- État -----------------------------------------------------------------------------

    def _read(self, name: str) -> NativeEdge | None:
        """Arête lue (mémorisée) ; ``None`` pour une arête perdue."""
        if name not in self._edges:
            index = edge_index(name)
            if index is None or index > len(self._shape.Edges):
                self._edges[name] = None
            else:
                self._edges[name] = native_edge(self._shape, index)
        return self._edges[name]

    def codes(self) -> list[str]:
        """Noms des arêtes choisies qui peuvent recevoir un profil, dans l'ordre des clics."""
        return [name for name in self._names if self._usable(name)]

    def listed(self) -> list[str]:
        """Toutes les arêtes de la liste, refusées et perdues comprises."""
        return list(self._names)

    def _usable(self, name: str) -> bool:
        edge = self._read(name)
        # Arête lue, saillante et d'angle accepté (30° à 150°) : le chanfrein, qui va à tout
        # angle, sert d'étalon ; une famille à angle droit est refusée à l'aperçu.
        return (
            edge is not None
            and edge.frame is not None
            and frame_refusal(edge.frame, EdgeFamily.CHAMFER) is None
        )

    def edge_colors(self) -> dict[str, str]:
        """Couleur de chaque arête utilisable, la même dans la liste et dans la vue 3D."""
        return {name: self._color_of(name) for name in self.codes()}

    def _color_of(self, name: str) -> str:
        if not self._usable(name):
            return GREY
        return EDGE_PALETTE[self.codes().index(name) % len(EDGE_PALETTE)]

    def check(self, names: Iterable[str]) -> None:
        """Arêtes désignées par un clic : ajoutées à la fin de la liste ; si toutes y sont déjà
        (second clic sur la même face ou arête), elles sont retirées."""
        names = [name for name in dict.fromkeys(names) if edge_index(name.lstrip("?"))]
        if not names:
            return
        if all(name in self._names for name in names):
            self._names = [name for name in self._names if name not in names]
        else:
            room = MAX_NATIVE_EDGES - len(self._names)
            self._names += [name for name in names if name not in self._names][: max(room, 0)]
        self._update()

    def remove_edge(self, name: str) -> None:
        """Croix rouge d'une ligne : cette arête seule quitte la liste."""
        if name in self._names:
            self._names.remove(name)
            self._update()

    def set_codes(self, codes: Iterable[str], *, silently: bool = False) -> None:
        """Arêtes remplacées par ``codes`` (noms natifs, perdus compris : ``"?Edge17"``) ;
        ``silently`` : sans ``changed``."""
        self._names = [str(name) for name in dict.fromkeys(codes)][:MAX_NATIVE_EDGES]
        if silently:
            self.refresh()
        else:
            self._update()

    def set_view(self, view: str) -> None:
        """Sans dessin de boîte : rien à basculer."""
        del view

    # --- Affichage ------------------------------------------------------------------------

    def refresh(self) -> None:
        """Lignes et compte remis d'après les arêtes choisies."""
        while self._rows.count():
            item = self._rows.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
        for name in self._names:
            self._rows.addWidget(self._row(name))
        self._empty.setVisible(not self._names)
        self._count.setText(translated(_COUNT, {"count": str(len(self.codes()))}))

    def _row(self, name: str) -> Widget:
        edge = self._read(name)
        index = edge_index(name.lstrip("?")) or 0
        widget = QtGui.QWidget()
        widget.setObjectName(f"edge_{name.lstrip('?')}")
        row = QtGui.QHBoxLayout(widget)
        row.setContentsMargins(0, 2, 0, 2)
        dot = QtGui.QLabel()
        dot.setObjectName("edge_color")
        dot.setFixedSize(10, 10)
        color = self._color_of(name)
        dot.setStyleSheet(f"background: {color}; border-radius: 5px;")
        row.addWidget(dot)
        label = QtGui.QLabel(translated(_EDGE, {"edge": edge_label(index)}))
        label.setObjectName("edge_name")
        label.setTextFormat(QtCore.Qt.TextFormat.PlainText)
        row.addWidget(label)
        row.addStretch()
        detail = QtGui.QLabel(self._detail(edge))
        detail.setObjectName("edge_detail")
        detail.setTextFormat(QtCore.Qt.TextFormat.PlainText)
        detail.setWordWrap(True)
        row.addWidget(detail)
        if edge is None:
            for part in (label, detail):
                part.setStyleSheet("color: #c62f3a;")
        elif not self._usable(name):
            for part in (label, detail):
                part.setStyleSheet(f"color: {GREY};")
        cross = QtGui.QToolButton()
        cross.setObjectName("remove_edge")
        cross.setText(translated(_CROSS))
        cross.setToolTip(translated(_REMOVE_EDGE))
        cross.setStyleSheet("QToolButton { color: #c62f3a; font-weight: bold; border: none; }")
        connect(cross, "clicked()", partial(self.remove_edge, name))
        row.addWidget(cross)
        return widget

    @staticmethod
    def _detail(edge: NativeEdge | None) -> str:
        if edge is None:
            return translated(_LOST)
        if edge.frame is None:
            return edge.refusal or ""
        refusal = frame_refusal(edge.frame, EdgeFamily.CHAMFER)
        if refusal is not None:
            return str(refusal)
        return translated(
            _SIZE, {"length": _number(edge.length), "angle": _number(edge.frame.angle)}
        )

    def _update(self) -> None:
        self.refresh()
        self._changed()
