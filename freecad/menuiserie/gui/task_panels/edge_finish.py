# SPDX-License-Identifier: LGPL-2.1-or-later
"""Panneau de tâche « Finition des chants » : profil des arêtes d'une ou plusieurs pièces
(issue #5, CH-c).

Le panneau règle la famille (quart de rond par défaut, 1 mm : c'est l'arête cassée ; chanfrein,
gorge, demi-rond, bec-de-corbin, doucine), la cote A, la cote B quand la famille la demande, et
les pièces concernées : une carte par pièce (désignée avant la commande ou cliquée dans la vue
3D), avec ses arêtes choisies sur un patron déplié ou une boîte en perspective
(:mod:`.edge_targets`). Chaque pièce reçoit son propre profil, de même famille et mêmes cotes ;
les arêtes choisies sont mises en valeur dans la vue 3D à la couleur de leur carte
(:mod:`~freecad.menuiserie.gui.edge_highlight`). Chaque saisie recrée ou modifie les profils
dans la transaction ouverte par la commande : « OK » la valide (une entrée d'annulation),
« Annuler » l'abandonne. Une saisie refusée s'affiche dans le panneau et ne change rien. Toute
écriture passe par l'API (``add_edge_profile``…), jamais par des écritures directes.
"""

from __future__ import annotations

from collections.abc import Sequence
from functools import partial
from typing import Final

import FreeCAD as App
from PySide import QtCore, QtGui

from freecad.menuiserie import api, icon_path
from freecad.menuiserie.core.edges import BROKEN_EDGE_MM, EdgeFamily, SecondSize, family_for
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.features.box_parts import box_part_refusal
from freecad.menuiserie.features.edge_profile import FAMILY_LABELS
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.gui.edge_highlight import EdgeHighlight
from freecad.menuiserie.gui.pick_edge import EdgePicker, Pick
from freecad.menuiserie.gui.task_panels import base
from freecad.menuiserie.gui.task_panels.base import (
    TransactionTaskPanel,
    UpdateGuard,
    connect,
    length_spinbox,
)
from freecad.menuiserie.gui.task_panels.edge_targets import PieceList
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
_PIECE_EDGES: Final = QT_TRANSLATE_NOOP("Menuiserie", "{piece} : {edges}")
_IGNORED: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Cliquez sur une pièce de bois, une de ses faces, arêtes ou sommets."
)
_NO_EDGE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Choisissez au moins une arête de « {piece} » ou supprimez ce profil."
)
_ERROR_STYLE: Final = "color: #c0392b;"


