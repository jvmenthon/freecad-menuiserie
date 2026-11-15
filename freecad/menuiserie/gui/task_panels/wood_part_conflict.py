# SPDX-License-Identifier: LGPL-2.1-or-later
"""Encadré « où ajouter l'épaisseur ? » du panneau de la pièce de bois (ADR 0060, maquette C).

Quand l'épaisseur saisie d'une pièce isolée défait un de ses assemblages (queue d'aronde plus à
fleur, par exemple), l'encadré apparaît sous les cotes, sans fenêtre : vers l'intérieur (la pièce
reste à fleur), vers l'extérieur en prolongeant l'autre pièce, ou revenir à l'ancienne épaisseur.
Le premier choix possible est coché et appliqué aussitôt (aperçu en direct) ; un choix impossible
est grisé, avec sa raison en dessous. Le document est écrit par
:class:`~freecad.menuiserie.features.thickness_choice.ThicknessEdit` ; ce composant ne fait que
montrer les choix et transmettre celui qui est coché.

Les widgets sont créés une fois et réutilisés (jamais détruits). Noms d'objets Qt pour les
vérifications d'interface : ``thicknessConflict``, ``conflictTitle``, ``conflictQuestion``,
``conflict_<choix>`` (bouton radio) et ``conflictReason_<choix>``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Final
from weakref import WeakMethod, ref

from PySide import QtGui

from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.furniture_bindings import report
from freecad.menuiserie.features.thickness_choice import (
    Choice,
    Conflict,
    ThicknessEdit,
    UnavailableError,
)
from freecad.menuiserie.gui.task_panels.base import Widget, connect
from freecad.menuiserie.gui.task_panels.furniture_widgets import message_label, show_message

_BOX_STYLE: Final = (
    "QFrame#thicknessConflict { background: #fdf6dc; border: 1px solid #e0a800; "
    "border-radius: 2px; }"
)
_CHOICES: Final = (Choice.OTHER_SIDE, Choice.EXTEND, Choice.REVERT)


class ConflictBox:
    """Encadré des choix d'épaisseur de la pièce ``obj``, ajouté à ``layout``. ``revert`` (méthode
    du panneau) remet l'ancienne épaisseur dans le champ ; elle est gardée par une référence
    faible (pas de cycle panneau ↔ composant) : ce doit être une méthode liée."""

    def __init__(self, layout: Widget, obj: DocumentObject, revert: Callable[[float], None]):
        self._obj = obj
        self._revert = WeakMethod(revert)
        self._edit: ThicknessEdit | None = None
        self._value = 0.0
        self.frame = QtGui.QFrame()
        self.frame.setObjectName("thicknessConflict")
        self.frame.setStyleSheet(_BOX_STYLE)
        column = QtGui.QVBoxLayout(self.frame)
        self._title = message_label("conflictTitle")
        bold = self._title.font()
        bold.setBold(True)
        self._title.setFont(bold)
        self._question = message_label("conflictQuestion", hint=True)
        column.addWidget(self._title)
        column.addWidget(self._question)
        self._group = QtGui.QButtonGroup(self.frame)
        self._radios: dict[Choice, Widget] = {}
        self._reasons: dict[Choice, Widget] = {}
        for choice in _CHOICES:
            radio = QtGui.QRadioButton()
            radio.setObjectName(f"conflict_{choice.value}")
            self._group.addButton(radio)
            connect(radio, "clicked()", _weak_choice(self, choice))
            reason = message_label(f"conflictReason_{choice.value}", hint=True)
            reason.setContentsMargins(24, 0, 0, 0)
            column.addWidget(radio)
            column.addWidget(reason)
            self._radios[choice] = radio
            self._reasons[choice] = reason
        layout.addWidget(self.frame)
        self.frame.setVisible(False)

    @property
    def shown(self) -> bool:
        """Vrai tant que l'encadré est affiché."""
        return not self.frame.isHidden()

    def edit(self, value: float) -> None:
        """:meth:`_edit_now` ; une erreur (pièce supprimée ou annulée entre-temps, document
        illisible) est écrite dans la vue rapport et l'encadré est oublié."""
        self._safely(lambda: self._edit_now(value))

    def _safely(self, action: Callable[[], None]) -> None:
        try:
            action()
        except (ValueError, ReferenceError, RuntimeError) as error:
            report([str(error)])
            self.forget()

    def _edit_now(self, value: float) -> None:
        """Épaisseur ``value`` saisie : écrite telle quelle si elle ne défait aucun assemblage,
        sinon l'encadré s'affiche et le premier choix possible est appliqué. Tant que l'encadré
        est affiché, chaque saisie repart de l'état d'avant la première (:class:`ThicknessEdit`)."""
        if self._edit is None:
            self._edit = ThicknessEdit(self._obj)
        self._value = value
        conflict = self._edit.conflict(value)
        if conflict is None:  # écrite telle quelle : point de départ de la saisie suivante
            report(self._edit.apply(value, Choice.AS_TYPED))
            self.forget()
            return
        self._show(conflict)
        preferred = conflict.preferred()
        if preferred is not None:
            self._radios[preferred].setChecked(True)
            self._apply(preferred)
        else:
            self._edit.apply(value, Choice.AS_TYPED)  # la saisie reste visible, encadré en tête

    def forget(self) -> None:
        """Autre saisie (cote, rotation, glissement, matériau) : l'état écrit devient le point de
        départ des saisies d'épaisseur suivantes ; l'encadré disparaît."""
        self._edit = None
        self.frame.setVisible(False)

    def _show(self, conflict: Conflict) -> None:
        show_message(self._title, conflict.title)
        show_message(self._question, conflict.question)
        self._group.setExclusive(False)  # aucun bouton coché tant qu'aucun choix n'est fait
        for option in conflict.options:
            radio = self._radios[option.choice]
            radio.setChecked(False)
            radio.setText(option.text)
            radio.setEnabled(option.reason is None)
            show_message(self._reasons[option.choice], option.reason or "")
        self._group.setExclusive(True)
        self.frame.setVisible(True)

    def chosen(self, choice: Choice) -> None:
        """Bouton ``choice`` cliqué : appliqué ; « Revenir » remet l'ancienne épaisseur. Une
        erreur est écrite dans la vue rapport (:meth:`_safely`)."""
        self._safely(lambda: self._choose(choice))

    def _choose(self, choice: Choice) -> None:
        if self._edit is None:
            return
        if choice is Choice.REVERT:
            old = self._edit.old
            self._edit.apply(old, Choice.REVERT)
            self.frame.setVisible(False)
            revert = self._revert()
            if revert is not None:
                revert(old)
            return
        self._apply(choice)

    def _apply(self, choice: Choice) -> None:
        if self._edit is None:
            return
        try:
            report(self._edit.apply(self._value, choice))
        except UnavailableError as error:  # le document a changé depuis l'essai (état rendu)
            show_message(self._reasons[choice], str(error))
            self._radios[choice].setEnabled(False)


def _weak_choice(box: ConflictBox, choice: Choice) -> Callable[[], None]:
    """Rappel du bouton ``choice`` qui ne garde pas ``box`` en vie."""
    target = ref(box)

    def call() -> None:
        current = target()
        if current is not None:
            current.chosen(choice)

    return call
