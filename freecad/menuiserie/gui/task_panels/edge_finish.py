# SPDX-License-Identifier: LGPL-2.1-or-later
"""Panneau de tâche « Finition des chants » : profil des arêtes d'une pièce (issue #5, CH-c).

Le panneau règle la famille (quart de rond par défaut, 1 mm : c'est l'arête cassée ; chanfrein,
gorge, demi-rond, bec-de-corbin, doucine), la cote A, la cote B quand la famille la demande, et
les arêtes (cases à cocher, cochées d'avance d'après la face, l'arête ou le sommet sélectionné,
puis par clic dans la vue 3D), et montre aussitôt le résultat : chaque saisie recrée ou modifie
le profil dans la transaction ouverte par la commande. « OK » la valide (une entrée
d'annulation), « Annuler » l'abandonne.
Une saisie refusée s'affiche dans le panneau et ne change rien. Toute écriture passe par
l'API (``set_edge_profile``…), jamais par des écritures directes.
"""

from __future__ import annotations

from functools import partial
from typing import Final

import FreeCAD as App
from PySide import QtCore, QtGui

from freecad.menuiserie import api, icon_path
from freecad.menuiserie.core.edges import (
    BROKEN_EDGE_MM,
    EdgeFamily,
    SecondSize,
    family_for,
)
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.features.edge_profile import FAMILY_LABELS
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.gui.pick_edge import EdgePicker, Pick
from freecad.menuiserie.gui.task_panels import base
from freecad.menuiserie.gui.task_panels.base import (
    TransactionTaskPanel,
    UpdateGuard,
    connect,
    length_spinbox,
)
from freecad.menuiserie.gui.task_panels.edge_targets import EdgeTargets
from freecad.menuiserie.gui.view_providers.edge_profile import ICON

FORM_NAME: Final = "EdgeFinishTaskPanel"
CREATE_TRANSACTION: Final = QT_TRANSLATE_NOOP("Menuiserie", "Finition des chants")
EDIT_TRANSACTION: Final = QT_TRANSLATE_NOOP("Menuiserie", "Modifier un profil d'arête")
_TITLE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Finition des chants")
_FAMILY: Final = QT_TRANSLATE_NOOP("Menuiserie", "Profil")
_SIZE_A: Final = QT_TRANSLATE_NOOP("Menuiserie", "Cote A (rayon, distance)")
_SIZE_B: Final = QT_TRANSLATE_NOOP("Menuiserie", "Cote B")
_DELETE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Supprimer ce profil")
_REPLACE_TITLE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Arêtes déjà profilées")
_REPLACE_TEXT: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Ces arêtes ont déjà un profil : {edges}. Le nouveau profil le remplace. Continuer ?",
)
_CONFLICT_NOTE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Déjà profilées ailleurs (remplacées à la validation) : {edges}."
)
_NO_EDGE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Cochez au moins une arête à profiler.")
_ERROR_STYLE: Final = "color: #c0392b;"


