# SPDX-License-Identifier: LGPL-2.1-or-later
"""Cas limites du panneau de la pièce de bois (lot J1c, testeur) : matériau absent de la
bibliothèque, bibliothèque vide, changement de Type, enregistrement puis réouverture, propriétés
pilotées par une expression (critère C6). Réunis dans :data:`VERIFICATIONS_LIMITES`.
"""

from __future__ import annotations

import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

import FreeCAD as App
import FreeCADGui as Gui

from freecad.menuiserie.features import library
from tests.gui.aides_panneau import (
    ERABLE,
    Verification,
    bibliotheque,
    ecritures,
    editer,
    libelle_affiche_par_type,
    transaction_ouverte,
)
from tests.gui.verifications_panneau import (
    COMMAND,
    CREATE,
    EDIT,
    annuler,
    avec_document,
    choisir,
    creer_par_la_commande,
    ecarts,
    formulaire,
    modifier_tout,
    nouveau_document,
    piece_validee,
    saisir,
    valeur,
    valeurs,
    valider,
)

# --- Matériau absent, bibliothèque vide, changement de Type -------------------------------


def verifier_materiau_absent_de_la_bibliotheque() -> list[str]:
    """C5 : matériau inconnu localement, libellé enregistré affiché, menu des épaisseurs
    inactif, aucun avertissement ; « Annuler » le rétablit, « OK » le garde."""
    from freecad.menuiserie.api import make_wood_part

    def verification(doc: Any) -> list[str]:
        with bibliotheque(None, ERABLE) as fichier:
            obj = make_wood_part(material_id="erable", doc=doc)
            fichier.unlink()
            library.reload_library()
        doc.recompute()
        avant = valeurs(obj)
        editer(obj)
        problemes = [
            *ecarts("matériau affiché", formulaire().materialCombo.currentData(), "erable"),
            *ecarts("menu actif", formulaire().standardThicknessButton.isEnabled(), False),
            *ecarts("avertissement masqué", formulaire().thicknessWarning.isHidden(), True),
            *libelle_affiche_par_type(obj),
        ]
        annuler()
        problemes += ecarts("valeurs rétablies", valeurs(obj), avant)
        editer(obj)
        saisir(formulaire().lengthEdit, 900.0)
        valider()
        return [
            *problemes,
            *ecarts("matériau gardé", (obj.MaterialId, obj.Material), ("erable", "Érable")),
            *ecarts("pièce valide", obj.isValid(), True),
        ]

    return avec_document("VerifMateriauAbsent", verification)


BIBLIOTHEQUE_VIDE = (
    "Menuiserie : Aucun matériau dans la bibliothèque : impossible de créer une pièce de bois. "
    "Vérifiez le fichier de matériaux (vue rapport).\n"
)


def message_de_la_commande() -> list[str]:
    """Avertissements de la commande lancée directement (sans trace d'exception)."""
    from freecad.menuiserie.gui.commands.wood_part import CreateWoodPartCommand

    messages: list[str] = []
    original = App.Console.PrintWarning
    App.Console.PrintWarning = messages.append
    try:
        CreateWoodPartCommand().Activated()
    finally:
        App.Console.PrintWarning = original
    return messages


