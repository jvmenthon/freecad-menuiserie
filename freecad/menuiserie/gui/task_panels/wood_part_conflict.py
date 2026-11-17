# SPDX-License-Identifier: LGPL-2.1-or-later
"""Encadré « où ajouter l'épaisseur ? » du panneau de la pièce de bois (ADR 0060, maquette C).

Quand l'épaisseur saisie d'une pièce assemblée change (pièce d'ensemble comprise, jv
2026-11-17 : l'ensemble est relié d'après le résultat à la fin), l'encadré apparaît sous les cotes,
sans fenêtre : vers l'intérieur (la pièce reste à fleur), vers l'extérieur en prolongeant l'autre
pièce, ou revenir à l'ancienne épaisseur ; si aucun assemblage n'est défait (tenon qui suit la
face, par exemple), « Laisser en l'état » vient en tête (jv, 2026-11-15).
Le premier choix possible est coché et appliqué aussitôt (aperçu en direct) ; un choix impossible
est grisé, avec sa raison en dessous. Si aucun choix ne tient (saisie transitoire comme « 2 »
avant « 22 », ou trop mince pour l'assemblage), rien n'est écrit et « OK » est inactif. Le
document est écrit par :class:`~freecad.menuiserie.features.thickness_choice.ThicknessEdit` ; ce
composant ne fait que montrer les choix et transmettre celui qui est coché.

Les widgets sont créés une fois et réutilisés (jamais détruits). Noms d'objets Qt pour les
vérifications d'interface : ``thicknessConflict``, ``conflictTitle``, ``conflictQuestion``,
``conflict_<choix>`` (bouton radio) et ``conflictReason_<choix>``.
"""

from __future__ import annotations

import traceback
from collections.abc import Callable
from typing import Final
from weakref import WeakMethod, ref

import FreeCAD as App
from PySide import QtGui

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.furniture_bindings import report
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.features.thickness_choice import (
    Choice,
    Conflict,
    ThicknessEdit,
    UnavailableError,
)
from freecad.menuiserie.gui.task_panels.base import Widget, connect, recompute_preview
from freecad.menuiserie.gui.task_panels.furniture_widgets import message_label, show_message
from freecad.menuiserie.gui.task_panels.unlock_widgets import OkGate

_BOX_STYLE: Final = (  # fond clair : texte foncé imposé, lisible aussi avec un thème sombre
    "QFrame#thicknessConflict { background: #fdf6dc; border: 1px solid #e0a800; "
    "border-radius: 2px; } "
    "QFrame#thicknessConflict QLabel, QFrame#thicknessConflict QRadioButton { color: #222; } "
    "QFrame#thicknessConflict QRadioButton:disabled { color: #8a8a8a; }"
)
_NOT_APPLIED: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Aucun choix ne garde l'assemblage à cette épaisseur : elle n'est pas appliquée.",
)
_GATE_SOURCE: Final = "thicknessConflict"
_ABANDONED: Final = QT_TRANSLATE_NOOP("Menuiserie", "Choix d'épaisseur abandonné : {error}")
_CHOICES: Final = (Choice.AS_TYPED, Choice.OTHER_SIDE, Choice.EXTEND, Choice.REVERT)


