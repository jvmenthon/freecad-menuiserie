# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fenêtre « Pièces proches » à la pose d'un assemblage entre deux pièces qui ne se touchent pas
(ADR 0039).

Quand les pièces ne sont écartées que de quelques millimètres, :func:`choose` propose de
**déplacer** une pièce jusqu'au contact, de l'**agrandir** jusqu'au contact ou d'annuler
l'assemblage. Seules les options possibles sont proposées.

La fenêtre est modale et ne peut pas être cliquée hors écran : ``chooser`` est un attribut de
module que les tests remplacent par une fonction ``(écart, options) -> "move" | "grow" | None``.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Final

import FreeCADGui as Gui
from PySide import QtGui

from freecad.menuiserie import api
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.joints import mm_text
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.features.near_gap import GROW, MOVE

__all__ = ["CANCEL", "KEEP", "ask", "choose", "chooser", "message_for", "propose"]

KEEP: Final = "keep"  # pièces déjà en contact, ou trop loin : rien à proposer
CANCEL: Final = "cancel"  # l'utilisateur renonce à l'assemblage

_TITLE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Menuiserie : pièces proches")
_TEXT: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Les pièces ne se touchent pas : {gap} mm les séparent."
)
_MOVE_TEXT: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Déplacer rapproche « {label} » de {gap} mm, jusqu'au contact."
)
_GROW_TEXT: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Agrandir étend « {label} » de {gap} mm, jusqu'au contact."
)
_MOVE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Déplacer")
_GROW: Final = QT_TRANSLATE_NOOP("Menuiserie", "Agrandir")
_CANCEL: Final = QT_TRANSLATE_NOOP("Menuiserie", "Annuler")
_EXPLANATIONS: Final = {MOVE: _MOVE_TEXT, GROW: _GROW_TEXT}


def message_for(gap: float, options: Mapping[str, str]) -> str:
    """Texte de la fenêtre pour un écart de ``gap`` mm ; ``options`` : option → nom de la pièce
    qui bouge ou grandit."""
    text = mm_text(gap)
    lines = [translated(_TEXT, {"gap": text})]
    lines += [
        translated(_EXPLANATIONS[how], {"label": label, "gap": text})
        for how, label in options.items()
    ]
    return lines[0] + "\n\n" + "\n".join(lines[1:]) if len(lines) > 1 else lines[0]


def ask(gap: float, options: Mapping[str, str]) -> str | None:
    """Ouvre la fenêtre modale ; ``"move"``, ``"grow"``, ou ``None`` pour « Annuler », Échap ou
    la fermeture de la fenêtre."""
    box = QtGui.QMessageBox(Gui.getMainWindow())
    box.setIcon(QtGui.QMessageBox.Question)
    box.setWindowTitle(translated(_TITLE))
    box.setText(message_for(gap, options))
    buttons = {}
    if MOVE in options:
        buttons[box.addButton(translated(_MOVE), QtGui.QMessageBox.AcceptRole)] = MOVE
    if GROW in options:
        buttons[box.addButton(translated(_GROW), QtGui.QMessageBox.AcceptRole)] = GROW
    cancel = box.addButton(translated(_CANCEL), QtGui.QMessageBox.RejectRole)
    box.setDefaultButton(next(iter(buttons)))
    box.setEscapeButton(cancel)
    box.exec()
    return buttons.get(box.clickedButton())


chooser: Callable[[float, Mapping[str, str]], str | None] = ask


def choose(gap: float, options: Mapping[str, str]) -> str | None:
    """Choix de l'utilisateur pour un écart de ``gap`` mm, par ``chooser``."""
    return chooser(gap, options)


def propose(host: DocumentObject, guest: DocumentObject) -> str:
    """``MOVE`` ou ``GROW`` si l'utilisateur choisit de rapprocher les pièces, ``CANCEL`` s'il
    renonce, ``KEEP`` s'il n'y a rien à proposer (pièces en contact, éloignées, en biais ou qu'on
    ne peut ni déplacer ni agrandir : la fabrique explique alors pourquoi elles ne se touchent
    pas)."""
    closing = api.closing_options(host, guest)
    if closing is None or not closing.options:
        return KEEP
    return choose(closing.distance, closing.options) or CANCEL
