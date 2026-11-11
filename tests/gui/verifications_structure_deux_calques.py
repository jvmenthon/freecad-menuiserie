# SPDX-License-Identifier: LGPL-2.1-or-later
"""Vérifications d'interface : deux transparences à la fois, celle de la tâche en cours et celle de
la ligne choisie du panneau « Structure » (ADR 0046, « Sélection et tâche en cours »).

Régression de la revue finale (#208) : la sélection était différée tant qu'une transaction était
ouverte, donc invisible pendant une tâche. Elle est écrite dans la transaction du panneau puis
retirée avant sa validation : jamais d'entrée d'annulation inutile, de Ctrl+Y qui la rejoue ni de
teinte dans le fichier. Module importé par ``verifier_atelier.py`` (lancé par FreeCAD hors écran).
"""

from __future__ import annotations

import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

import FreeCADGui as Gui

from freecad.menuiserie.core.display_layers import EDIT_TRANSPARENCY
from freecad.menuiserie.gui.display_layers import DISPLAY
from freecad.menuiserie.gui.structure_sync import StructureSync
from tests.gui.verifications_panneau import annuler, ecarts, ouvrir_par_double_clic, valider
from tests.gui.verifications_structure import avec_panneau, traiter
from tests.gui.verifications_structure_selection import (
    SELECTION,
    choisir_lignes,
    etat,
    graine,
    transparence_enregistree,
)
from tests.gui.verifications_structure_tache import TacheEtrangere
from tests.integration.bureau import Bureau


def _deux_calques(bureau: Bureau, _dock: Any, arbre: Any, _synchro: StructureSync) -> list[str]:
    """Tâche ouverte sur P, clic de la ligne de V : P à 60 % sans teinte, V à 50 % teintée."""
    piece, origine, edition = graine(bureau)
    autre = bureau.shown("V")
    origine_autre = etat(autre)
    ouvrir_par_double_clic(piece)
    choisir_lignes(arbre, autre.Name)
    problemes = [
        *ecarts("pièce éditée : transparence d'édition", piece.ViewObject.Transparency, 60),
        *ecarts("pièce éditée : sans teinte", etat(piece), edition),
        *ecarts("pièce de la ligne : sélection", etat(autre), SELECTION),
        *ecarts("constante d'édition", EDIT_TRANSPARENCY, 60),
    ]
    choisir_lignes(arbre)
    problemes += [
        *ecarts("ligne désélectionnée : origine rendue", etat(autre), origine_autre),
        *ecarts("ligne désélectionnée : édition gardée", etat(piece), edition),
    ]
    annuler()
    traiter()
    return problemes + ecarts("tâche finie : origine", etat(piece), origine)


def verifier_structure_deux_transparences_pendant_la_tache() -> list[str]:
    return avec_panneau(_deux_calques)


def _meme_objet(bureau: Bureau, _dock: Any, arbre: Any, _synchro: StructureSync) -> list[str]:
    """Ligne de la pièce éditée : l'édition prime ; la sélection reparaît à la fin de la tâche."""
    piece, origine, edition = graine(bureau)
    ouvrir_par_double_clic(piece)
    choisir_lignes(arbre, piece.Name)
    problemes = ecarts("même pièce : l'édition prime", etat(piece), edition)
    annuler()
    traiter()
    problemes += ecarts("tâche finie, ligne gardée : sélection", etat(piece), SELECTION)
    choisir_lignes(arbre)
    return problemes + ecarts("désélection : origine", etat(piece), origine)


def verifier_structure_deux_transparences_meme_objet() -> list[str]:
    return avec_panneau(_meme_objet)


def _ok_puis_annulation(
    bureau: Bureau, _dock: Any, arbre: Any, _synchro: StructureSync
) -> list[str]:
    """Modification, ligne de V choisie, « OK » : Ctrl+Z, désélection, Ctrl+Y ne rejouent aucun
    calque ; le fichier n'en contient aucun."""
    piece, origine, _ = graine(bureau)
    autre = bureau.shown("V")
    origine_autre = etat(autre)
    doc = bureau.doc
    doc.clearUndos()
    formulaire = ouvrir_par_double_clic(piece)
    formulaire.markEdit.selectAll()
    formulaire.markEdit.insert("M7")
    choisir_lignes(arbre, autre.Name)
    valider()
    traiter()
    problemes = [
        *ecarts("OK : ligne choisie toujours transparente", etat(autre), SELECTION),
        *ecarts("OK : pièce éditée rendue à son origine", etat(piece), origine),
    ]
    doc.undo()
    traiter()
    choisir_lignes(arbre)
    doc.redo()
    traiter()
    problemes += [
        *ecarts("Ctrl+Y : origine de la ligne", etat(autre), origine_autre),
        *ecarts("Ctrl+Y : origine de la pièce", etat(piece), origine),
    ]
    return problemes + _fichier(doc, {piece.Name: origine[0], autre.Name: origine_autre[0]})


