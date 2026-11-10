# SPDX-License-Identifier: LGPL-2.1-or-later
"""Double-clic d'une ligne du panneau « Structure » pendant qu'une tâche est ouverte (ADR 0046).

La décision est dans ``core/task_switch`` ; ce module l'applique. Sans modification, la tâche de
l'atelier est fermée sans rien changer, puis la pièce s'ouvre. Avec des modifications, une boîte
propose « Appliquer » (la tâche est validée comme avec « OK »), « Annuler » (elle est abandonnée
comme avec « Annuler » : rien n'est conservé, Ctrl+Z n'a rien à défaire) ou de poursuivre (Échap,
fermeture de la boîte : on reste sur la tâche). Une tâche d'un autre atelier est refusée avec un
message. L'ouverture suit la fermeture d'un tour de boucle d'évènements : FreeCAD a alors rendu
la vue des tâches.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Final

import FreeCADGui as Gui
from PySide import QtCore, QtGui

from freecad.menuiserie.core.structure_actions import BUSY
from freecad.menuiserie.core.task_switch import (
    APPLY_LABEL,
    ASK_TEXT,
    ASK_TITLE,
    DISCARD_LABEL,
    FOREIGN_TASK,
    STAY_LABEL,
    Action,
    Choice,
    plan,
    resolve,
)
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.gui.commands.base import report_refusal
from freecad.menuiserie.gui.display_layers import object_alive
from freecad.menuiserie.gui.task_panels import active

__all__ = ["ASK_BOX_NAME", "ask_user", "chooser", "switch_to"]

ASK_BOX_NAME: Final = "MenuiserieTaskSwitchBox"
_STATUS_MS: Final = 4000


def ask_user() -> Choice | None:
    """Boîte modale (texte brut) : appliquer, annuler les modifications ou poursuivre. Échap et la
    fermeture de la boîte valent « poursuivre »."""
    box = QtGui.QMessageBox(Gui.getMainWindow())
    box.setObjectName(ASK_BOX_NAME)
    box.setIcon(QtGui.QMessageBox.Question)
    box.setWindowTitle(translated(ASK_TITLE))
    box.setTextFormat(QtCore.Qt.PlainText)
    box.setText(translated(ASK_TEXT))
    apply = box.addButton(translated(APPLY_LABEL), QtGui.QMessageBox.AcceptRole)
    discard = box.addButton(translated(DISCARD_LABEL), QtGui.QMessageBox.DestructiveRole)
    stay = box.addButton(translated(STAY_LABEL), QtGui.QMessageBox.RejectRole)
    box.setDefaultButton(stay)
    box.setEscapeButton(stay)
    box.exec()
    clicked = box.clickedButton()
    return {apply: Choice.APPLY, discard: Choice.DISCARD}.get(clicked, Choice.STAY)


# Fonction de choix en service : les tests la remplacent (hors écran, une boîte modale ne se clique
# pas). Lue à l'appel.
chooser: Callable[[], Choice | None] = ask_user


def switch_to(obj: Any, open_panel: Callable[[Any], bool]) -> None:
    """Ouvre le panneau de ``obj`` (par ``open_panel``) en réglant d'abord la tâche en cours."""
    panel = active.current()
    action = plan(
        task_open=bool(Gui.Control.activeDialog()),
        ours=panel is not None,
        creating=panel is not None and panel.creating,
        changed=panel is not None and panel.has_changes(),
    )
    if action is Action.ASK:
        action = resolve(chooser())
    _run(action, panel, obj, open_panel)


def _run(
    action: Action, panel: active.ActivePanel | None, obj: Any, open_panel: Callable[[Any], bool]
) -> None:
    if action is Action.REFUSE:
        report_refusal(translated(FOREIGN_TASK))
    elif action is Action.OPEN:
        _open(obj, open_panel)
    elif panel is not None and action is Action.DISCARD_THEN_OPEN:
        panel.reject()
        _open_later(obj, open_panel)
    elif panel is not None and action is Action.APPLY_THEN_OPEN:
        _apply_then_open(panel, obj, open_panel)


def _apply_then_open(
    panel: active.ActivePanel, obj: Any, open_panel: Callable[[Any], bool]
) -> None:
    """« OK » de la tâche ; refusé (erreur à corriger), on reste sur la tâche."""
    if panel.accept() and panel.closed:
        _open_later(obj, open_panel)


def _open_later(obj: Any, open_panel: Callable[[Any], bool]) -> None:
    def run() -> None:
        _open(obj, open_panel)

    QtCore.QTimer.singleShot(0, run)


def _open(obj: Any, open_panel: Callable[[Any], bool]) -> None:
    if not object_alive(obj):
        return  # supprimé avec la tâche abandonnée (création)
    if not open_panel(obj) and Gui.Control.activeDialog():
        Gui.getMainWindow().statusBar().showMessage(translated(BUSY), _STATUS_MS)
