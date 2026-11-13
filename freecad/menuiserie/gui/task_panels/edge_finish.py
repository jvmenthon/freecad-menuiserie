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
import FreeCADGui as Gui
from PySide import QtCore, QtGui

from freecad.menuiserie import api, icon_path
from freecad.menuiserie.core.edges import BROKEN_EDGE_MM, EdgeFamily, SecondSize, family_for
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.text import quoted_value
from freecad.menuiserie.features.box_parts import box_part_refusal
from freecad.menuiserie.features.edge_profile import FAMILY_LABELS
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.i18n import translated, translated_errors
from freecad.menuiserie.gui.edge_highlight import EdgeHighlight
from freecad.menuiserie.gui.pick_edge import EdgePicker, Pick
from freecad.menuiserie.gui.task_panels import base
from freecad.menuiserie.gui.task_panels.base import (
    DeletionWatcher,
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
        # Profil modifié supprimé pendant la tâche (console, Édition > Supprimer) : fermeture.
        watcher = None if profile is None else DeletionWatcher(profile, Gui.Control.closeDialog)
        super().__init__(document, creating=profile is None, watcher=watcher)
        self.profile = profile  # profil modifié (double-clic), ``None`` en création
        # Nom de pièce → nom de son profil du panneau ; les objets sont relus dans le document
        # (un objet supprimé pendant la tâche n'y est plus).
        self._profiles: dict[str, str] = {}
        self._applied: dict[str, tuple[object, ...]] = {}  # derniers réglages écrits par pièce
        self._failed = False
        self._asymmetric = False  # profil relu dont la cote B diffère de A : B reste visible
        self._guard = UpdateGuard()
        self._picker = EdgePicker(document, self.on_pick, self._ignored)
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
        try:
            self._picker.start()
            self.rebuild()
        except BaseException:
            # Le panneau n'est pas encore enregistré : rien d'autre ne retirerait l'observateur
            # et la mise en valeur (revue sécurité).
            self._release_display()
            raise
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
            index = self._family.findData(profile.Family)  # inconnue : quart de rond
            self._family.setCurrentIndex(
                index if index >= 0 else self._family.findData(EdgeFamily.ROUND.value)
            )
            self._size_a.setProperty("rawValue", profile.SizeA.Value)
            self._size_b.setProperty("rawValue", profile.SizeB.Value)
            self._asymmetric = profile.SizeB.Value not in (0.0, profile.SizeA.Value)
            card = self.pieces.add(profile.Part, removable=False)
            card.set_codes(profile.Edges, silently=True)
        self._profiles[profile.Part.Name] = profile.Name

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
        try:
            with translated_errors():  # cotes de la pièce illisibles
                card = self.pieces.add(pick.part)
        except ValueError as error:
            self._show_message(str(error))
            return
        card.check(pick.codes)

    # --- Aperçu ---------------------------------------------------------------------------

    def _profile_of(self, part_name: str) -> DocumentObject | None:
        """Profil du panneau de la pièce ``part_name``, ``None`` s'il n'y en a pas (ou plus)."""
        name = self._profiles.get(part_name)
        return None if name is None else self.doc.getObject(name)

    def _remove_profile(self, part_name: str) -> None:
        """Profil du panneau de la pièce retiré (s'il existe encore)."""
        profile = self._profile_of(part_name)
        self._profiles.pop(part_name, None)
        self._applied.pop(part_name, None)
        if profile is not None:
            api.remove_edge_profile(profile)

    def _others(self, part: DocumentObject) -> set[str]:
        """Arêtes de ``part`` profilées par un profil qui n'est pas celui du panneau."""
        mine = self._profile_of(part.Name)
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
        self.pieces.prune(self.doc)  # pièces supprimées pendant la tâche
        listed = {part.Name for part in self.pieces.parts()}
        for name in [name for name in self._profiles if name not in listed]:
            self._remove_profile(name)
        conflicts: list[str] = []
        for part, codes in self.pieces.entries():
            others = self._others(part)
            mine = sorted(set(codes) & others)
            # Aperçu : les arêtes déjà profilées par un autre profil ne lui sont retirées
            # qu'après confirmation, dans accept().
            free = [code for code in codes if code not in others]
            try:
                messages.extend(self._preview(part, free, bool(mine)))
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

    def _preview(self, part: DocumentObject, free: list[str], conflicts: bool) -> tuple[str, ...]:
        """Aperçu de ``part`` avec ses arêtes libres ``free``. Toutes ses arêtes choisies déjà
        profilées ailleurs (``conflicts`` sans ``free``) : le profil du panneau est retiré, sauf
        le profil modifié, gardé tel quel jusqu'à « OK » (note, pas refus)."""
        if free or not conflicts:
            return self._apply(part, free, replace=False)
        profile = self._profile_of(part.Name)
        if profile is not None and profile == self.profile:
            return (translated(_NO_EDGE, {"piece": quoted_value(part.Label)}),)
        self._remove_profile(part.Name)
        return ()

    @staticmethod
    def _piece_edges(part: DocumentObject, codes: Sequence[str]) -> str:
        return translated(
            _PIECE_EDGES, {"piece": quoted_value(part.Label), "edges": ", ".join(codes)}
        )

    def _apply(self, part: DocumentObject, codes: list[str], *, replace: bool) -> tuple[str, ...]:
        """Profil de ``part`` créé, modifié ou retiré d'après les champs, pour ``codes`` ;
        avertissements."""
        family = str(self._family.currentData())
        size_a = float(self._size_a.property("rawValue"))
        size_b = float(self._size_b.property("rawValue")) if self._needs_size_b() else 0.0
        profile = self._profile_of(part.Name)
        if not codes:
            if profile is None:
                return ()
            if profile == self.profile:
                raise ValueError(translated(_NO_EDGE, {"piece": quoted_value(part.Label)}))
            self._remove_profile(part.Name)
            return ()
        settings = (tuple(codes), family, size_a, size_b, replace)
        if profile is not None and self._applied.get(part.Name) == settings:
            return ()  # rien n'a changé pour cette pièce : pas de recalcul du document
        if profile is None:
            profile, notices = api.add_edge_profile(
                part, codes, family, size_a, size_b, replace=replace
            )
            self._profiles[part.Name] = profile.Name
        else:
            notices = api.set_edge_profile(profile, codes, family, size_a, size_b, replace=replace)
        self._applied[part.Name] = settings
        return tuple(notices)

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
                self.rebuild()  # état et messages réalignés sur le document
                self._show_message(str(error))
                return False
        if not any(self._profile_of(name) is not None for name in self._profiles):
            return self.reject()
        return super().accept()

    def _confirmed(self, conflicts: str) -> bool:
        box = QtGui.QMessageBox(self.form)
        box.setIcon(QtGui.QMessageBox.Icon.Question)
        box.setWindowTitle(translated(_REPLACE_TITLE))
        box.setTextFormat(QtCore.Qt.TextFormat.PlainText)  # libellés venus du document
        box.setText(translated(_REPLACE_TEXT, {"edges": conflicts}))
        box.setStandardButtons(QtGui.QMessageBox.Yes | QtGui.QMessageBox.No)
        return bool(box.exec() == QtGui.QMessageBox.Yes)


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
