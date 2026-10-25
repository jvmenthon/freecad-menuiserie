# SPDX-License-Identifier: LGPL-2.1-or-later
"""Panneau « Définir une distance » (DI-b, critères E2 et E5, ADR 0022).

Le panneau montre les deux éléments choisis, la distance actuelle, un champ « Distance » (unités
et calculs de FreeCAD) et la pièce déplacée (bouton « Inverser »), et, pour deux sommets, la
direction (directe, X, Y ou Z). La pièce suit la saisie en direct (:class:`DistanceMove` écrit
son ``Placement`` sans recalculer le document) ; « OK » relie l'ensemble éventuel et valide la
transaction de la commande, « Annuler » l'abandonne : rien n'a changé (E5).

La case « Garder cette distance » (DI-c, cochée par défaut) crée l'objet ``Distance`` à « OK » ;
elle est grisée, avec une infobulle qui explique pourquoi, si les pièces ne sont pas dans le même
ensemble ou si la direction n'est parallèle à aucun axe de l'ensemble. Une distance refusée (rangée
bloquée par des pièces verrouillées) laisse le panneau ouvert avec « Ne plus garder et appliquer ».
"""

from __future__ import annotations

from functools import partial
from typing import Final

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtGui

from freecad.menuiserie import icon_path
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.text import quoted_value
from freecad.menuiserie.features.distance_keep import KeepError
from freecad.menuiserie.features.distance_move import AXES, DistanceMove
from freecad.menuiserie.features.furniture_bindings import report
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.gui.commands.base import report_refusal
from freecad.menuiserie.gui.task_panels.base import (
    DeletionWatcher,
    TransactionTaskPanel,
    UpdateGuard,
    Widget,
    connect,
    show_panel,
)
from freecad.menuiserie.gui.task_panels.furniture_widgets import (
    message_label,
    quantity_field,
    show_message,
)

__all__ = ["DistanceTaskPanel", "open_panel"]

FORM_NAME: Final = "DistanceTaskPanel"
ICON: Final = "Menuiserie_SetDistance.svg"
TITLE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Définir une distance")
_BETWEEN: Final = QT_TRANSLATE_NOOP("Menuiserie", "Entre : {first} et {second}")
_CURRENT: Final = QT_TRANSLATE_NOOP("Menuiserie", "Distance actuelle : {value}")
_DISTANCE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Distance")
_DISTANCE_TIP: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Distance à obtenir entre les deux éléments, avec une unité (« 320 mm ») ou un calcul "
    "(« 300 mm + 20 mm »). La pièce déplacée suit la saisie.",
)
_MOVED: Final = QT_TRANSLATE_NOOP("Menuiserie", "Pièce déplacée : {label}")
_SWAP: Final = QT_TRANSLATE_NOOP("Menuiserie", "Inverser")
_SWAP_TIP: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Déplace l'autre pièce : celle qui était la référence devient la pièce déplacée."
)
_SWAP_IMPOSSIBLE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "L'autre objet n'est pas une pièce de l'atelier : il ne peut pas être déplacé."
)
_KEEP: Final = QT_TRANSLATE_NOOP("Menuiserie", "Garder cette distance")
_KEEP_TIP: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Crée une Distance dans l'ensemble : les deux pièces gardent cet écart quand l'ensemble "
    "change, et la valeur se règle ensuite comme une cote.",
)
_NO_KEEP_APPLY: Final = QT_TRANSLATE_NOOP("Menuiserie", "Ne plus garder et appliquer")
_NO_KEEP_APPLY_TIP: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Applique la distance sans la garder : les pièces ne se verrouillent pas."
)
_DIRECTION: Final = QT_TRANSLATE_NOOP("Menuiserie", "Direction")
_DIRECT: Final = QT_TRANSLATE_NOOP("Menuiserie", "Directe")
_DIRECTION_TIP: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Directe : distance en ligne droite entre les deux sommets. X, Y ou Z : distance mesurée "
    "sur cet axe du conteneur seul.",
)


