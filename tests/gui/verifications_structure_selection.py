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
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtGui

from freecad.menuiserie.core.display_layers import (
    EDIT_TRANSPARENCY,
    SELECTION_TINT,
    SELECTION_TRANSPARENCY,
)
from freecad.menuiserie.core.task_switch import FOREIGN_TASK, Choice
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.gui import structure_switch
from freecad.menuiserie.gui.display_layers import DISPLAY
from freecad.menuiserie.gui.structure_sync import StructureSync
from freecad.menuiserie.gui.structure_tree_widget import item_for
from tests.gui.verifications_ensemble import boite_de_refus
from tests.gui.verifications_panneau import (
    annuler,
    avec_document,
    ecarts,
    ouvrir_par_double_clic,
    piece_validee,
    valider,
)
from tests.gui.verifications_souris import place, preparer, proche, px_en_mm, saisir, sur_la_fleche
from tests.gui.verifications_souris import tirer as tirer_la_fleche
from tests.gui.verifications_souris_rotation import (
    TRANSACTION as TRANSACTION_ROTATION,
)
from tests.gui.verifications_souris_rotation import (
    lacet,
    saisir_anneau,
    tourner_de,
    vue_isometrique,
)
from tests.gui.verifications_structure import avec_panneau, panneau_structure, traiter
from tests.integration.bureau import Bureau

ORIGINE = 20  # transparence d'origine de la pièce, pour vérifier une restauration exacte
Etat = tuple[int, tuple[int, ...]]
SELECTION: Etat = (SELECTION_TRANSPARENCY, SELECTION_TINT)


def _etat(obj: Any) -> Etat:
    """Transparence et couleur diffuse (0 à 255) affichées de ``obj``."""
    vobj = obj.ViewObject
    diffuse = vobj.ShapeAppearance[0].DiffuseColor
    return int(vobj.Transparency), tuple(round(c * 255) for c in diffuse[:3])


def _choisir(arbre: Any, *cles: str) -> None:
    """Lignes de ``cles`` seules sélectionnées, comme un clic."""
    arbre.clearSelection()
    for cle in cles:
        ligne = item_for(arbre, cle)
        if ligne is not None:
            ligne.setSelected(True)
    traiter()


def _graine(bureau: Bureau) -> tuple[Any, Etat, Etat]:
    """Plateau avec une transparence d'origine propre, son état d'origine et celui de l'édition
    attendue (même couleur, transparence d'édition)."""
    piece = bureau.shown("P")
    piece.ViewObject.Transparency = ORIGINE
    origine = _etat(piece)
    return piece, origine, (EDIT_TRANSPARENCY, origine[1])


# --- Transparence de sélection ------------------------------------------------------------


def _selection_teintee(
    bureau: Bureau, _dock: Any, arbre: Any, _synchro: StructureSync
) -> list[str]:
    piece, origine, _ = _graine(bureau)
    jambe = bureau.shown("JG")
    bureau.doc.clearUndos()
    _choisir(arbre, piece.Name)
    problemes = [
        *ecarts("pièce de la ligne : transparente et teintée", _etat(piece), SELECTION),
        *ecarts("autre pièce intacte", _etat(jambe)[0], 0),
        *ecarts("aucune entrée d'annulation", bureau.doc.UndoNames, []),
    ]
    _choisir(arbre)
    problemes += ecarts("désélection : origine rendue", _etat(piece), origine)
    # ensemble : toutes ses pièces ; assemblage : ses deux pièces
    _choisir(arbre, bureau.furniture.Name)
    problemes += ecarts(
        "ensemble : ses quatre pièces",
        [_etat(bureau.shown(m)) for m in ("P", "JG", "JD", "V")],
        [SELECTION] * 4,
    )
    _choisir(arbre, bureau.joints[0].Name)
    problemes += ecarts(
        "assemblage : ses deux pièces",
        [_etat(bureau.shown(m)) for m in ("JG", "V")],
        [SELECTION] * 2,
    )
    problemes += ecarts("assemblage : les autres pièces intactes", _etat(piece), origine) + ecarts(
        "assemblage : joue droite intacte", _etat(bureau.shown("JD"))[0], 0
    )
    _choisir(arbre)
    return problemes + ecarts("tout désélectionné : plus de calque", DISPLAY.tracked(), [])


def verifier_structure_selection_transparente() -> list[str]:
    return avec_panneau(_selection_teintee)


def _selection_depuis_freecad(
    bureau: Bureau, _dock: Any, _arbre: Any, _synchro: StructureSync
) -> list[str]:
    """Une sélection faite dans l'arbre natif ou la 3D est suivie par la ligne puis la
    transparence ; la vider rend l'origine."""
    piece, origine, _ = _graine(bureau)
    Gui.Selection.addSelection(bureau.doc.Name, piece.Name)
    traiter()
    problemes = ecarts("sélection de FreeCAD : transparence", _etat(piece), SELECTION)
    Gui.Selection.clearSelection()
    traiter()
    return problemes + ecarts("sélection vidée : origine", _etat(piece), origine)


