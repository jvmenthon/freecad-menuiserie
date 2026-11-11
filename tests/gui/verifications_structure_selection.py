# SPDX-License-Identifier: LGPL-2.1-or-later
"""Vérifications d'interface du panneau « Structure » : sélection de ligne et tâche en cours
(ADR 0046, section « Sélection et tâche en cours »).

Transparence teintée de la ligne sélectionnée, coexistence avec la transparence d'édition,
restauration à chaque sortie (désélection, fermeture de la tâche, masquage du panneau, suppression,
enregistrement, fermeture du document), déplacement et rotation à la souris depuis une ligne (par
la session de glissement, comme ``verifications_souris``), double-clic pendant une tâche (sans
modification, avec modification : appliquer, annuler, poursuivre ; tâche d'un autre atelier).
Module importé par ``verifier_atelier.py`` (lancé par FreeCAD hors écran). Une boîte modale ne se
clique pas hors écran : la fonction de choix de ``structure_switch`` est remplacée.
"""

from __future__ import annotations

import shutil
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

import FreeCAD as App
import FreeCADGui as Gui

from freecad.menuiserie.core.display_layers import (
    EDIT_TRANSPARENCY,
    SELECTION_TINT,
    SELECTION_TRANSPARENCY,
)
from freecad.menuiserie.gui.display_layers import DISPLAY
from freecad.menuiserie.gui.structure_sync import StructureSync
from freecad.menuiserie.gui.structure_tree_widget import item_for
from tests.gui.verifications_panneau import (
    annuler,
    ecarts,
    ouvrir_par_double_clic,
    valider,
)
from tests.gui.verifications_structure import avec_panneau, traiter
from tests.integration.bureau import Bureau

ORIGINE = 20  # transparence d'origine de la pièce, pour vérifier une restauration exacte
Etat = tuple[int, tuple[int, ...]]
SELECTION: Etat = (SELECTION_TRANSPARENCY, SELECTION_TINT)


def etat(obj: Any) -> Etat:
    """Transparence et couleur diffuse (0 à 255) affichées de ``obj``."""
    vobj = obj.ViewObject
    diffuse = vobj.ShapeAppearance[0].DiffuseColor
    return int(vobj.Transparency), tuple(round(c * 255) for c in diffuse[:3])


def choisir_lignes(arbre: Any, *cles: str) -> None:
    """Lignes de ``cles`` seules sélectionnées, comme un clic."""
    arbre.clearSelection()
    for cle in cles:
        ligne = item_for(arbre, cle)
        if ligne is not None:
            ligne.setSelected(True)
    traiter()


def graine(bureau: Bureau) -> tuple[Any, Etat, Etat]:
    """Plateau avec une transparence d'origine propre, son état d'origine et celui de l'édition
    attendue (même couleur, transparence d'édition)."""
    piece = bureau.shown("P")
    piece.ViewObject.Transparency = ORIGINE
    origine = etat(piece)
    return piece, origine, (EDIT_TRANSPARENCY, origine[1])


# --- Transparence de sélection ------------------------------------------------------------


def _selection_teintee(
    bureau: Bureau, _dock: Any, arbre: Any, _synchro: StructureSync
) -> list[str]:
    piece, origine, _ = graine(bureau)
    jambe = bureau.shown("JG")
    bureau.doc.clearUndos()
    choisir_lignes(arbre, piece.Name)
    problemes = [
        *ecarts("pièce de la ligne : transparente et teintée", etat(piece), SELECTION),
        *ecarts("autre pièce intacte", etat(jambe)[0], 0),
        *ecarts("aucune entrée d'annulation", bureau.doc.UndoNames, []),
    ]
    choisir_lignes(arbre)
    problemes += ecarts("désélection : origine rendue", etat(piece), origine)
    # ensemble : toutes ses pièces ; assemblage : ses deux pièces
    choisir_lignes(arbre, bureau.furniture.Name)
    problemes += ecarts(
        "ensemble : ses quatre pièces",
        [etat(bureau.shown(m)) for m in ("P", "JG", "JD", "V")],
        [SELECTION] * 4,
    )
    choisir_lignes(arbre, bureau.joints[0].Name)
    problemes += ecarts(
        "assemblage : ses deux pièces",
        [etat(bureau.shown(m)) for m in ("JG", "V")],
        [SELECTION] * 2,
    )
    problemes += ecarts("assemblage : les autres pièces intactes", etat(piece), origine) + ecarts(
        "assemblage : joue droite intacte", etat(bureau.shown("JD"))[0], 0
    )
    choisir_lignes(arbre)
    return problemes + ecarts("tout désélectionné : plus de calque", DISPLAY.tracked(), [])


def verifier_structure_selection_transparente() -> list[str]:
    return avec_panneau(_selection_teintee)