def verifier_bibliotheque_vide() -> list[str]:
    """Bibliothèque vide : la commande est inactive ; lancée quand même, elle ne crée rien et ne
    laisse ni panneau ni transaction (message traduit, pas de trace d'exception) ;
    le panneau d'une pièce existante s'ouvre, un type vide ne la modifie pas, « OK » marche."""
    from freecad.menuiserie.api import make_wood_part

    def verification(doc: Any) -> list[str]:
        obj = make_wood_part(doc=doc)
        doc.recompute()
        with bibliotheque(Path(tempfile.mkdtemp()) / "absente.json"):
            problemes = [
                *ecarts("commande active", Gui.Command.get(COMMAND).isActive(), False),
                *ecarts("message traduit", message_de_la_commande(), [BIBLIOTHEQUE_VIDE]),
            ]
            Gui.Command.get(COMMAND).run()
            problemes += [
                *ecarts("pièces après la commande", len(doc.Objects), 1),
                *ecarts("panneau après la commande", Gui.Control.activeDialog(), False),
                *ecarts("transaction après la commande", transaction_ouverte(), None),
            ]
            avant = valeurs(obj)
            editer(obj)
            problemes += ecarts(
                "libellé affiché", formulaire().materialCombo.currentText(), "Chêne"
            )
            formulaire().kindCombo.setCurrentIndex(1)
            problemes += ecarts("pièce inchangée par un type vide", valeurs(obj), avant)
            formulaire().kindCombo.setCurrentIndex(0)
            saisir(formulaire().lengthEdit, 900.0)
            valider()
        return [
            *problemes,
            *ecarts("longueur validée", obj.Length.Value, 900.0),
            *ecarts("matériau gardé", obj.MaterialId, "chene"),
            *ecarts("entrées d'annulation", doc.UndoNames, [EDIT]),
        ]

    return avec_document("VerifBibliothequeVide", verification)


def verifier_changements_de_type() -> list[str]:
    """C5 : chaque type affiche le libellé de ``obj.Material`` ; « Annuler » rétablit tout ;
    le même parcours validé par « OK » donne une seule entrée d'annulation."""

    def verification(doc: Any) -> list[str]:
        obj = piece_validee(doc)
        avant = valeurs(obj)
        editer(obj)
        problemes = libelle_affiche_par_type(obj)
        annuler()
        problemes += ecarts("valeurs rétablies", valeurs(obj), avant)
        editer(obj)
        libelle_affiche_par_type(obj)
        valider()
        return problemes + ecarts("entrées d'annulation", doc.UndoNames, [EDIT, CREATE])

    return avec_document("VerifTypes", verification)


# --- Enregistrement et réouverture --------------------------------------------------------


def verifier_reouverture_apres_le_panneau() -> list[str]:
    """Pièce réglée dans le panneau, enregistrée, rouverte : valeurs intactes, document non
    modifié, panneau rouvert avec ses valeurs, nouvelle modification annulable."""
    doc = nouveau_document("VerifReouverturePanneau")
    obj = creer_par_la_commande(doc)
    modifier_tout(formulaire())
    valider()
    nom, attendu = obj.Name, valeurs(obj)
    chemin = Path(tempfile.mkdtemp()) / f"{doc.Name}.FCStd"
    doc.saveAs(str(chemin))
    App.closeDocument(doc.Name)
    doc = App.openDocument(str(chemin))
    doc.UndoMode = 1
    try:
        obj = doc.getObject(nom)
        problemes = [
            *ecarts("valeurs rouvertes", valeurs(obj), attendu),
            *ecarts("document modifié", Gui.getDocument(doc.Name).Modified, False),
        ]
        editer(obj)
        problemes += [
            *ecarts("longueur affichée", valeur(formulaire().lengthEdit), 1000.0),
            *ecarts("matériau affiché", formulaire().materialCombo.currentData(), "hetre"),
        ]
        saisir(formulaire().widthEdit, 300.0)
        valider()
        problemes += ecarts("entrées d'annulation", doc.UndoNames, [EDIT])
        doc.undo()
        return problemes + ecarts("largeur annulée", obj.Width.Value, 250.0)
    finally:
        App.closeDocument(doc.Name)


# --- C6 : expressions ---------------------------------------------------------------------


