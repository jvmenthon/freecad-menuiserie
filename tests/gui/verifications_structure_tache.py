# SPDX-License-Identifier: LGPL-2.1-or-later
"""Vérifications d'interface du panneau « Structure » : double-clic pendant une tâche (ADR 0046,
section « Sélection et tâche en cours »).

Sans modification, avec modification (appliquer, annuler, poursuivre), tâche d'un autre atelier,
et une écriture « Inverser » (propriétés déclarées en lecture seule) qui doit compter comme une
modification. Module importé par ``verifier_atelier.py`` (lancé par FreeCAD hors écran). Une boîte
modale ne se clique pas hors écran : la fonction de choix du panneau (``StructureSync.choose``) est
remplacée.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

import FreeCADGui as Gui
from PySide import QtGui

from freecad.menuiserie.core.task_switch import FOREIGN_TASK, Choice
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.gui.structure_sync import StructureSync
from freecad.menuiserie.gui.structure_tree_widget import item_for
from tests.gui.verifications_assemblages import cadre, usinee_de
from tests.gui.verifications_ensemble import boite_de_refus
from tests.gui.verifications_panneau import annuler, ecarts, ouvrir_par_double_clic
from tests.gui.verifications_panneau_assemblage import double_cliquer, tenon_valide
from tests.gui.verifications_structure import avec_panneau, panneau_structure, traiter
from tests.gui.verifications_structure_selection import choisir_lignes
from tests.integration.bureau import Bureau

# --- Double-clic pendant une tâche --------------------------------------------------------


@contextmanager
def _reponse(synchro: StructureSync, choix: Choice | None) -> Iterator[list[int]]:
    """Boîte de choix du panneau remplacée par ``choix`` ; donne le nombre de questions posées."""
    posees: list[int] = []

    def repondre() -> Choice | None:
        posees.append(1)
        return choix

    original, synchro.choose = synchro.choose, repondre
    try:
        yield posees
    finally:
        synchro.choose = original


def _tache_ouverte_sur(nom: str) -> bool:
    """Vrai si un panneau est ouvert sur l'objet ``nom`` (mode édition de FreeCAD)."""
    en_edition = Gui.ActiveDocument.getInEdit()
    return (
        bool(Gui.Control.activeDialog())
        and en_edition is not None
        and en_edition.Object.Name == nom
    )


def _double_clic(arbre: Any, cle: str) -> None:
    ligne = item_for(arbre, cle)
    if ligne is not None:
        arbre.itemDoubleClicked.emit(ligne, 0)
    traiter()


def _modifier(piece: Any) -> None:
    """Modification du repère par le formulaire, comme une saisie."""
    formulaire = ouvrir_par_double_clic(piece)
    formulaire.markEdit.selectAll()
    formulaire.markEdit.insert("M9")


def _sans_modification(bureau: Bureau, _dock: Any, arbre: Any, synchro: StructureSync) -> list[str]:
    piece, cible = bureau.shown("P"), bureau.shown("JG")
    bureau.doc.clearUndos()
    ouvrir_par_double_clic(piece)
    with _reponse(synchro, Choice.STAY) as questions:
        _double_clic(arbre, cible.Name)
    return [
        *ecarts("aucune question", questions, []),
        *ecarts("nouvelle pièce ouverte", _tache_ouverte_sur(cible.Name), True),
        *ecarts("rien n'a changé : pas d'entrée d'annulation", bureau.doc.UndoNames, []),
    ]


def verifier_structure_double_clic_sans_modification() -> list[str]:
    return avec_panneau(_sans_modification)


def _avec_modification(choix: Choice | None) -> Callable[..., list[str]]:
    def verification(bureau: Bureau, _dock: Any, arbre: Any, synchro: StructureSync) -> list[str]:
        piece, cible = bureau.shown("P"), bureau.shown("JG")
        repere = str(piece.Mark)
        bureau.doc.clearUndos()
        _modifier(piece)
        with _reponse(synchro, choix) as questions:
            _double_clic(arbre, cible.Name)
        problemes = ecarts("une question posée", len(questions), 1)
        if choix is Choice.APPLY:
            problemes += [
                *ecarts("appliqué : repère modifié", piece.Mark, "M9"),
                *ecarts("appliqué : une entrée d'annulation", len(bureau.doc.UndoNames), 1),
                *ecarts("appliqué : nouvelle pièce ouverte", _tache_ouverte_sur(cible.Name), True),
            ]
        elif choix is Choice.DISCARD:
            problemes += [
                *ecarts("annulé : repère d'origine", piece.Mark, repere),
                *ecarts("annulé : rien n'est conservé", bureau.doc.UndoNames, []),
                *ecarts("annulé : nouvelle pièce ouverte", _tache_ouverte_sur(cible.Name), True),
            ]
        else:
            problemes += [
                *ecarts("poursuivre : modification gardée", piece.Mark, "M9"),
                *ecarts("poursuivre : même tâche", _tache_ouverte_sur(piece.Name), True),
            ]
        return problemes

    return verification