def _selection_depuis_freecad(
    bureau: Bureau, _dock: Any, arbre: Any, _synchro: StructureSync
) -> list[str]:
    """Une sélection faite dans l'arbre natif ou la 3D ne rend rien transparent ; reprise par le
    panneau après un choix de ligne, elle retire la transparence de ce choix."""
    piece, origine, _ = graine(bureau)
    Gui.Selection.addSelection(bureau.doc.Name, piece.Name)
    traiter()
    problemes = ecarts("sélection de FreeCAD : aucune transparence", etat(piece), origine)
    Gui.Selection.clearSelection()
    traiter()
    choisir_lignes(arbre, piece.Name)
    problemes += ecarts("ligne choisie : transparence", etat(piece), SELECTION)
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(bureau.doc.Name, bureau.shown("V").Name)
    traiter()
    return problemes + ecarts("sélection reprise de FreeCAD : origine", etat(piece), origine)


def verifier_structure_selection_depuis_freecad() -> list[str]:
    return avec_panneau(_selection_depuis_freecad)


# --- Coexistence avec la tâche en cours ---------------------------------------------------


def _coexistence(bureau: Bureau, _dock: Any, arbre: Any, _synchro: StructureSync) -> list[str]:
    piece, origine, edition = graine(bureau)
    autre = bureau.shown("V")
    bureau.doc.clearUndos()
    choisir_lignes(arbre, piece.Name)
    ouvrir_par_double_clic(piece)
    problemes = ecarts(
        "tâche + sélection sur la même pièce : l'édition prime", etat(piece), edition
    )
    # autre ligne pendant la tâche : écrite aussitôt dans la transaction du panneau (retirée
    # avant sa fermeture) ; l'édition reste affichée sur sa pièce
    choisir_lignes(arbre, autre.Name)
    problemes += [
        *ecarts("pendant la tâche : ligne choisie transparente", etat(autre), SELECTION),
        *ecarts("pendant la tâche : l'édition prime toujours", etat(piece), edition),
    ]
    annuler()
    traiter()
    problemes += [
        *ecarts("tâche finie : ligne choisie transparente", etat(autre), SELECTION),
        *ecarts("tâche finie : pièce rendue à son origine", etat(piece), origine),
    ]
    choisir_lignes(arbre)
    return [
        *problemes,
        *ecarts("tout rendu : origine de l'autre", etat(autre)[0], 0),
        *ecarts("aucune entrée d'annulation", bureau.doc.UndoNames, []),
    ]


def verifier_structure_selection_et_edition_coexistent() -> list[str]:
    return avec_panneau(_coexistence)


def _ok_sans_changement(
    bureau: Bureau, _dock: Any, arbre: Any, _synchro: StructureSync
) -> list[str]:
    """La sélection de ligne est retirée de la transaction avant son solde : « OK » sans
    modification ne laisse aucune entrée d'annulation."""
    piece, origine, _ = graine(bureau)
    bureau.doc.clearUndos()
    ouvrir_par_double_clic(piece)
    choisir_lignes(arbre, bureau.shown("V").Name)
    valider()
    traiter()
    problemes = [
        *ecarts("OK sans changement : pas d'entrée d'annulation", bureau.doc.UndoNames, []),
        *ecarts("tâche finie : ligne choisie transparente", etat(bureau.shown("V")), SELECTION),
    ]
    choisir_lignes(arbre)
    return problemes + ecarts("origine rendue", etat(piece), origine)


def verifier_structure_ok_sans_changement_apres_selection() -> list[str]:
    return avec_panneau(_ok_sans_changement)


# --- Restauration à chaque sortie ---------------------------------------------------------


def _masquage_du_panneau(
    bureau: Bureau, dock: Any, arbre: Any, _synchro: StructureSync
) -> list[str]:
    piece, origine, _ = graine(bureau)
    choisir_lignes(arbre, piece.Name)
    dock.hide()
    traiter()
    return ecarts("panneau masqué : origine rendue", etat(piece), origine)


def verifier_structure_selection_rendue_au_masquage() -> list[str]:
    return avec_panneau(_masquage_du_panneau)


def _suppression(bureau: Bureau, _dock: Any, arbre: Any, _synchro: StructureSync) -> list[str]:
    piece, _origine, _ = graine(bureau)
    nom = piece.Name
    choisir_lignes(arbre, nom)
    bureau.doc.removeObject(nom)
    traiter()
    return ecarts(
        "objet supprimé : calque oublié", [c for c in DISPLAY.tracked() if nom in str(c)], []
    )


def verifier_structure_selection_objet_supprime() -> list[str]:
    return avec_panneau(_suppression)


def _fermeture_du_document(
    bureau: Bureau, _dock: Any, arbre: Any, _synchro: StructureSync
) -> list[str]:
    piece, _origine, _ = graine(bureau)
    choisir_lignes(arbre, piece.Name)
    App.closeDocument(bureau.doc.Name)
    traiter()
    return ecarts("document fermé : aucun calque", DISPLAY.tracked(), [])


def verifier_structure_selection_document_ferme() -> list[str]:
    return avec_panneau(_fermeture_du_document)


