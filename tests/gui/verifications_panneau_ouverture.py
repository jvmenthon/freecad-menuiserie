# SPDX-License-Identifier: LGPL-2.1-or-later
"""Cas limites du panneau de la pièce de bois (lot J1c, testeur) : double-clic sur une pièce
déjà en édition ou en création, ouvertures successives, document fermé ou pièce supprimée
pendant l'édition. Réunis dans :data:`VERIFICATIONS_LIMITES`.
"""

from __future__ import annotations

from typing import Any

import FreeCAD as App
import FreeCADGui as Gui

from tests.gui.aides_panneau import (
    NOUVELLE,
    Verification,
    double_cliquer,
    editer,
    transaction_ouverte,
)
from tests.gui.verifications_panneau import (
    COMMAND,
    CREATE,
    annuler,
    avec_document,
    creer_par_la_commande,
    ecarts,
    formulaire,
    nouveau_document,
    piece_validee,
    saisir,
    valeurs,
    valider,
)

# --- Double-clic --------------------------------------------------------------------------


def verifier_double_clic_pendant_la_creation() -> list[str]:
    """Double-clic sur la pièce en cours de création : refusé, le panneau de création reste."""

    def verification(doc: Any) -> list[str]:
        obj = creer_par_la_commande(doc)
        saisir(formulaire().lengthEdit, 1000.0)
        problemes = [
            *ecarts("double-clic accepté", double_cliquer(obj), False),
            *ecarts("panneau de création", formulaire().windowTitle(), NOUVELLE),
            *ecarts("pièce en édition", Gui.ActiveDocument.getInEdit(), None),
        ]
        annuler()
        return [
            *problemes,
            *ecarts("pièces", len(doc.Objects), 0),
            *ecarts("entrées d'annulation", doc.UndoCount, 0),
        ]

    return avec_document("VerifDoubleClicCreation", verification)


def verifier_double_clic_sur_la_piece_en_edition() -> list[str]:
    """C4 : un second double-clic ne fait rien ; « Annuler » rétablit tout."""

    def verification(doc: Any) -> list[str]:
        obj = piece_validee(doc)
        avant = valeurs(obj)
        editer(obj)
        saisir(formulaire().lengthEdit, 1000.0)
        double_cliquer(obj)
        annuler()
        return [
            *ecarts("valeurs d'origine", valeurs(obj), avant),
            *ecarts("entrées d'annulation", doc.UndoNames, [CREATE]),
        ]

    return avec_document("VerifDoubleClicEdition", verification)


def verifier_double_clic_sur_une_autre_piece() -> list[str]:
    """C4 : le double-clic sur une autre pièce est refusé ; « Annuler » rétablit la première."""

    def verification(doc: Any) -> list[str]:
        premiere, seconde = piece_validee(doc), piece_validee(doc)
        avant = valeurs(premiere)
        editer(premiere)
        saisir(formulaire().lengthEdit, 1000.0)
        accepte = double_cliquer(seconde)
        annuler()
        return [
            *ecarts("double-clic accepté", accepte, False),
            *ecarts("valeurs d'origine", valeurs(premiere), avant),
            *ecarts("entrées d'annulation", doc.UndoNames, [CREATE, CREATE]),
        ]

    return avec_document("VerifDoubleClicAutre", verification)


def verifier_ouvertures_successives() -> list[str]:
    """Stabilité (enveloppes PySide réutilisées en 1.0) : 30 ouvertures, « OK » et « Annuler »
    en alternance ; chaque panneau s'ouvre et porte les bons widgets."""

    def verification(doc: Any) -> list[str]:
        obj = piece_validee(doc)
        problemes: list[str] = []
        for tour in range(30):
            if not double_cliquer(obj) or not Gui.Control.activeDialog():
                problemes.append(f"tour {tour} : panneau non ouvert")
                continue
            saisir(formulaire().lengthEdit, 900.0 + tour)
            (valider if tour % 2 else annuler)()
        return problemes + ecarts("longueur finale", obj.Length.Value, 929.0)

    return avec_document("VerifOuvertures", verification)


# --- Document fermé, pièce supprimée ------------------------------------------------------


def verifier_document_ferme_pendant_l_edition() -> list[str]:
    """Fermer le document pendant l'édition ferme le panneau sans transaction pendante."""
    doc = nouveau_document("VerifFermetureEdition")
    obj = piece_validee(doc)
    editer(obj)
    saisir(formulaire().lengthEdit, 1000.0)
    App.closeDocument(doc.Name)
    problemes = [
        *ecarts("panneau fermé", Gui.Control.activeDialog(), False),
        *ecarts("transaction close", transaction_ouverte(), None),
    ]
    if Gui.Control.activeDialog():
        Gui.Control.closeDialog()
    return problemes + avec_document(
        "VerifApresFermeture",
        lambda _doc: ecarts("commande active", Gui.Command.get(COMMAND).isActive(), True),
    )


def verifier_document_ferme_pendant_la_creation() -> list[str]:
    """Fermer le document pendant la création ferme le panneau (FreeCAD 1.0 plantait en
    détruisant les liaisons d'expression) ; la commande redevient active."""
    doc = nouveau_document("VerifFermetureCreation")
    creer_par_la_commande(doc)
    saisir(formulaire().lengthEdit, 1000.0)
    App.closeDocument(doc.Name)
    Gui.updateGui()  # suites différées de la fermeture
    problemes = [
        *ecarts("panneau fermé", Gui.Control.activeDialog(), False),
        *ecarts("transaction close", transaction_ouverte(), None),
    ]
    if Gui.Control.activeDialog():
        Gui.Control.closeDialog()
    return problemes + avec_document(
        "VerifApresFermetureCreation",
        lambda _doc: ecarts("commande active", Gui.Command.get(COMMAND).isActive(), True),
    )


def verifier_piece_supprimee_pendant_la_creation() -> list[str]:
    """Supprimer la pièce en création : suppression refusée ou panneau fermé."""

    def verification(doc: Any) -> list[str]:
        obj = creer_par_la_commande(doc)
        nom = obj.Name
        Gui.Selection.clearSelection()
        Gui.Selection.addSelection(obj)
        Gui.runCommand("Std_Delete")
        supprimee = doc.getObject(nom) is None
        Gui.updateGui()  # suites différées de la fermeture du panneau
        return [
            *ecarts(
                "panneau ouvert sur une pièce supprimée",
                (supprimee and bool(Gui.Control.activeDialog())),
                False,
            ),
            *ecarts("transaction close", transaction_ouverte(), None),
            *ecarts("commande active", Gui.Command.get(COMMAND).isActive(), True),
        ]

    return avec_document("VerifSuppressionCreation", verification)


VERIFICATIONS_OUVERTURE: tuple[Verification, ...] = (
    verifier_double_clic_pendant_la_creation,
    verifier_double_clic_sur_la_piece_en_edition,
    verifier_double_clic_sur_une_autre_piece,
    verifier_ouvertures_successives,
    verifier_document_ferme_pendant_l_edition,
    verifier_document_ferme_pendant_la_creation,
    verifier_piece_supprimee_pendant_la_creation,
)