class EdgeFinishTaskPanel(TransactionTaskPanel):
    """Profils d'arête de plusieurs pièces et aperçu, dans la transaction ouverte par la
    commande ou par :func:`start_editing` ; transaction, fermeture et surveillance du document :
    :mod:`base`."""

    def __init__(
        self,
        picks: Sequence[Pick] = (),
        profile: DocumentObject | None = None,
        refusals: Sequence[str] = (),
    ) -> None:
        document = (
            profile.Document
            if profile is not None
            else picks[0].part.Document
            if picks
            else App.ActiveDocument
        )
        super().__init__(document, creating=profile is None)
        self.profile = profile  # profil modifié (double-clic), ``None`` en création
        self._profiles: dict[str, DocumentObject] = {}  # nom de pièce → son profil du panneau
        self._failed = False
        self._asymmetric = False  # profil relu dont la cote B diffère de A : B reste visible
        self._guard = UpdateGuard()
        self._picker = EdgePicker(document, None, self.on_pick, self._ignored)
        self._highlight = EdgeHighlight(document)
        self.form = QtGui.QWidget()
        self.form.setObjectName(FORM_NAME)
        self.form.setWindowIcon(QtGui.QIcon(icon_path(ICON)))
        self.form.setWindowTitle(translated(_TITLE))
        layout = QtGui.QVBoxLayout(self.form)
        self._fields(layout)
        self.pieces = PieceList(layout, self.rebuild)
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
        self._load(profile)
        with self._guard:
            for pick in picks:
                self.pieces.add(pick.part).set_codes(pick.codes, silently=True)
        self._show_size_b()
        connect(self._family, "currentIndexChanged(int)", self._family_changed)
        connect(self._size_a, "valueChanged(double)", self.rebuild)
        connect(self._size_b, "valueChanged(double)", self.rebuild)
        self._picker.start()
        self.rebuild()
        if refusals:
            self._show_message("\n".join(refusals))

    # --- Formulaire -----------------------------------------------------------------------

    def _fields(self, layout: QtGui.QVBoxLayout) -> None:
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

    def _load(self, profile: DocumentObject | None) -> None:
        """Champs et carte remplis d'après le profil à modifier (sans le réécrire) ; sa pièce ne
        peut pas quitter la liste (« Supprimer ce profil » le fait)."""
        if profile is None or profile.Part is None:
            return
        with self._guard:
            self._family.setCurrentIndex(self._family.findData(profile.Family))
            self._size_a.setProperty("rawValue", profile.SizeA.Value)
            self._size_b.setProperty("rawValue", profile.SizeB.Value)
            self._asymmetric = profile.SizeB.Value not in (0.0, profile.SizeA.Value)
            card = self.pieces.add(profile.Part, removable=False)
            card.set_codes(profile.Edges, silently=True)
        self._profiles[profile.Part.Name] = profile

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

    def codes(self, part: DocumentObject | None = None) -> list[str]:
        """Arêtes choisies de ``part`` (par défaut, la première pièce de la liste)."""
        cards = self.pieces.cards()
        card = cards[0] if part is None and cards else self.pieces.card_of(part)
        return [] if card is None else card.codes()

    def _show_message(self, message: str) -> None:
        self._error.setText(message)
        self._error.setVisible(bool(message))

    def _ignored(self) -> None:
        """Clic sur autre chose qu'une pièce de bois : la consigne est rappelée."""
        self._show_message(translated(_IGNORED))

    def on_pick(self, pick: Pick) -> None:
        """Pièce, face, arête ou sommet cliqué dans la vue 3D : la pièce s'ajoute à la liste
        (une pièce qui n'est pas une boîte est refusée), ses arêtes désignées sont choisies."""
        refusal = box_part_refusal(pick.part)
        if refusal is not None:
            self._show_message(refusal)
            return
        self.pieces.add(pick.part).check(pick.codes)

    # --- Aperçu ---------------------------------------------------------------------------

    def _others(self, part: DocumentObject) -> set[str]:
        """Arêtes de ``part`` profilées par un profil qui n'est pas celui du panneau."""
        mine = self._profiles.get(part.Name)
        return {
            code for other in api.edge_profiles_of(part) if other != mine for code in other.Edges
        }

    def rebuild(self, *_changed: object) -> None:
        """Profils créés, modifiés ou retirés d'après les champs et les cartes ; un refus
        s'affiche sous les champs et ne change rien. Une pièce sans arête choisie n'a pas de
        profil du panneau."""
        if self._guard.active:
            return
        messages: list[str] = []
        self._failed = False
        listed = {part.Name for part in self.pieces.parts()}
        for name in [name for name in self._profiles if name not in listed]:
            api.remove_edge_profile(self._profiles.pop(name))
        conflicts: list[str] = []
        for part, codes in self.pieces.entries():
            others = self._others(part)
            mine = sorted(set(codes) & others)
            try:
                # Aperçu : les arêtes déjà profilées par un autre profil ne lui sont retirées
                # qu'après confirmation, dans accept().
                free = [code for code in codes if code not in others]
                if free or not mine:
                    messages.extend(self._apply(part, free, replace=False))
            except (TypeError, ValueError) as error:
                messages.append(str(error))
                self._failed = True
            if mine:
                conflicts.append(self._piece_edges(part, mine))
        if conflicts:
            messages.append(translated(_CONFLICT_NOTE, {"edges": " ; ".join(conflicts)}))
        self._show_message("\n".join(messages))
        self._highlight.show(
            [(card.part, card.codes(), card.color) for card in self.pieces.cards()]
        )

    @staticmethod
    def _piece_edges(part: DocumentObject, codes: Sequence[str]) -> str:
        return translated(_PIECE_EDGES, {"piece": part.Label, "edges": ", ".join(codes)})

    def _apply(self, part: DocumentObject, codes: list[str], *, replace: bool) -> tuple[str, ...]:
        """Profil de ``part`` créé, modifié ou retiré d'après les champs, pour ``codes`` ;
        avertissements."""
        family = str(self._family.currentData())
        size_a = float(self._size_a.property("rawValue"))
        size_b = float(self._size_b.property("rawValue")) if self._needs_size_b() else 0.0
        profile = self._profiles.get(part.Name)
        if not codes:
            if profile is None:
                return ()
            if profile == self.profile:
                raise ValueError(translated(_NO_EDGE, {"piece": part.Label}))
            api.remove_edge_profile(self._profiles.pop(part.Name))
            return ()
        if profile is None:
            created, notices = api.add_edge_profile(
                part, codes, family, size_a, size_b, replace=replace
            )
            self._profiles[part.Name] = created
            return tuple(notices)
        return tuple(api.set_edge_profile(profile, codes, family, size_a, size_b, replace=replace))

    def _delete(self) -> None:
        """« Supprimer ce profil » : profil retiré (la pièce usinée disparaît si elle n'a plus
        rien), les profils des autres pièces du panneau sont gardés ; panneau fermé en validant
        la transaction."""
        if self.profile is None:
            return
        self._release_display()
        if self.profile.Part is not None:
            self._profiles.pop(self.profile.Part.Name, None)
        api.remove_edge_profile(self.profile)
        self.profile = None
        TransactionTaskPanel.accept(self)

    # --- Cycle de vie (FreeCAD) -----------------------------------------------------------

    def _release_display(self) -> None:
        """Observateur de sélection et mise en valeur retirés à toute fermeture."""
        self._picker.stop()
        self._highlight.remove()

    def accept(self) -> bool:
        """« OK » : sans profil, rien à valider (abandon) ; valeurs refusées, le panneau reste
        ouvert ; arêtes déjà profilées : confirmation avant de les remplacer."""
        if self._failed:
            return False
        conflicts = [
            (part, codes, sorted(set(codes) & self._others(part)))
            for part, codes in self.pieces.entries()
        ]
        conflicts = [entry for entry in conflicts if entry[2]]
        if conflicts:
            listed = " ; ".join(self._piece_edges(part, mine) for part, _codes, mine in conflicts)
            if not self._confirmed(listed):
                return False
            try:
                for part, codes, _mine in conflicts:
                    self._apply(part, codes, replace=True)
            except (TypeError, ValueError) as error:
                self._show_message(str(error))
                return False
        if not self._profiles:
            return self.reject()
        return super().accept()

    def _confirmed(self, conflicts: str) -> bool:
        reply = QtGui.QMessageBox.question(
            self.form,
            translated(_REPLACE_TITLE),
            translated(_REPLACE_TEXT, {"edges": conflicts}),
        )
        return bool(reply == QtGui.QMessageBox.Yes)


def show_panel(picks: Sequence[Pick] = (), refusals: Sequence[str] = ()) -> None:
    """Ouvre le panneau dans la transaction déjà ouverte, avec les pièces et arêtes ``picks``
    déjà choisies (aucune : il demande de les désigner) et les refus ``refusals`` affichés ; une
    exception l'abandonne."""
    base.show_panel(partial(EdgeFinishTaskPanel, tuple(picks), None, tuple(refusals)))


def start_editing(profile: DocumentObject) -> bool:
    """Double-clic sur un profil d'arête : son panneau, dans la transaction « Modifier un profil
    d'arête » ; faux si un autre panneau est ouvert ou si le profil n'a plus de pièce."""
    if profile.Part is None:
        return False
    return base.start_editing(
        profile.Document,
        EDIT_TRANSACTION,
        partial(EdgeFinishTaskPanel, (), profile),
        profile,
    )