def _fichier(doc: Any, attendu: dict[str, int]) -> list[str]:
    """Transparences écrites dans un fichier enregistré sous un nom temporaire."""
    dossier = Path(tempfile.mkdtemp(prefix="menuiserie_calques_"))
    try:
        chemin = dossier / "calques.FCStd"
        doc.saveAs(str(chemin))
        return [
            probleme
            for nom, valeur in attendu.items()
            for probleme in ecarts(
                f"fichier : {nom}", transparence_enregistree(chemin, nom), valeur
            )
        ]
    finally:
        shutil.rmtree(dossier, ignore_errors=True)


def verifier_structure_deux_transparences_ok_puis_annulation() -> list[str]:
    return avec_panneau(_ok_puis_annulation)


def _enregistrement_pendant_la_tache(
    bureau: Bureau, _dock: Any, arbre: Any, _synchro: StructureSync
) -> list[str]:
    """Enregistrement pendant la tâche : aucun des deux calques dans le fichier, les deux
    reposés ensuite."""
    piece, origine, edition = graine(bureau)
    autre = bureau.shown("V")
    origine_autre = etat(autre)
    ouvrir_par_double_clic(piece)
    choisir_lignes(arbre, autre.Name)
    problemes = _fichier(bureau.doc, {piece.Name: origine[0], autre.Name: origine_autre[0]})
    problemes += [
        *ecarts("enregistré : édition reposée", etat(piece), edition),
        *ecarts("enregistré : sélection reposée", etat(autre), SELECTION),
    ]
    annuler()
    traiter()
    choisir_lignes(arbre)
    return problemes + ecarts("tout rendu", etat(autre), origine_autre)


def verifier_structure_deux_transparences_enregistrement() -> list[str]:
    return avec_panneau(_enregistrement_pendant_la_tache)


def _suppression_pendant_la_tache(
    bureau: Bureau, _dock: Any, arbre: Any, _synchro: StructureSync
) -> list[str]:
    """Objet de la ligne supprimé pendant la tâche : calque oublié, « Annuler » sans erreur."""
    piece, _origine, edition = graine(bureau)
    autre = bureau.shown("V")
    nom = autre.Name
    ouvrir_par_double_clic(piece)
    choisir_lignes(arbre, nom)
    bureau.doc.removeObject(nom)
    traiter()
    problemes = [
        *ecarts("supprimé : calque oublié", [c for c in DISPLAY.tracked() if nom in str(c)], []),
        *ecarts("supprimé : édition gardée", etat(piece), edition),
    ]
    annuler()
    traiter()
    return problemes + ecarts("tâche finie : aucun calque", DISPLAY.tracked(), [])


def verifier_structure_deux_transparences_suppression() -> list[str]:
    return avec_panneau(_suppression_pendant_la_tache)


def _tache_etrangere(bureau: Bureau, _dock: Any, arbre: Any, _synchro: StructureSync) -> list[str]:
    """Tâche d'un autre atelier dans une transaction ouverte : rien n'est posé (on ne maîtrise pas
    la transaction), la ligne s'affiche à la fin."""
    piece, _origine, _ = graine(bureau)
    origine = etat(piece)
    doc = bureau.doc
    doc.openTransaction("Tâche étrangère")
    Gui.Control.showDialog(TacheEtrangere())
    choisir_lignes(arbre, piece.Name)
    problemes = ecarts("tâche étrangère : rien de posé", etat(piece), origine)
    Gui.Control.closeDialog()
    doc.abortTransaction()
    DISPLAY.flush()
    traiter()
    problemes += ecarts("tâche étrangère finie : ligne choisie", etat(piece), SELECTION)
    choisir_lignes(arbre)
    return problemes + ecarts("désélection : origine", etat(piece), origine)


def verifier_structure_deux_transparences_tache_etrangere() -> list[str]:
    return avec_panneau(_tache_etrangere)


VERIFICATIONS_STRUCTURE_DEUX_CALQUES: tuple[Callable[[], list[str]], ...] = (
    verifier_structure_deux_transparences_pendant_la_tache,
    verifier_structure_deux_transparences_meme_objet,
    verifier_structure_deux_transparences_ok_puis_annulation,
    verifier_structure_deux_transparences_enregistrement,
    verifier_structure_deux_transparences_suppression,
    verifier_structure_deux_transparences_tache_etrangere,
)
