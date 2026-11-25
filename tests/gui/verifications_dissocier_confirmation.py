# SPDX-License-Identifier: LGPL-2.1-or-later
"""Confirmation avant « Dissocier la répétition » (demande de jv, 2026-11-24) : la vraie fenêtre
(bouton par défaut, Échap, texte), l'absence de transaction ouverte à la question et le refus
depuis le panneau « Structure ».

Module importé par ``verifier_atelier.py`` (lancé par FreeCAD hors écran)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide import QtCore, QtGui

from freecad.menuiserie import api
from freecad.menuiserie.core.structure_menu import Action
from freecad.menuiserie.features import repeat
from freecad.menuiserie.gui import dissociate_confirm
from tests.gui.verifications_ensemble import lancer
from tests.gui.verifications_panneau import avec_document, ecarts
from tests.gui.verifications_repetition import DISSOCIER, source
from tests.gui.verifications_structure import avec_panneau, traiter
from tests.gui.verifications_structure_lot3 import actions_de


def _touche(widget: QtGui.QWidget, key: Any) -> None:
    """Appui puis relâchement de ``key`` sur ``widget`` (QtTest n'est pas fourni par FreeCAD)."""
    for kind in (QtCore.QEvent.KeyPress, QtCore.QEvent.KeyRelease):
        QtGui.QApplication.sendEvent(widget, QtGui.QKeyEvent(kind, key, QtCore.Qt.NoModifier))


def _repetition(doc: Any, count: int = 3) -> Any:
    rep = api.make_repeat(
        [source(doc)], api.RepeatParams(count=count, step=400.0, axis=api.RepeatAxis.X)
    )
    doc.clearUndos()
    return rep


def _poser(reponse: Callable[[QtGui.QMessageBox], None], faire: Callable[[], Any]) -> list[Any]:
    """Exécute ``faire`` ; ``reponse`` agit sur la fenêtre modale dès qu'elle apparaît. Renvoie
    [texte, bouton par défaut, boutons] vus à l'ouverture, vide si aucune fenêtre."""
    vu: list[Any] = []

    def agir() -> None:
        box = QtGui.QApplication.activeModalWidget()
        if not isinstance(box, QtGui.QMessageBox):
            QtCore.QTimer.singleShot(50, agir)
            return
        vu.extend(
            [
                box.text(),
                box.defaultButton().text(),
                [b.text() for b in box.buttons()],
                box.textFormat() == QtCore.Qt.PlainText,
            ]
        )
        reponse(box)

    QtCore.QTimer.singleShot(50, agir)
    faire()
    return vu


def _fenetre_echap(doc: Any) -> list[str]:
    rep = _repetition(doc)
    copies = repeat.copies_of(rep)
    vu = _poser(
        lambda box: _touche(box, QtCore.Qt.Key_Escape),
        lambda: lancer(DISSOCIER, copies[0]),
    )
    if not vu:
        return ["aucune fenêtre de confirmation"]
    return [
        *ecarts("texte nomme la répétition", f"« {rep.Label} »" in vu[0], True),
        *ecarts("texte donne le nombre de copies", "3" in vu[0], True),
        *ecarts("défaut = Annuler", vu[1], "Annuler"),
        *ecarts("libellés pris comme du texte brut", vu[3], True),
        *ecarts("Échap : copies toujours liées", [repeat.is_copy(c) for c in copies], [True] * 3),
        *ecarts("Échap : répétition gardée", doc.getObject(rep.Name) is not None, True),
        *ecarts("Échap : aucune entrée d'annulation", doc.UndoNames, []),
    ]


def verifier_dissocier_confirmation_echap() -> list[str]:
    """Échap dans la vraie fenêtre : rien ne change, aucune entrée d'annulation."""
    return avec_document("VerifDissocierEchap", _fenetre_echap)


def _fenetre_entree(doc: Any) -> list[str]:
    rep = _repetition(doc)
    copies = repeat.copies_of(rep)
    vu = _poser(
        lambda box: _touche(box, QtCore.Qt.Key_Return),
        lambda: lancer(DISSOCIER, copies[0]),
    )
    return [
        *ecarts("Entrée = bouton par défaut = Annuler", vu[1:2], ["Annuler"]),
        *ecarts("Entrée : copies toujours liées", [repeat.is_copy(c) for c in copies], [True] * 3),
        *ecarts("Entrée : aucune entrée", doc.UndoNames, []),
    ]


def verifier_dissocier_confirmation_entree() -> list[str]:
    """Entrée (bouton par défaut) n'accepte pas la dissociation."""
    return avec_document("VerifDissocierEntree", _fenetre_entree)


def _fenetre_dissocier(doc: Any) -> list[str]:
    rep = _repetition(doc)
    copies = repeat.copies_of(rep)

    def cliquer(box: QtGui.QMessageBox) -> None:
        next(b for b in box.buttons() if b.text() == "Dissocier").click()

    vu = _poser(cliquer, lambda: lancer(DISSOCIER, copies[0]))
    return [
        *ecarts("fenêtre vue", bool(vu), True),
        *ecarts("copies libres", [repeat.is_copy(c) for c in copies], [False] * 3),
        *ecarts("entrées", doc.UndoNames, ["Dissocier la répétition"]),
    ]


def verifier_dissocier_confirmation_dissocier() -> list[str]:
    """« Dissocier » dans la vraie fenêtre : comme avant."""
    return avec_document("VerifDissocierOk", _fenetre_dissocier)


def _aucune_transaction(doc: Any) -> list[str]:
    """La question est posée avant toute transaction (commande)."""
    rep = _repetition(doc)
    copies = repeat.copies_of(rep)
    vues: list[tuple[bool, list[str]]] = []

    def confirmer(_libelles: Any, _copies: int) -> bool:
        vues.append((bool(doc.HasPendingTransaction), list(doc.UndoNames)))
        return False

    original, dissociate_confirm.confirmer = dissociate_confirm.confirmer, confirmer
    try:
        lancer(DISSOCIER, copies[0])
    finally:
        dissociate_confirm.confirmer = original
    return ecarts("transaction ouverte à la question", vues, [(False, [])])


def verifier_dissocier_confirmation_avant_transaction() -> list[str]:
    return avec_document("VerifDissocierAvant", _aucune_transaction)


def _structure_refus(bureau: Any, dock: Any, _arbre: Any, _synchro: Any) -> list[str]:
    """Panneau « Structure » : « Annuler » ne change rien ; la question précède la transaction."""
    planche = api.make_wood_part(600, 300, 19, "chene", mark="Planche", doc=bureau.doc)
    bureau.doc.recompute()
    rep = api.make_repeat([planche], api.RepeatParams(count=2, step=700.0, axis=api.RepeatAxis.X))
    bureau.doc.recompute()
    _synchro.refresh_now(force=True)
    traiter()
    copies = repeat.copies_of(rep)
    doc = bureau.doc
    doc.clearUndos()
    vues: list[tuple[bool, int]] = []

    def confirmer(libelles: Any, nombre: int) -> bool:
        vues.append((bool(doc.HasPendingTransaction), nombre))
        return False

    original, dissociate_confirm.confirmer = dissociate_confirm.confirmer, confirmer
    try:
        fait = actions_de(dock).run_action(Action.DISSOCIATE, [copies[0].Name])
    finally:
        dissociate_confirm.confirmer = original
    traiter()
    return [
        *ecarts("entrée exécutée", fait, True),
        *ecarts("question posée une fois, sans transaction", [v[0] for v in vues], [False]),
        *ecarts("copies toujours liées", [repeat.is_copy(c) for c in copies], [True] * len(copies)),
        *ecarts("répétition gardée", doc.getObject(rep.Name) is not None, True),
        *ecarts("aucune entrée d'annulation", doc.UndoNames, []),
    ]


def verifier_dissocier_confirmation_structure_refus() -> list[str]:
    return avec_panneau(_structure_refus)


VERIFICATIONS_DISSOCIER_CONFIRMATION: tuple[Callable[[], list[str]], ...] = (
    verifier_dissocier_confirmation_echap,
    verifier_dissocier_confirmation_entree,
    verifier_dissocier_confirmation_dissocier,
    verifier_dissocier_confirmation_avant_transaction,
    verifier_dissocier_confirmation_structure_refus,
)