class ConflictBox:
    """Encadré des choix d'épaisseur de la pièce ``obj``, ajouté à ``layout``. ``revert`` (méthode
    du panneau) remet l'ancienne épaisseur dans le champ, ``preview`` recalcule l'aperçu 3D de la
    pièce après un choix cliqué (les autres pièces écrites sont recalculées ici). Elles sont
    gardées par des références faibles (pas de cycle panneau ↔ composant) : ce doivent être des
    méthodes liées."""

    def __init__(
        self,
        layout: Widget,
        obj: DocumentObject,
        revert: Callable[[float], None],
        preview: Callable[[], None],
        gate: OkGate,
    ):
        self._obj = obj
        self._revert = WeakMethod(revert)
        self._preview = WeakMethod(preview)
        self._edit: ThicknessEdit | None = None
        self._value = 0.0
        self._gate = gate  # « OK » partagé avec le refus d'épaisseur (UnlockBox)
        self._blocked = False
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
        self._not_applied = message_label("conflictNotApplied", error=True)
        column.addWidget(self._not_applied)
        layout.addWidget(self.frame)
        self.frame.setVisible(False)
        show_message(self._not_applied, "")

    @property
    def shown(self) -> bool:
        """Vrai tant que l'encadré est affiché."""
        return not self.frame.isHidden()

    @property
    def blocked(self) -> bool:
        """Vrai tant qu'aucun choix ne tient à l'épaisseur saisie : rien n'est écrit et « OK » est
        inactif."""
        return self._blocked

    def _block(self, blocked: bool) -> None:
        self._blocked = blocked
        show_message(self._not_applied, translated(_NOT_APPLIED) if blocked else "")
        self._gate.update(blocked, _GATE_SOURCE)

    def edit(self, value: float) -> None:
        """:meth:`_edit_now` ; une erreur (pièce supprimée ou annulée entre-temps, document
        illisible) est écrite dans la vue rapport et l'encadré est oublié."""
        self._safely(lambda: self._edit_now(value))

    def _safely(self, action: Callable[[], None]) -> bool:
        """``action`` ; toute erreur (rappel d'un signal Qt : rien ne doit en sortir), même une
        erreur de programmation, est écrite dans la vue rapport (pile complète dans le journal),
        le champ remontre l'épaisseur du document et l'encadré est oublié. Vrai si tout s'est
        bien passé."""
        try:
            action()
        except Exception as error:  # pylint: disable=broad-exception-caught
            report([translated(_ABANDONED, {"error": str(error)})])
            App.Console.PrintLog(traceback.format_exc())  # diagnostic d'une erreur imprévue
            edit, self._edit = self._edit, None
            _finish(edit, restore=True)  # état de départ rendu, puis ensemble relié
            revert = self._revert()
            if edit is not None and revert is not None:
                revert(edit.old)  # le champ remontre l'épaisseur du document
            self.frame.setVisible(False)
            self._block(False)
            return False
        return True

    def _edit_now(self, value: float) -> None:
        """Épaisseur ``value`` saisie : écrite telle quelle pour l'épaisseur de départ ; sinon
        l'encadré s'affiche (« Laisser en l'état » en tête si rien n'est défait) et le premier
        choix possible est appliqué. Si aucun ne tient, rien n'est écrit et « OK » est bloqué.
        Tant que l'encadré est affiché, chaque saisie repart de l'état d'avant la première
        (:class:`ThicknessEdit`)."""
        if self._edit is None:
            self._edit = ThicknessEdit(self._obj)
        edit = self._edit
        self._probe(edit, value)
        self.refresh(edit.parts)

    def _probe(self, edit: ThicknessEdit, value: float) -> None:
        self._value = value
        conflict = edit.probe(value)
        if conflict is None:  # écrite telle quelle : point de départ de la saisie suivante
            report(edit.messages)
            self.forget()
            return
        self._show(conflict)
        preferred = conflict.preferred()
        if preferred is not None:
            self._radios[preferred].setChecked(True)
            self._apply(preferred)
        else:  # saisie transitoire (« 2 » avant « 22 ») ou impossible : rien d'écrit
            edit.restore()
            self._block(True)

    def forget(self) -> None:
        """Autre saisie (cote, rotation, glissement, matériau) : l'état écrit devient le point de
        départ des saisies d'épaisseur suivantes ; l'encadré disparaît. Une épaisseur non appliquée
        (aucun choix ne tenait) est retirée du champ : il remontre celle du document."""
        if self._blocked and self._edit is not None:
            revert = self._revert()
            if revert is not None:
                revert(self._edit.old)
        edit, self._edit = self._edit, None
        _finish(edit)  # pièce d'ensemble : ensemble relié d'après l'état écrit
        self.frame.setVisible(False)
        self._block(False)

    def _show(self, conflict: Conflict) -> None:
        show_message(self._title, conflict.title)
        show_message(self._question, conflict.question)
        self._group.setExclusive(False)  # aucun bouton coché tant qu'aucun choix n'est fait
        offered = {option.choice: option for option in conflict.options}
        for choice, radio in self._radios.items():
            option = offered.get(choice)
            radio.setChecked(False)
            radio.setVisible(option is not None)
            if option is not None:
                radio.setText(option.text)
                radio.setEnabled(option.reason is None)
            show_message(self._reasons[choice], (option.reason or "") if option else "")
        self._group.setExclusive(True)
        self.frame.setVisible(True)

    def chosen(self, choice: Choice) -> None:
        """Bouton ``choice`` cliqué : appliqué ; « Revenir » remet l'ancienne épaisseur. Une
        erreur est écrite dans la vue rapport (:meth:`_safely`). L'aperçu 3D est recalculé."""
        parts = self._edit.parts if self._edit is not None else []
        if self._safely(lambda: self._choose(choice)):
            self.refresh(parts)
        preview = self._preview()
        if preview is not None:
            self._safely(preview)

    def refresh(self, parts: list[DocumentObject]) -> None:
        """Aperçu des pièces ``parts`` que les choix écrivent (autres que la pièce du panneau,
        recalculée par le panneau) : prolongées ou déplacées, elles suivent dans la vue 3D.
        ``parts`` est lu avant le choix, qui peut oublier l'encadré (« Revenir »)."""
        name = self._obj.Name
        others = [part for part in parts if part.Name != name]
        if others:  # même document : pièces assemblées de proche en proche (``attached``)
            self._safely(lambda: recompute_preview(others[0], *others[1:]))

    def _choose(self, choice: Choice) -> None:
        if self._edit is None:
            return
        if choice is Choice.REVERT:
            old = self._edit.old
            self._edit.apply(old, Choice.REVERT)
            self.frame.setVisible(False)
            self._block(False)
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
            self._block(True)
            return
        self._block(False)


def _finish(edit: ThicknessEdit | None, *, restore: bool = False) -> None:
    """Fin des saisies de ``edit`` (pièce d'ensemble : ensemble relié), avertissements dans la vue
    rapport. ``restore`` : après une erreur, l'état de départ est d'abord rendu (jamais d'ensemble
    relié sur un choix à moitié écrit). L'ensemble qui ne peut pas être relié retrouve ses liaisons
    d'avant et le message le dit ; toute autre erreur est écrite aussi (rappel d'un signal Qt :
    rien ne doit en sortir)."""
    if edit is None:
        return
    try:
        if restore:
            edit.restore()
        report(edit.finish())
    except ValueError as error:  # ensemble non relié : liaisons d'avant rendues, message traduit
        report([str(error)])
    except Exception as error:  # pylint: disable=broad-exception-caught
        report([translated(_ABANDONED, {"error": str(error)})])
        App.Console.PrintLog(traceback.format_exc())


def _weak_choice(box: ConflictBox, choice: Choice) -> Callable[[], None]:
    """Rappel du bouton ``choice`` qui ne garde pas ``box`` en vie."""
    target = ref(box)

    def call() -> None:
        current = target()
        if current is not None:
            current.chosen(choice)

    return call