def verifier_expression_sur_une_surcote() -> list[str]:
    """C6 : surcote pilotée par une expression, affichée par le champ et conservée ; la valeur
    suit une cote modifiée dans le panneau et un changement de matériau ne l'écrit pas."""

    def verification(doc: Any) -> list[str]:
        obj = piece_validee(doc)
        obj.setExpression("LengthAllowance", "Length / 40")
        doc.recompute()
        editer(obj)
        champ = formulaire().lengthAllowanceEdit.property("expression")
        problemes = ecarts("expression affichée", champ, "Length / 40")
        choisir(formulaire().materialCombo, "mdf")
        saisir(formulaire().lengthEdit, 1000.0)
        valider()
        doc.recompute()
        return [
            *problemes,
            *ecarts(
                "expression conservée",
                dict(obj.ExpressionEngine),
                {"LengthAllowance": "Length / 40"},
            ),
            *ecarts("surcote recalculée", obj.LengthAllowance.Value, 25.0),
            *ecarts("matériau", obj.MaterialId, "mdf"),
        ]

    return avec_document("VerifExpressionSurcote", verification)


def verifier_cotes_pilotees_jamais_ecrites() -> list[str]:
    """C6 : saisie dans un champ piloté et épaisseur standard du menu : rien n'est écrit."""

    def verification(doc: Any) -> list[str]:
        obj = piece_validee(doc)
        obj.setExpression("Length", "Width * 4")
        obj.setExpression("Thickness", "Width / 10")
        doc.recompute()
        editer(obj)
        with ecritures(obj) as ecrites:
            saisir(formulaire().lengthEdit, 1234.0)
            saisir(formulaire().thicknessEdit, 18.0)
            for action in formulaire().standardThicknessButton.menu().actions():
                action.trigger()
        valider()
        return [
            *ecarts("cotes écrites", sorted({"Length", "Thickness"} & set(ecrites)), []),
            *ecarts("expressions", sorted(dict(obj.ExpressionEngine)), ["Length", "Thickness"]),
            *ecarts("cotes", (obj.Length.Value, obj.Thickness.Value), (800.0, 20.0)),
        ]

    return avec_document("VerifCotesPilotees", verification)


def champ_pilote_inactif_et_jamais_ecrit(
    prop: str, expression: str, action: Callable[[Any], None], widget: str
) -> Verification:
    """C6 : ``prop`` pilotée par ``expression`` ; widget inactif, ``action`` n'écrit rien."""

    def verification(doc: Any) -> list[str]:
        obj = piece_validee(doc)
        obj.GrainDirection = "Width"
        obj.setExpression(prop, expression)
        doc.recompute()
        editer(obj)
        actif = getattr(formulaire(), widget).isEnabled()
        with ecritures(obj) as ecrites:
            action(formulaire())
        valider()
        return [
            *ecarts(f"{widget} actif", actif, False),
            *ecarts(f"propriétés écrites par le panneau ({prop})", ecrites, []),
            *ecarts("expression conservée", prop in dict(obj.ExpressionEngine), True),
        ]

    return lambda: avec_document(f"VerifPilote{prop}", verification)


def _taper_un_repere(form: Any) -> None:
    form.markEdit.selectAll()
    form.markEdit.insert("X")  # émet textEdited, comme une frappe


def verifier_repere_pilote() -> list[str]:
    return champ_pilote_inactif_et_jamais_ecrit("Mark", "Label", _taper_un_repere, "markEdit")()


def verifier_fil_pilote() -> list[str]:
    return champ_pilote_inactif_et_jamais_ecrit(
        "GrainDirection",
        "<<Width>>",
        lambda form: choisir(form.grainCombo, "Length"),
        "grainCombo",
    )()


def verifier_materiau_pilote() -> list[str]:
    return champ_pilote_inactif_et_jamais_ecrit(
        "Material",
        "<<Hêtre>>",
        lambda form: choisir(form.materialCombo, "mdf"),
        "materialCombo",
    )()


VERIFICATIONS_MATERIAUX: tuple[Verification, ...] = (
    verifier_materiau_absent_de_la_bibliotheque,
    verifier_bibliotheque_vide,
    verifier_changements_de_type,
    verifier_reouverture_apres_le_panneau,
    verifier_expression_sur_une_surcote,
    verifier_cotes_pilotees_jamais_ecrites,
    verifier_repere_pilote,
    verifier_fil_pilote,
    verifier_materiau_pilote,
)