class DistanceTaskPanel(TransactionTaskPanel):
    """Panneau de tâche d'une distance à définir ; ``move`` est lu et déplacé par le panneau, qui
    doit être affiché dans la transaction ouverte par la commande."""

    def __init__(self, move: DistanceMove) -> None:
        part = move.moving_part
        watcher = DeletionWatcher(part, Gui.Control.closeDialog)
        super().__init__(part.Document, creating=True, watcher=watcher)
        self._move = move
        self._guard = UpdateGuard()
        self.form: Widget = QtGui.QWidget()
        self.form.setObjectName(FORM_NAME)
        self.form.setWindowIcon(QtGui.QIcon(icon_path(ICON)))
        self.form.setWindowTitle(translated(TITLE))
        self._build()
        self._move.begin()
        with self._guard:
            self._show_current(reset=True)

    # --- Formulaire -----------------------------------------------------------------------

    def _build(self) -> None:
        layout = QtGui.QVBoxLayout(self.form)
        self._between = message_label("betweenLabel")
        self._current = message_label("currentLabel")
        layout.addWidget(self._between)
        layout.addWidget(self._current)
        row = QtGui.QHBoxLayout()
        row.addWidget(QtGui.QLabel(translated(_DISTANCE)))
        self._field = quantity_field("distanceEdit", 0.0)
        self._field.setToolTip(translated(_DISTANCE_TIP))
        row.addWidget(self._field)
        layout.addLayout(row)
        self._keep = QtGui.QCheckBox(translated(_KEEP))
        self._keep.setObjectName("keepCheck")
        self._keep.setChecked(True)
        layout.addWidget(self._keep)
        moved = QtGui.QHBoxLayout()
        self._moved = message_label("movedLabel")
        self._swap = QtGui.QPushButton(translated(_SWAP))
        self._swap.setObjectName("swapButton")
        self._swap.setToolTip(translated(_SWAP_TIP if self._move.can_swap else _SWAP_IMPOSSIBLE))
        moved.addWidget(self._moved, 1)
        moved.addWidget(self._swap)
        layout.addLayout(moved)
        self._direction_row = QtGui.QWidget()
        direction = QtGui.QHBoxLayout(self._direction_row)
        direction.setContentsMargins(0, 0, 0, 0)
        direction.addWidget(QtGui.QLabel(translated(_DIRECTION)))
        self._direction = QtGui.QComboBox()
        self._direction.setObjectName("directionCombo")
        self._direction.setToolTip(translated(_DIRECTION_TIP))
        self._direction.addItem(translated(_DIRECT), "")
        for axis in AXES:
            self._direction.addItem(axis, axis)
        direction.addWidget(self._direction, 1)
        layout.addWidget(self._direction_row)
        self._error = message_label("errorLabel", error=True)
        layout.addWidget(self._error)
        self._no_keep = QtGui.QPushButton(translated(_NO_KEEP_APPLY))
        self._no_keep.setObjectName("noKeepButton")
        self._no_keep.setToolTip(translated(_NO_KEEP_APPLY_TIP))
        self._no_keep.setVisible(False)
        layout.addWidget(self._no_keep)
        layout.addStretch(1)
        connect(self._field, "valueChanged(double)", self._distance_edited)
        connect(self._swap, "clicked()", self._swapped)
        connect(self._direction, "currentIndexChanged(int)", self._direction_chosen)
        connect(self._no_keep, "clicked()", self._apply_without_keeping)

    def _axis(self) -> str | None:
        """Axe choisi pour deux sommets, ``None`` pour « Directe » ou une autre paire."""
        if not self._move.between_points:
            return None
        return str(self._direction.currentData()) or None

    def _show_current(self, *, reset: bool) -> None:
        """Textes d'après les éléments et la pièce déplacée ; ``reset`` : le champ reprend la
        distance actuelle. À appeler sous la garde (pas de saisie réécrite)."""
        first, second = self._move.elements
        params = {"first": first.label(), "second": second.label()}
        self._between.setText(translated(_BETWEEN, params))
        label = quoted_value(self._move.moving_part.Label)
        self._moved.setText(translated(_MOVED, {"label": label}))
        self._swap.setEnabled(self._move.can_swap)
        self._direction_row.setVisible(self._move.between_points)
        self._show_keep()
        try:
            current = self._move.gap(self._axis()).value
        except ValueError as error:
            show_message(self._error, str(error))
            return
        shown = App.Units.Quantity(f"{current} mm").UserString
        self._current.setText(translated(_CURRENT, {"value": shown}))
        if reset:
            self._field.setProperty("rawValue", current)

    def _show_keep(self) -> None:
        """Case « Garder » : active (et cochée) si la distance peut être gardée, sinon grisée
        avec la raison en infobulle."""
        why = self._move.keep_reason(self._axis())
        self._keep.setEnabled(why is None)
        self._keep.setToolTip(why or translated(_KEEP_TIP))
        if why is not None:
            self._keep.setChecked(False)
        elif not self._keep.isEnabled():  # pragma: no cover - jamais atteint
            self._keep.setChecked(True)

    # --- Saisies --------------------------------------------------------------------------

    def _value(self) -> float:
        return round(float(self._field.property("rawValue")), 6)

    def _preview(self) -> bool:
        """La pièce est placée d'après le champ ; un refus s'affiche en rouge (E4)."""
        try:
            self._move.move_to(self._value(), self._axis())
        except (TypeError, ValueError) as error:
            show_message(self._error, str(error))
            return False
        show_message(self._error, "")
        return True

    def _distance_edited(self, *_value: object) -> None:
        if not self._guard.active:
            self._preview()

    def _direction_chosen(self, *_index: object) -> None:
        """Autre direction : le champ reprend la distance actuelle dans cette direction."""
        if self._guard.active:
            return
        with self._guard:
            self._show_current(reset=True)
        self._preview()

    def _swapped(self) -> None:
        """Inverser : l'autre pièce est déplacée, avec la distance déjà saisie."""
        self._move.swap()
        self._move.begin()
        with self._guard:
            self._show_current(reset=False)
        self._preview()

    # --- Fermeture ------------------------------------------------------------------------

    def accept(self) -> bool:
        """« OK » : la pièce est placée, l'ensemble relié et la transaction validée ; un refus
        s'affiche sans fermer le panneau. Une rangée bloquée annule tout (E5)."""
        if not self._preview():
            return False
        keep = self._keep.isEnabled() and self._keep.isChecked()
        try:
            messages = self._move.finish(keep=keep, axis=self._axis())
        except KeepError as error:  # la pièce est revenue : le panneau reste ouvert
            self._move.begin()
            self._preview()
            show_message(self._error, str(error))
            self._no_keep.setVisible(error.blocked)
            return False
        except (TypeError, ValueError) as error:
            report_refusal(str(error))
            return self.reject()
        self._attach_view()
        report(messages)
        window = Gui.getMainWindow()
        if messages and window is not None:
            window.statusBar().showMessage(" ".join(messages))
        return super().accept()

    def _attach_view(self) -> None:
        """ViewProvider de la Distance créée par « OK »."""
        created = self._move.created
        if created is not None:
            from freecad.menuiserie.gui.view_providers.distance import ViewProviderDistance

            ViewProviderDistance(created.ViewObject)

    def _apply_without_keeping(self) -> None:
        """« Ne plus garder et appliquer » : la distance est appliquée sans objet Distance."""
        self._keep.setChecked(False)
        self._no_keep.setVisible(False)
        self.accept()

    def reject(self) -> bool:
        """« Annuler » : la pièce revient et la transaction est abandonnée."""
        self._move.cancel()
        return super().reject()


def open_panel(move: DistanceMove) -> None:
    """Affiche le panneau de ``move`` dans la transaction ouverte par la commande ; une
    exception l'abandonne."""
    show_panel(partial(DistanceTaskPanel, move))