class EdgeFinishTaskPanel(TransactionTaskPanel):
    """Profil d'arête et aperçu, dans la transaction ouverte par la commande ou par
    :func:`start_editing` ; transaction, fermeture et surveillance du document : :mod:`base`."""

    def __init__(
        self,
        part: DocumentObject | None,
        profile: DocumentObject | None = None,
        preselected: Pick | None = None,
    ) -> None:
        document = App.ActiveDocument if part is None else part.Document
        super().__init__(document, creating=profile is None)
        self.part = part
        self.profile = profile
        self._failed = False
        self._asymmetric = False  # profil relu dont la cote B diffère de A : B reste visible
        self._guard = UpdateGuard()
        self._others: set[str] = set()
        self._picker = EdgePicker(document, part, self.on_pick)
        self.form = QtGui.QWidget()
        self.form.setObjectName(FORM_NAME)
        self.form.setWindowIcon(QtGui.QIcon(icon_path(ICON)))
        self.form.setWindowTitle(translated(_TITLE))
        layout = QtGui.QVBoxLayout(self.form)
        form = QtGui.QFormLayout()
        layout.addLayout(form)
        self._family = QtGui.QComboBox()
        self._family.setObjectName("family")
        for family in EdgeFamily:
            self._family.addItem(translated(FAMILY_LABELS[family]), family.value)
        self._family.setCurrentIndex(self._family.findData(EdgeFamily.ROUND.value))
        form.addRow(translated(_FAMILY), self._family)
        self._size_a = length_spinbox("size_a", BROKEN_EDGE_MM)
        self._size_b = length_spinbox("size_b", 0.0)
        self._label_b = QtGui.QLabel(translated(_SIZE_B))
        form.addRow(translated(_SIZE_A), self._size_a)
        form.addRow(self._label_b, self._size_b)
        self._targets = EdgeTargets(layout, self.rebuild)
        self._error = QtGui.QLabel()
        self._error.setObjectName("errorLabel")
        self._error.setWordWrap(True)
        self._error.setTextFormat(QtCore.Qt.TextFormat.PlainText)
        self._error.setStyleSheet(_ERROR_STYLE)
        layout.addWidget(self._error)
        if profile is not None:
            delete = QtGui.QPushButton(translated(_DELETE))
            delete.setObjectName("delete_profile")
            layout.addWidget(delete)
            connect(delete, "clicked()", self._delete)
        self._bind(part)
        self._load(profile)
        if preselected is not None:
            for face in preselected.faces:
                self._targets.add_face(face)
            self._targets.set_silently(preselected.codes)
        self._show_size_b()
        connect(self._family, "currentIndexChanged(int)", self._family_changed)
        connect(self._size_a, "valueChanged(double)", self.rebuild)
        connect(self._size_b, "valueChanged(double)", self.rebuild)
        self._picker.start()
        self.rebuild()

    # --- Formulaire -----------------------------------------------------------------------

    def _load(self, profile: DocumentObject | None) -> None:
        """Champs remplis d'après le profil à modifier (sans le réécrire)."""
        if profile is None:
            return
        with self._guard:
            self._family.setCurrentIndex(self._family.findData(profile.Family))
            self._size_a.setProperty("rawValue", profile.SizeA.Value)
            self._size_b.setProperty("rawValue", profile.SizeB.Value)
            self._asymmetric = profile.SizeB.Value not in (0.0, profile.SizeA.Value)
            self._targets.set_silently(profile.Edges)

    def _needs_size_b(self) -> bool:
        """Cote B demandée : bec-de-corbin et doucine ; un profil relu asymétrique la garde."""
        second = family_for(str(self._family.currentData())).second
        return second is SecondSize.REQUIRED or (
            second is SecondSize.SAME_IF_ZERO and self._asymmetric
        )

    def _show_size_b(self) -> None:
        visible = self._needs_size_b()
        self._label_b.setVisible(visible)
        self._size_b.setVisible(visible)

    def _family_changed(self, *_changed: object) -> None:
        self._show_size_b()
        self.rebuild()

    def codes(self) -> list[str]:
        """Codes des arêtes cochées, dans l'ordre des douze arêtes."""
        return self._targets.codes()

    def _bind(self, part: DocumentObject | None) -> None:
        """Pièce travaillée : sans elle, le panneau demande d'abord de la désigner."""
        self.part = part
        self._others = (
            set()
            if part is None
            else {
                code
                for other in api.edge_profiles_of(part)
                if other != self.profile
                for code in other.Edges
            }
        )
        self._targets.show_for(has_part=part is not None)
        if part is not None:
            self._picker.bind(part)

    def on_pick(self, pick: Pick) -> None:
        """Cibles désignées dans la vue 3D : pièce (la première fois), faces et arêtes cochées."""
        if self.part is None:
            self._bind(pick.part)
        for face in pick.faces:
            self._targets.add_face(face)
        self._targets.check(pick.codes)

    # --- Aperçu ---------------------------------------------------------------------------

    def rebuild(self, *_changed: object) -> None:
        """Profil créé ou modifié d'après les champs ; un refus s'affiche sous les champs et
        ne change rien. Sans arête cochée en création, il n'y a pas de profil."""
        if self._guard.active:
            return
        codes = self.codes()
        if self.part is None:
            return
        conflicts = sorted(set(codes) & self._others)
        message = ""
        self._failed = False
        try:
            # Aperçu : les arêtes déjà profilées par un autre profil ne lui sont retirées
            # qu'après confirmation, dans accept().
            free = [code for code in codes if code not in self._others]
            if free or not conflicts:
                message = "\n".join(self._apply(free, replace=False))
            if conflicts:
                note = translated(_CONFLICT_NOTE, {"edges": ", ".join(conflicts)})
                message = f"{message}\n{note}" if message else note
        except (TypeError, ValueError) as error:
            message, self._failed = str(error), True
        self._error.setText(message)
        self._error.setVisible(bool(message))

    def _apply(self, codes: list[str], *, replace: bool) -> tuple[str, ...]:
        """Profil créé ou modifié d'après les champs, pour ``codes`` ; avertissements."""
        family = str(self._family.currentData())
        size_a = float(self._size_a.property("rawValue"))
        size_b = float(self._size_b.property("rawValue")) if self._needs_size_b() else 0.0
        if not codes:
            if self.profile is not None:
                raise ValueError(translated(_NO_EDGE))
            return ()
        if self.profile is None:
            self.profile, notices = api.add_edge_profile(
                self.part, codes, family, size_a, size_b, replace=replace
            )
            return tuple(notices)
        return tuple(
            api.set_edge_profile(self.profile, codes, family, size_a, size_b, replace=replace)
        )

    def _delete(self) -> None:
        """« Supprimer ce profil » : profil retiré (la pièce usinée disparaît si elle n'a plus
        rien), panneau fermé en validant la transaction."""
        if self.profile is None:
            return
        self._picker.stop()
        api.remove_edge_profile(self.profile)
        self.profile = None
        TransactionTaskPanel.accept(self)

    # --- Cycle de vie (FreeCAD) -----------------------------------------------------------

    def _release_display(self) -> None:
        """Observateur de sélection retiré à toute fermeture."""
        self._picker.stop()

    def accept(self) -> bool:
        """« OK » : sans arête en création, rien à valider (abandon) ; valeurs refusées, le
        panneau reste ouvert ; arêtes déjà profilées : confirmation avant de les remplacer."""
        codes = self.codes()
        if not codes and self.profile is None:
            return self.reject()
        if self._failed:
            return False
        conflicts = sorted(set(codes) & self._others)
        if conflicts:
            if not self._confirmed(conflicts):
                return False
            try:
                self._apply(codes, replace=True)
            except (TypeError, ValueError) as error:
                self._error.setText(str(error))
                self._error.setVisible(True)
                return False
        elif self.profile is None:
            return False
        return super().accept()

    def _confirmed(self, conflicts: list[str]) -> bool:
        reply = QtGui.QMessageBox.question(
            self.form,
            translated(_REPLACE_TITLE),
            translated(_REPLACE_TEXT, {"edges": ", ".join(conflicts)}),
        )
        return bool(reply == QtGui.QMessageBox.Yes)


def show_panel(
    part: DocumentObject | None,
    profile: DocumentObject | None = None,
    preselected: Pick | None = None,
) -> None:
    """Ouvre le panneau dans la transaction déjà ouverte, avec les cibles ``preselected`` (faces
    et arêtes) cochées ; sans pièce, il demande de la désigner ; une exception l'abandonne."""
    base.show_panel(partial(EdgeFinishTaskPanel, part, profile, preselected))


def start_editing(profile: DocumentObject) -> bool:
    """Double-clic sur un profil d'arête : son panneau, dans la transaction « Modifier un profil
    d'arête » ; faux si un autre panneau est ouvert ou si le profil n'a plus de pièce."""
    part = profile.Part
    if part is None:
        return False
    return base.start_editing(
        profile.Document,
        EDIT_TRANSACTION,
        partial(EdgeFinishTaskPanel, part, profile),
        profile,
    )
