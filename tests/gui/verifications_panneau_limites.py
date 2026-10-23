# SPDX-License-Identifier: LGPL-2.1-or-later
"""Cas limites de la commande « Pièce de bois » et de son panneau (lot J1c, testeur).

Critères C2 à C7 de ``docs/specs/J1-piece-de-bois.md`` : saisies avec unités et refusées,
recalcul après chaque champ, titres, annuler / rétablir après « OK » et « Annuler ». Les autres
cas limites (double-clic, document fermé, matériaux, réouverture, expressions) sont dans
``verifications_panneau_ouverture.py`` et ``verifications_panneau_materiaux.py`` ;
:data:`VERIFICATIONS_LIMITES` les réunit dans leur ordre d'origine. Module importé par
``verifier_atelier.py``.

Aucune vérification ne garde de référence à un formulaire au-delà de la vie de son panneau :
une enveloppe PySide survivant à son widget serait réutilisée à tort par le panneau suivant.
"""

from __future__ import annotations

from typing import Any

import FreeCADGui as Gui

from tests.gui.aides_panneau import (
    VOLUME_INITIAL,
    Verification,
    editer,
    taper,
    transaction_ouverte,
)
from tests.gui.verifications_panneau import (
    CREATE,
    EDIT,
    annuler,
    avec_document,
    creer_par_la_commande,
    ecarts,
    formulaire,
    modifier_tout,
    piece_validee,
    saisir,
    valeurs,
    valider,
)
from tests.gui.verifications_panneau_materiaux import VERIFICATIONS_MATERIAUX
from tests.gui.verifications_panneau_ouverture import VERIFICATIONS_OUVERTURE

# --- C7 : unités, valeurs refusées, valeurs extrêmes --------------------------------------

SAISIES = (
    # (champ, texte tapé, valeur attendue de la propriété en mm)
    ("lengthEdit", "80 cm", 800.0),
    ("widthEdit", "2'", 609.6),
    ("thicknessEdit", "0", 22.0),
    ("thicknessEdit", "-5", 22.0),
    ("thicknessEdit", "0.05 mm", 22.0),
    ("thicknessEdit", "abc", 22.0),
    ("thicknessEdit", "0.1 mm", 0.1),
    ("lengthEdit", "20001 mm", 800.0),
    ("lengthEdit", "1e9", 800.0),
    ("lengthEdit", "20000 mm", 20000.0),
    ("lengthAllowanceEdit", "-1 mm", 20.0),
    ("lengthAllowanceEdit", "0 mm", 0.0),
)
PROPRIETES = {
    "lengthEdit": "Length",
    "widthEdit": "Width",
    "thicknessEdit": "Thickness",
    "lengthAllowanceEdit": "LengthAllowance",
    "widthAllowanceEdit": "WidthAllowance",
    "thicknessAllowanceEdit": "ThicknessAllowance",
}


def verifier_saisies_et_refus() -> list[str]:
    """C7 : unités acceptées ; ≤ 0, sous 0,1 mm, au-delà de 20 000 mm ou illisible : la pièce
    garde sa dernière valeur valide ; « Annuler » rétablit tout."""

    def verification(doc: Any) -> list[str]:
        obj = piece_validee(doc)
        avant = valeurs(obj)
        editer(obj)
        problemes: list[str] = []
        for champ, texte, attendu in SAISIES:
            taper(getattr(formulaire(), champ), texte)
            prop = PROPRIETES[champ]
            obtenu = round(getattr(obj, prop).Value, 6)
            problemes += ecarts(f"{prop} après « {texte} »", obtenu, attendu)
            problemes += ecarts(f"pièce valide après « {texte} »", obj.isValid(), True)
        annuler()
        return problemes + ecarts("valeurs rétablies", valeurs(obj), avant)

    return avec_document("VerifSaisies", verification)


# --- C4 : recalcul après chaque champ -----------------------------------------------------

NOUVELLES_COTES = (
    ("lengthEdit", 1000.0, 1000 * 200 * 22),
    ("widthEdit", 250.0, 1000 * 250 * 22),
    ("thicknessEdit", 27.0, 1000 * 250 * 27),
    ("lengthAllowanceEdit", 35.0, 1000 * 250 * 27),
    ("widthAllowanceEdit", 7.0, 1000 * 250 * 27),
    ("thicknessAllowanceEdit", 2.0, 1000 * 250 * 27),
)


def verifier_recalcul_de_chaque_cote() -> list[str]:
    """C4 : chaque cote saisie est écrite et la forme recalculée aussitôt (aperçu). L'objet
    reste « Touched » jusqu'à « OK » : ``obj.recompute()`` ne le remet pas à jour."""

    def verification(doc: Any) -> list[str]:
        obj = creer_par_la_commande(doc)
        problemes: list[str] = []
        for champ, cote, volume in NOUVELLES_COTES:
            saisir(getattr(formulaire(), champ), cote)
            prop = PROPRIETES[champ]
            problemes += [
                *ecarts(prop, getattr(obj, prop).Value, cote),
                *ecarts(f"volume après {prop}", round(obj.Shape.Volume), volume),
                *ecarts(f"pièce valide après {prop}", obj.isValid(), True),
            ]
        valider()
        return problemes + ecarts("entrées d'annulation", doc.UndoNames, [CREATE])

    return avec_document("VerifRecalcul", verification)


# --- C2, C4 : titres ----------------------------------------------------------------------