def verifier_structure_selection_depuis_freecad() -> list[str]:
    return avec_panneau(_selection_depuis_freecad)


# --- Coexistence avec la tâche en cours ---------------------------------------------------


def _coexistence(bureau: Bureau, _dock: Any, arbre: Any, _synchro: StructureSync) -> list[str]:
    piece, origine, edition = _graine(bureau)
    autre = bureau.shown("V")
    bureau.doc.clearUndos()
    _choisir(arbre, piece.Name)
    ouvrir_par_double_clic(piece)
    problemes = ecarts(
        "tâche + sélection sur la même pièce : l'édition prime", _etat(piece), edition
    )
    _choisir(arbre, autre.Name)  # autre ligne pendant la tâche : calque de sélection seulement
    problemes += [
        *ecarts("autre ligne : sélection teintée", _etat(autre), SELECTION),
        *ecarts("pièce en édition : toujours l'édition", _etat(piece), edition),
    ]
    _choisir(arbre, piece.Name, autre.Name)
    annuler()
    traiter()
    problemes += [
        *ecarts("tâche finie, ligne encore choisie : sélection", _etat(piece), SELECTION),
        *ecarts("tâche finie : pas l'état de l'édition comme origine", _etat(autre), SELECTION),
    ]
    _choisir(arbre)
    return [
        *problemes,
        *ecarts("tout rendu : origine de la pièce", _etat(piece), origine),
        *ecarts("tout rendu : origine de l'autre", _etat(autre)[0], 0),
        *ecarts("aucune entrée d'annulation", bureau.doc.UndoNames, []),
    ]


def verifier_structure_selection_et_edition_coexistent() -> list[str]:
    return avec_panneau(_coexistence)


def _ok_sans_changement(
    bureau: Bureau, _dock: Any, arbre: Any, _synchro: StructureSync
) -> list[str]:
    """Une sélection de ligne pendant la tâche n'écrit rien dans sa transaction : « OK » sans
    modification ne laisse aucune entrée d'annulation."""
    piece, origine, _ = _graine(bureau)
    bureau.doc.clearUndos()
    ouvrir_par_double_clic(piece)
    _choisir(arbre, bureau.shown("V").Name)
    valider()
    traiter()
    problemes = ecarts("OK sans changement : pas d'entrée d'annulation", bureau.doc.UndoNames, [])
    _choisir(arbre)
    return problemes + ecarts("origine rendue", _etat(piece), origine)


def verifier_structure_ok_sans_changement_apres_selection() -> list[str]:
    return avec_panneau(_ok_sans_changement)


# --- Restauration à chaque sortie ---------------------------------------------------------


def _masquage_du_panneau(
    bureau: Bureau, dock: Any, arbre: Any, _synchro: StructureSync
) -> list[str]:
    piece, origine, _ = _graine(bureau)
    _choisir(arbre, piece.Name)
    dock.hide()
    traiter()
    return ecarts("panneau masqué : origine rendue", _etat(piece), origine)


def verifier_structure_selection_rendue_au_masquage() -> list[str]:
    return avec_panneau(_masquage_du_panneau)


def _suppression(bureau: Bureau, _dock: Any, arbre: Any, _synchro: StructureSync) -> list[str]:
    piece, _origine, _ = _graine(bureau)
    nom = piece.Name
    _choisir(arbre, nom)
    bureau.doc.removeObject(nom)
    traiter()
    return ecarts("objet supprimé : calque oublié", [c for c in DISPLAY.tracked() if nom in c], [])


def verifier_structure_selection_objet_supprime() -> list[str]:
    return avec_panneau(_suppression)


def _fermeture_du_document(
    bureau: Bureau, _dock: Any, arbre: Any, _synchro: StructureSync
) -> list[str]:
    piece, _origine, _ = _graine(bureau)
    _choisir(arbre, piece.Name)
    App.closeDocument(bureau.doc.Name)
    traiter()
    return ecarts("document fermé : aucun calque", DISPLAY.tracked(), [])


def verifier_structure_selection_document_ferme() -> list[str]:
    return avec_panneau(_fermeture_du_document)


def _transparence_enregistree(chemin: Path, nom: str) -> int | None:
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
    piece, origine, _ = _graine(bureau)
    _choisir(arbre, piece.Name)
    dossier = Path(tempfile.mkdtemp(prefix="menuiserie_selection_"))
    try:
        chemin = dossier / "selection.FCStd"
        bureau.doc.saveAs(str(chemin))
        problemes = [
            *ecarts(
                "fichier : transparence d'origine",
                _transparence_enregistree(chemin, piece.Name),
                ORIGINE,
            ),
            *ecarts("après l'enregistrement : sélection reposée", _etat(piece), SELECTION),
        ]
    finally:
        shutil.rmtree(dossier, ignore_errors=True)
    _choisir(arbre)
    return problemes + ecarts("désélection : origine", _etat(piece), origine)


def verifier_structure_selection_absente_du_fichier() -> list[str]:
    return avec_panneau(_enregistrement)


# --- Déplacer et tourner depuis une ligne -------------------------------------------------


