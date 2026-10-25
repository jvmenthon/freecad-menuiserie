# SPDX-License-Identifier: LGPL-2.1-or-later
"""Refus d'une rangée bloquée et déverrouillage des pièces (ADR 0019, critères G2 et G3).

Composant partagé par le panneau de l'ensemble (cote refusée) et celui de la pièce de bois
(épaisseur refusée) : le refus en rouge, puis, si des pièces verrouillées en sont la cause, une
case à cocher par pièce (cochées par défaut) et le bouton « Déverrouiller et appliquer ». Le
panneau décide de ce que fait le bouton (:class:`UnlockBox` lui remet les pièces cochées) ;
« OK » est rendu inactif tant que le refus dure.

Les widgets ne touchent jamais le document. Les cases sont créées à la demande puis réutilisées
(masquées quand elles ne servent plus), jamais détruites : pas d'enveloppe PySide périmée.
Noms d'objets Qt pour les vérifications d'interface : ``refusalLabel``, ``unlockPieces``,
``unlock_<Name>`` (une case par pièce), ``unlockButton``.
"""

from __future__ import annotations

import weakref
from collections.abc import Callable, Sequence
from typing import Final

from PySide import QtGui

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.furniture_locks import refusal_of
from freecad.menuiserie.features.furniture_view import shown_object
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.gui.task_panels.base import Widget, connect
from freecad.menuiserie.gui.task_panels.furniture_widgets import message_label, show_message

_TITLE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Pièces aux cotes fixes à déverrouiller :")
_APPLY: Final = QT_TRANSLATE_NOOP("Menuiserie", "Déverrouiller et appliquer")
_APPLY_TIP: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Déverrouille les pièces cochées, relie l'ensemble puis applique la valeur refusée.",
)
_PIECE_TIP: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Cochée : la pièce perd ses cotes fixes et peut s'adapter."
)


class OkGate:
    """Bouton « OK » du panneau de tâche, inactif pendant un refus. Les boutons sont passés par
    FreeCAD à l'affichage (``modifyStandardButtons``) et gardés ici : l'enveloppe Python de la
    boîte doit vivre pour que celle de « OK » reste valide."""

    def __init__(self) -> None:
        self._buttons: Widget = None
        self._blocked = False

    def attach(self, box: Widget) -> None:
        """Boîte des boutons du panneau."""
        self._buttons = box
        self.update(self._blocked)

    def update(self, blocked: bool) -> None:
        """« OK » actif sauf si ``blocked`` (boîte détruite par FreeCAD : oubliée)."""
        self._blocked = blocked
        try:
            button = self._buttons.button(QtGui.QDialogButtonBox.Ok) if self._buttons else None
            if button is not None:
                button.setEnabled(not blocked)
        except RuntimeError:
            self._buttons = None


class UnlockBox:
    """Refus, cases des pièces verrouillées et bouton « Déverrouiller et appliquer ».

    ``on_apply`` (méthode du panneau) reçoit les pièces cochées ; elle est gardée par une
    référence faible : sans cycle panneau ↔ composant, le panneau et les enveloppes PySide de ses
    widgets disparaissent dès sa fermeture, avant que Qt ne réutilise leurs adresses (sinon
    ``kindCombo`` d'un panneau suivant peut être vu comme un ``QBoxLayout``). :meth:`refuse`
    affiche un refus (et ses pièces) et rend « OK » inactif, :meth:`clear` efface tout."""

    def __init__(
        self, layout: Widget, on_apply: Callable[[Sequence[DocumentObject]], None]
    ) -> None:
        self._on_apply = weakref.WeakMethod(on_apply)
        self._gate = OkGate()
        self._pieces: tuple[DocumentObject, ...] = ()
        self._boxes: list[Widget] = []
        self._refused = False
        self.label = message_label("refusalLabel", error=True)
        layout.addWidget(self.label)
        self._host = QtGui.QWidget()
        self._host.setObjectName("unlockPieces")
        self._column = QtGui.QVBoxLayout(self._host)
        self._column.setContentsMargins(0, 0, 0, 0)
        self._column.addWidget(QtGui.QLabel(translated(_TITLE)))
        self._button = QtGui.QPushButton(translated(_APPLY))
        self._button.setObjectName("unlockButton")
        self._button.setToolTip(translated(_APPLY_TIP))
        connect(self._button, "clicked()", self._apply)
        self._column.addWidget(self._button)
        layout.addWidget(self._host)
        self._show("", ())

    @property
    def refused(self) -> bool:
        """Vrai tant qu'un refus est affiché."""
        return self._refused

    def attach_buttons(self, box: Widget) -> None:
        """Boutons du panneau de tâche (``modifyStandardButtons``)."""
        self._gate.attach(box)

    def refuse(self, error: ValueError) -> None:
        """Affiche le refus ``error`` et, s'il vient de pièces verrouillées, leurs cases."""
        text, pieces = refusal_of(error)
        self._show(text, pieces)

    def clear(self) -> None:
        """Plus de refus : libellé, cases et bouton disparaissent."""
        self._show("", ())

    def checked(self) -> list[DocumentObject]:
        """Pièces dont la case est cochée."""
        return [p for p, box in zip(self._pieces, self._boxes, strict=False) if box.isChecked()]

    def _show(self, text: str, pieces: tuple[DocumentObject, ...]) -> None:
        self._refused = bool(text)
        show_message(self.label, text)
        self._set_pieces(pieces if text else ())
        self._host.setVisible(bool(self._pieces))
        self._gate.update(self._refused)

    def _set_pieces(self, pieces: tuple[DocumentObject, ...]) -> None:
        """Une case par pièce, cochée ; les cases d'une même liste de pièces gardent leur
        état (un refus qui se répète ne les recoche pas)."""
        same = [p.Name for p in pieces] == [p.Name for p in self._pieces]
        self._pieces = pieces
        if same:
            return
        for index, piece in enumerate(pieces):
            box = self._box(index)
            box.setText(str(shown_object(piece).Label))
            box.setObjectName(f"unlock_{piece.Name}")
            box.setChecked(True)
        for index, box in enumerate(self._boxes):
            box.setVisible(index < len(pieces))
        self._update_button()

    def _box(self, index: int) -> Widget:
        """Case numéro ``index``, créée au besoin avant le bouton."""
        while len(self._boxes) <= index:
            box = QtGui.QCheckBox()
            box.setToolTip(translated(_PIECE_TIP))
            self._column.insertWidget(1 + len(self._boxes), box)
            connect(box, "toggled(bool)", self._update_button)
            self._boxes.append(box)
        return self._boxes[index]

    def _update_button(self, *_checked: object) -> None:
        """Le bouton n'a de sens qu'avec au moins une pièce cochée."""
        self._button.setEnabled(bool(self.checked()))

    def _apply(self) -> None:
        on_apply = self._on_apply()
        if on_apply is not None:
            on_apply(self.checked())