def verifier_titre_avec_un_libelle_particulier() -> list[str]:
    """C4 : titre « Modifier « <Label> » », accolades et guillemets du libellé compris."""

    def verification(doc: Any) -> list[str]:
        obj = piece_validee(doc)
        obj.Label = "Montant {gauche} « bis »"
        editer(obj)
        titre = formulaire().windowTitle()
        return ecarts("titre", titre, "Modifier « Montant {gauche} « bis » »")

    return avec_document("VerifTitre", verification)


# --- C3, C4 : annuler / rétablir ----------------------------------------------------------


def verifier_ok_et_annuler_sans_modification() -> list[str]:
    """« OK » ou « Annuler » sans rien changer : aucune entrée d'annulation, pièce à jour et
    pile « Rétablir » intacte."""

    def verification(doc: Any) -> list[str]:
        obj = piece_validee(doc)
        piece_validee(doc)
        doc.undo()
        problemes: list[str] = []
        for bouton in (valider, annuler):
            editer(obj)
            bouton()
            nom = bouton.__name__
            problemes += [
                *ecarts(f"{nom} : annulations", doc.UndoNames, [CREATE]),
                *ecarts(f"{nom} : rétablissements", doc.RedoNames, [CREATE]),
                *ecarts(f"{nom} : pièce à jour", "Touched" in obj.State, False),
            ]
        return problemes

    return avec_document("VerifSansModification", verification)


def verifier_annuler_retablir_la_creation() -> list[str]:
    """C2 : la création validée s'annule puis se rétablit avec les valeurs du panneau."""

    def verification(doc: Any) -> list[str]:
        obj = creer_par_la_commande(doc)
        modifier_tout(formulaire())
        valider()
        nom, apres = obj.Name, valeurs(obj)
        doc.undo()
        problemes = ecarts("création annulée", doc.getObject(nom), None)
        doc.redo()
        doc.recompute()
        obj = doc.getObject(nom)
        return [
            *problemes,
            *ecarts("création rétablie", valeurs(obj), apres),
            *ecarts("volume rétabli", round(obj.Shape.Volume), 1000 * 250 * 27),
        ]

    return avec_document("VerifAnnulerCreation", verification)


def verifier_annuler_retablir_la_modification() -> list[str]:
    """C4 : l'entrée « Modifier » validée s'annule et se rétablit, forme et couleur comprises."""

    def verification(doc: Any) -> list[str]:
        obj = piece_validee(doc)
        avant = valeurs(obj)
        editer(obj)
        modifier_tout(formulaire())
        valider()
        apres = valeurs(obj)
        doc.undo()
        problemes = [
            *ecarts("valeurs annulées", valeurs(obj), avant),
            *ecarts("volume annulé", round(obj.Shape.Volume), VOLUME_INITIAL),
        ]
        doc.redo()
        return [
            *problemes,
            *ecarts("valeurs rétablies", valeurs(obj), apres),
            *ecarts("volume rétabli", round(obj.Shape.Volume), 1000 * 250 * 27),
            *ecarts("rétablissements", doc.RedoNames, []),
        ]

    return avec_document("VerifAnnulerModification", verification)


def verifier_annuler_apres_une_annulation() -> list[str]:
    """C4 : « Annuler » n'ajoute aucune entrée, même juste après Édition > Annuler."""

    def verification(doc: Any) -> list[str]:
        obj = piece_validee(doc)
        editer(obj)
        saisir(formulaire().lengthEdit, 1000.0)
        valider()
        doc.undo()
        editer(obj)
        annuler()
        return [
            *ecarts("annulations", doc.UndoNames, [CREATE]),
            *ecarts("rétablissements", doc.RedoNames, [EDIT]),
        ]

    return avec_document("VerifAnnulerApresUndo", verification)


def verifier_std_undo_pendant_l_edition() -> list[str]:
    """C4 : « Annuler » rétablit les valeurs d'origine, même après Std_Undo dans le panneau."""

    def verification(doc: Any) -> list[str]:
        obj = piece_validee(doc)
        avant = valeurs(obj)
        editer(obj)
        saisir(formulaire().lengthEdit, 1000.0)
        Gui.Command.get("Std_Undo").run()
        if Gui.Control.activeDialog():
            saisir(formulaire().widthEdit, 300.0)
            annuler()
        Gui.updateGui()  # suites différées de la fermeture du panneau
        return [
            *ecarts("valeurs d'origine", valeurs(obj), avant),
            *ecarts("transaction close", transaction_ouverte(), None),
            *ecarts("mode édition quitté", Gui.ActiveDocument.getInEdit(), None),
        ]

    return avec_document("VerifUndoPendantEdition", verification)


VERIFICATIONS_SAISIES: tuple[Verification, ...] = (
    verifier_saisies_et_refus,
    verifier_recalcul_de_chaque_cote,
    verifier_titre_avec_un_libelle_particulier,
    verifier_ok_et_annuler_sans_modification,
    verifier_annuler_retablir_la_creation,
    verifier_annuler_retablir_la_modification,
    verifier_annuler_apres_une_annulation,
    verifier_std_undo_pendant_l_edition,
)

VERIFICATIONS_LIMITES: tuple[Verification, ...] = (
    *VERIFICATIONS_SAISIES,
    *VERIFICATIONS_OUVERTURE,
    *VERIFICATIONS_MATERIAUX,
)