def _deplacer_et_tourner(doc: Any) -> list[str]:
    """Une ligne choisie donne les mêmes flèches et anneaux qu'une sélection faite en 3D ; le
    glissement (session interne, sans vrais évènements de souris) déplace puis tourne la pièce,
    une transaction chacun, sans toucher à la transparence de sélection."""
    session = preparer(doc)
    piece = piece_validee(doc)
    doc.clearUndos()
    _dock, arbre, _synchro = panneau_structure()
    vue_isometrique()
    _choisir(arbre, piece.Name)
    problemes = [
        *ecarts("ligne choisie : flèches actives", session.active, True),
        *ecarts("ligne choisie : trois flèches", len(session.layout.arrows), 3),
        *ecarts("ligne choisie : trois anneaux", len(session.layout.rings), 3),
        *ecarts("pièce transparente et teintée", _etat(piece), SELECTION),
    ]
    avant, pas = place(piece), px_en_mm(session)
    survol = sur_la_fleche(session, 0, 40.0)
    session.move(survol)
    problemes += ecarts("flèche saisie", saisir(session, survol), True)
    voulu = tirer_la_fleche(session, 150.0, deplacer=False)
    session.move(voulu)
    session.release(voulu)
    problemes += proche("déplacée de 150 mm (x)", place(piece)[0], avant[0] + 150.0, 3 * pas)
    problemes += ecarts("déplacement : une transaction", doc.UndoNames, ["Déplacer la pièce"])
    problemes += ecarts("déplacement : transparence gardée", _etat(piece), SELECTION)
    pris, depart = saisir_anneau(session, 2)
    arrivee = tourner_de(session, 2, 34.0, depart)
    session.release(arrivee)
    problemes += [
        *ecarts("anneau saisi", pris, True),
        *proche("tournée de 30° (aimant)", lacet(piece), 30.0, 0.01),
        *ecarts("rotation : une transaction de plus", doc.UndoNames[:1], [TRANSACTION_ROTATION]),
        *ecarts("rotation : transparence gardée", _etat(piece), SELECTION),
    ]
    _choisir(arbre)
    return problemes + ecarts("flèches retirées à la désélection", session.active, False)


def verifier_structure_deplacer_et_tourner_depuis_une_ligne() -> list[str]:
    return avec_document("VerifStructureSouris", _deplacer_et_tourner)


# --- Double-clic pendant une tâche --------------------------------------------------------


@contextmanager
def _reponse(choix: Choice | None) -> Iterator[list[int]]:
    """Boîte de choix remplacée par ``choix`` ; donne le nombre de questions posées."""
    posees: list[int] = []

    def repondre() -> Choice | None:
        posees.append(1)
        return choix

    original, structure_switch.chooser = structure_switch.chooser, repondre
    try:
        yield posees
    finally:
        structure_switch.chooser = original


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


def _sans_modification(
    bureau: Bureau, _dock: Any, arbre: Any, _synchro: StructureSync
) -> list[str]:
    piece, cible = bureau.shown("P"), bureau.shown("JG")
    bureau.doc.clearUndos()
    ouvrir_par_double_clic(piece)
    with _reponse(Choice.STAY) as questions:
        _double_clic(arbre, cible.Name)
    return [
        *ecarts("aucune question", questions, []),
        *ecarts("nouvelle pièce ouverte", _tache_ouverte_sur(cible.Name), True),
        *ecarts("rien n'a changé : pas d'entrée d'annulation", bureau.doc.UndoNames, []),
    ]


def verifier_structure_double_clic_sans_modification() -> list[str]:
    return avec_panneau(_sans_modification)


def _avec_modification(choix: Choice | None) -> Callable[..., list[str]]:
    def verification(bureau: Bureau, _dock: Any, arbre: Any, _synchro: StructureSync) -> list[str]:
        piece, cible = bureau.shown("P"), bureau.shown("JG")
        repere = str(piece.Mark)
        bureau.doc.clearUndos()
        _modifier(piece)
        with _reponse(choix) as questions:
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


def _tache_etrangere(bureau: Bureau, _dock: Any, arbre: Any, _synchro: StructureSync) -> list[str]:
    Gui.Control.showDialog(_TacheEtrangere())
    with _reponse(Choice.APPLY) as questions:
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


VERIFICATIONS_STRUCTURE_SELECTION: tuple[Callable[[], list[str]], ...] = (
    verifier_structure_selection_transparente,
    verifier_structure_selection_depuis_freecad,
    verifier_structure_selection_et_edition_coexistent,
    verifier_structure_ok_sans_changement_apres_selection,
    verifier_structure_selection_rendue_au_masquage,
    verifier_structure_selection_objet_supprime,
    verifier_structure_selection_document_ferme,
    verifier_structure_selection_absente_du_fichier,
    verifier_structure_deplacer_et_tourner_depuis_une_ligne,
    verifier_structure_double_clic_sans_modification,
    verifier_structure_double_clic_appliquer,
    verifier_structure_double_clic_annuler,
    verifier_structure_double_clic_echap,
    verifier_structure_double_clic_tache_etrangere,
)