def transparence_enregistree(chemin: Path, nom: str) -> int | None:
    """Transparence de l'objet ``nom`` écrite dans ``GuiDocument.xml`` du fichier ``chemin``."""
    with zipfile.ZipFile(chemin) as archive:
        racine = ET.fromstring(archive.read("GuiDocument.xml"))  # noqa: S314 (fichier produit ici)
    for fournisseur in racine.iter("ViewProvider"):
        if fournisseur.get("name") != nom:
            continue
        for propriete in fournisseur.iter("Property"):
            valeur = next(iter(propriete), None)
            if propriete.get("name") == "Transparency" and valeur is not None:
                return int(valeur.get("value", "-1"))
    return None


def _enregistrement(bureau: Bureau, _dock: Any, arbre: Any, _synchro: StructureSync) -> list[str]:
    """L'affichage temporaire n'entre jamais dans le fichier ; il revient après l'enregistrement."""
    piece, origine, _ = graine(bureau)
    choisir_lignes(arbre, piece.Name)
    dossier = Path(tempfile.mkdtemp(prefix="menuiserie_selection_"))
    try:
        chemin = dossier / "selection.FCStd"
        bureau.doc.saveAs(str(chemin))
        problemes = [
            *ecarts(
                "fichier : transparence d'origine",
                transparence_enregistree(chemin, piece.Name),
                ORIGINE,
            ),
            *ecarts("après l'enregistrement : sélection reposée", etat(piece), SELECTION),
        ]
    finally:
        shutil.rmtree(dossier, ignore_errors=True)
    choisir_lignes(arbre)
    return problemes + ecarts("désélection : origine", etat(piece), origine)


def verifier_structure_selection_absente_du_fichier() -> list[str]:
    return avec_panneau(_enregistrement)


def _suppression_puis_annulation(
    bureau: Bureau, _dock: Any, arbre: Any, _synchro: StructureSync
) -> list[str]:
    """La transaction de suppression garde le ViewObject avec ses propriétés du moment : Ctrl+Z
    ne doit pas recréer la pièce teintée ni transparente."""
    piece, origine, _ = graine(bureau)
    nom, doc = piece.Name, bureau.doc
    choisir_lignes(arbre, nom)
    doc.openTransaction("Suppression de test")
    doc.removeObject(nom)
    doc.commitTransaction()
    traiter()
    doc.undo()
    doc.recompute()
    traiter()
    recreee = doc.getObject(nom)
    return [
        *ecarts("Ctrl+Z : pièce recréée", recreee is not None, True),
        *ecarts("Ctrl+Z : origine, sans calque", recreee is not None and etat(recreee), origine),
    ]


def verifier_structure_suppression_puis_annulation() -> list[str]:
    return avec_panneau(_suppression_puis_annulation)


def _apres_ok_puis_annulation(
    bureau: Bureau, _dock: Any, arbre: Any, _synchro: StructureSync
) -> list[str]:
    """Ligne choisie pendant une tâche modifiée puis « OK » : Ctrl+Z, désélection, Ctrl+Y ne
    laissent aucune teinte (ni dans la pièce, ni dans le fichier)."""
    piece, origine, _ = graine(bureau)
    doc = bureau.doc
    doc.clearUndos()
    formulaire = ouvrir_par_double_clic(piece)
    formulaire.markEdit.selectAll()
    formulaire.markEdit.insert("M8")
    choisir_lignes(arbre, piece.Name)  # écrite dans la transaction, retirée avant « OK »
    valider()
    traiter()
    problemes = ecarts("OK : ligne choisie transparente", etat(piece), SELECTION)
    doc.undo()
    traiter()
    choisir_lignes(arbre)
    doc.redo()
    traiter()
    problemes += ecarts("Ctrl+Y après désélection : origine", etat(piece), origine)
    dossier = Path(tempfile.mkdtemp(prefix="menuiserie_revue_"))
    try:
        chemin = dossier / "revue.FCStd"
        doc.saveAs(str(chemin))
        problemes += ecarts(
            "fichier : transparence d'origine",
            transparence_enregistree(chemin, piece.Name),
            ORIGINE,
        )
    finally:
        shutil.rmtree(dossier, ignore_errors=True)
    return problemes


def verifier_structure_selection_apres_ok_puis_annulation() -> list[str]:
    return avec_panneau(_apres_ok_puis_annulation)


VERIFICATIONS_STRUCTURE_SELECTION: tuple[Callable[[], list[str]], ...] = (
    verifier_structure_selection_transparente,
    verifier_structure_selection_depuis_freecad,
    verifier_structure_selection_et_edition_coexistent,
    verifier_structure_ok_sans_changement_apres_selection,
    verifier_structure_selection_rendue_au_masquage,
    verifier_structure_selection_objet_supprime,
    verifier_structure_suppression_puis_annulation,
    verifier_structure_selection_document_ferme,
    verifier_structure_selection_absente_du_fichier,
    verifier_structure_selection_apres_ok_puis_annulation,
)