def verifier_structure_double_clic_appliquer() -> list[str]:
    return avec_panneau(_avec_modification(Choice.APPLY))


def verifier_structure_double_clic_annuler() -> list[str]:
    return avec_panneau(_avec_modification(Choice.DISCARD))


def verifier_structure_double_clic_echap() -> list[str]:
    return avec_panneau(_avec_modification(None))


class _TacheEtrangere:
    """Tâche d'un autre atelier : ni inscrite ni reconnue par l'atelier."""

    def __init__(self) -> None:
        self.form = QtGui.QWidget()

    def accept(self) -> bool:
        Gui.Control.closeDialog()
        return True

    def reject(self) -> bool:
        Gui.Control.closeDialog()
        return True


def _tache_etrangere(bureau: Bureau, _dock: Any, arbre: Any, synchro: StructureSync) -> list[str]:
    Gui.Control.showDialog(_TacheEtrangere())
    with _reponse(synchro, Choice.APPLY) as questions:
        _double_clic(arbre, bureau.shown("P").Name)
    boite = boite_de_refus()
    problemes = [
        *ecarts("aucune question", questions, []),
        *ecarts("la tâche étrangère reste ouverte", bool(Gui.Control.activeDialog()), True),
        *ecarts("message de refus", boite is not None and boite.text(), translated(FOREIGN_TASK)),
    ]
    Gui.Control.closeDialog()
    return problemes


def verifier_structure_double_clic_tache_etrangere() -> list[str]:
    return avec_panneau(_tache_etrangere)


def _inversion_comptee_comme_modification() -> list[str]:
    """« Inverser » écrit HostPart et GuestPart (déclarées en lecture seule) : c'est une
    modification. Une ligne choisie pendant la tâche n'abandonne pas sa transaction et un
    double-clic propose la boîte, l'inversion est gardée."""
    with cadre("VerifStructureInverser") as (doc, pieces):
        joint = tenon_valide(doc, pieces)
        _dock, arbre, synchro = panneau_structure()
        try:
            avant = joint.HostPart.Name
            double_cliquer(joint)
            joint.Proxy.invert(joint)  # ce que fait « Inverser » (grisé pour un tenon)
            inversee = joint.HostPart.Name
            choisir_lignes(arbre, joint.Name)
            problemes = [
                *ecarts("inversion faite", inversee != avant, True),
                *ecarts("ligne choisie : inversion gardée", joint.HostPart.Name, inversee),
            ]
            cible = usinee_de(pieces["M1"]).Name
            with _reponse(synchro, Choice.STAY) as questions:
                _double_clic(arbre, cible)
            problemes += [
                *ecarts("double-clic : la boîte est proposée", len(questions), 1),
                *ecarts("poursuivre : inversion gardée", joint.HostPart.Name, inversee),
                *ecarts("poursuivre : même tâche", bool(Gui.Control.activeDialog()), True),
            ]
            annuler()
            traiter()
            return problemes + ecarts("annulé : assemblage d'origine", joint.HostPart.Name, avant)
        finally:
            choisir_lignes(arbre)


def verifier_structure_inverser_compte_comme_modification() -> list[str]:
    return _inversion_comptee_comme_modification()


VERIFICATIONS_STRUCTURE_TACHE: tuple[Callable[[], list[str]], ...] = (
    verifier_structure_double_clic_sans_modification,
    verifier_structure_double_clic_appliquer,
    verifier_structure_double_clic_annuler,
    verifier_structure_double_clic_echap,
    verifier_structure_double_clic_tache_etrangere,
    verifier_structure_inverser_compte_comme_modification,
)
