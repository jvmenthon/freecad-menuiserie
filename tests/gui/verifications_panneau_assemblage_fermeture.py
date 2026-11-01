# SPDX-License-Identifier: LGPL-2.1-or-later
"""Vérifications d'interface du panneau des assemblages : fermetures forcées (S1) et refus
visible (S3) de la revue de J3d. Suite de ``verifications_panneau_assemblage.py``, importée par
``verifier_atelier.py`` ; mêmes conventions."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import FreeCADGui as Gui

from tests.gui.aides_panneau import transaction_ouverte
from tests.gui.verifications_assemblages import (
    CADRE,
    assembler,
    cadre,
    observateurs_comptes,
    selectionner,
    usinee_de,
)
from tests.gui.verifications_panneau import annuler, ecarts, formulaire_nomme, saisir, valider
from tests.gui.verifications_panneau_assemblage import (
    creer_sans_valider,
    double_cliquer,
    tenon_valide,
)

Widget = Any

# --- Fermetures forcées (comme J1c, revue J3d S1) ----------------------------------------


def verifier_std_undo_pendant_la_creation() -> list[str]:
    """Édition > Annuler pendant la création : panneau fermé, rien ne reste."""
    with cadre("VerifUndoCreationAssemblage") as (doc, pieces):
        doc.clearUndos()
        creer_sans_valider(doc, pieces)
        Gui.Command.get("Std_Undo").run()
        Gui.updateGui()
        return [
            *ecarts("panneau fermé", bool(Gui.Control.activeDialog()), False),
            *ecarts("objets", [o.Label for o in doc.Objects], list(CADRE)),
            *ecarts("transaction close", transaction_ouverte(), None),
        ]


def verifier_fermeture_forcee_depuis_la_piece_usinee() -> list[str]:
    """S1 : brute supprimée puis Édition > Annuler pendant une édition ouverte depuis la pièce
    usinée : panneau fermé et mode édition quitté (la pièce usinée a perdu sa brute)."""
    problemes = []
    for action in ("suppression", "Std_Undo"):
        with cadre(f"VerifFermetureUsinee{action.replace('_', '')}") as (doc, pieces):
            tenon_valide(doc, pieces)
            usinee = usinee_de(pieces["M1"])
            double_cliquer(usinee)
            saisir(_formulaire_de_la_piece(), 700.0)
            if action == "suppression":
                doc.removeObject(pieces["M1"].Name)
            else:
                Gui.Command.get("Std_Undo").run()
            Gui.updateGui()
            problemes += [
                *ecarts(f"{action} : panneau fermé", bool(Gui.Control.activeDialog()), False),
                *ecarts(f"{action} : édition quittée", Gui.ActiveDocument.getInEdit(), None),
                *ecarts(f"{action} : transaction close", transaction_ouverte(), None),
            ]
    return problemes


def _formulaire_de_la_piece() -> Widget:
    """Champ de longueur du panneau de la pièce de bois ouvert."""
    return formulaire_nomme("WoodPartTaskPanel").lengthEdit


def verifier_aucun_observateur_apres_le_panneau() -> list[str]:
    """C7 : aucun observateur global après le panneau d'assemblage (annulé ou validé)."""
    with cadre("VerifObservateursPanneau") as (doc, pieces), observateurs_comptes() as solde:
        creer_sans_valider(doc, pieces)
        annuler()
        problemes = ecarts("après « Annuler »", solde[0], 0)
        joint = assembler(doc, pieces["M1"], pieces["T1"])
        double_cliquer(joint)
        valider()
        return problemes + ecarts("après « OK »", solde[0], 0)


def verifier_refus_visible() -> list[str]:
    """S3 : pièces refusées par la fabrique (deux conteneurs différents) : rien n'est créé,
    le refus est affiché dans la barre d'état."""
    with cadre("VerifRefusVisible") as (doc, pieces):
        conteneur = doc.addObject("App::Part", "Conteneur")
        conteneur.addObject(pieces["T1"])
        doc.clearUndos()
        selectionner(pieces["M1"], pieces["T1"])
        barre = Gui.getMainWindow().statusBar()
        barre.clearMessage()
        avant = len(doc.Objects)
        Gui.Command.get("Menuiserie_MortiseTenon").run()
        return [
            *ecarts("panneau", bool(Gui.Control.activeDialog()), False),
            *ecarts("objets créés", len(doc.Objects) - avant, 0),
            *ecarts("entrées", doc.UndoNames, []),
            *ecarts("message affiché", bool(barre.currentMessage()), True),
        ]


VERIFICATIONS_PANNEAU_ASSEMBLAGE_FERMETURE: tuple[Callable[[], list[str]], ...] = (
    verifier_std_undo_pendant_la_creation,
    verifier_fermeture_forcee_depuis_la_piece_usinee,
    verifier_aucun_observateur_apres_le_panneau,
    verifier_refus_visible,
)
