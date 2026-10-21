# SPDX-License-Identifier: LGPL-2.1-or-later
"""Vérifications d'interface du panneau de tâche des assemblages (J3e).

Critères E1 à E5 de ``docs/specs/J3-assemblages.md`` et suites de revue de J3d (S1 : fermeture
forcée d'une édition ouverte depuis la pièce usinée ; S3 : refus visible). Module importé par
``verifier_atelier.py`` (lancé par FreeCAD hors écran) : chaque vérification renvoie la liste
de ses problèmes. Les champs sont manipulés comme par l'utilisateur, par leurs propriétés et
signaux Qt ; « OK » et « Annuler » passent par le dialogue actif de FreeCAD.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import FreeCADGui as Gui
from PySide import QtCore, QtGui

from freecad.menuiserie.core.text import quoted_value
from tests.gui.verifications_assemblages import (
    CADRE,
    CREATION,
    assembler,
    cadre,
    observateurs_comptes,
    selectionner,
    usinee_de,
)
from tests.gui.verifications_panneau import annuler, ecarts, saisir, valider
from tests.gui.verifications_panneau_limites import transaction_ouverte

FORM = "JointTaskPanel"
MODIFICATION = "Modifier un assemblage"
TOURILLONS = "Menuiserie_Dowels"
# Tenon-mortaise de M1 et T1 : valeurs automatiques (épaisseur 22 -> 7, largeur 60 -> 40,
# profondeur 60 -> 40), jeu de fond 2 mm, non traversant.
AUTOMATIQUES = {"TenonThickness": 7.0, "TenonWidth": 40.0, "TenonLength": 40.0}

Widget = Any


def panneau() -> Widget:
    """Formulaire du panneau d'assemblage ouvert (``None`` s'il n'y en a pas)."""
    trouves = [w for w in QtGui.QApplication.allWidgets() if w.objectName() == FORM]
    return trouves[0] if trouves else None


def widget(form: Widget, nom: str) -> Widget:
    trouves = [w for w in form.findChildren(QtGui.QWidget) if w.objectName() == nom]
    if not trouves:
        raise LookupError(f"widget {nom} absent du panneau")
    return trouves[0]


def valeur(champ: Widget) -> float:
    return round(float(champ.property("rawValue")), 3)


def texte(form: Widget, nom: str) -> str:
    return str(widget(form, nom).text())


def creer_sans_valider(doc: Any, pieces: dict[str, Any], commande: str = "") -> Any:
    """Commande lancée sur M1 puis T1, panneau laissé ouvert ; renvoie l'assemblage."""
    options = {"commande": commande} if commande else {}
    return assembler(doc, pieces["M1"], pieces["T1"], ok=False, **options)


def tenon_valide(doc: Any, pieces: dict[str, Any]) -> Any:
    """Tenon-mortaise M1 / T1 créé et validé, historique d'annulation vide ensuite."""
    joint = assembler(doc, pieces["M1"], pieces["T1"])
    doc.clearUndos()
    return joint


def double_cliquer(obj: Any) -> bool:
    vobj = obj.ViewObject
    return bool(vobj.Proxy.doubleClicked(vobj))


# --- E1 : formulaire --------------------------------------------------------------------


def verifier_formulaire_du_tenon_mortaise() -> list[str]:
    """E1 : pièces, « Inverser », une ligne par paramètre, cases « Auto » et valeurs
    effectives dans les champs inactifs."""
    with cadre("VerifPanneauAssemblage") as (doc, pieces):
        creer_sans_valider(doc, pieces)
        form = panneau()
        if form is None:
            return ["panneau non ouvert à la création"]
        problemes = [
            *ecarts("titre", form.windowTitle(), "Nouvel assemblage : Tenon-mortaise"),
            *ecarts("hôte", texte(form, "hostLabel"), "Pièce hôte : « M1 »"),
            *ecarts("invitée", texte(form, "guestLabel"), "Pièce invitée : « T1 »"),
            *ecarts("bouton", texte(form, "invertButton"), "Inverser"),
            *ecarts("erreur masquée", widget(form, "errorLabel").isHidden(), True),
        ]
        for nom, attendu in AUTOMATIQUES.items():
            champ, auto = widget(form, nom), widget(form, f"{nom}Auto")
            problemes += [
                *ecarts(f"{nom} auto", (auto.isChecked(), auto.text()), (True, "Auto")),
                *ecarts(f"{nom} inactif", champ.isEnabled(), False),
                *ecarts(f"{nom} valeur effective", valeur(champ), attendu),
            ]
        problemes += [
            *ecarts("jeu de fond", valeur(widget(form, "MortiseClearance")), 2.0),
            *ecarts("traversant", widget(form, "Through").isChecked(), False),
            *ecarts("jeu sans case Auto", len(form.findChildren(QtGui.QCheckBox)), 4),
        ]
        annuler()
        return problemes


def verifier_formulaire_des_tourillons() -> list[str]:
    """E1 : même panneau pour un autre type ; nombre automatique affiché."""
    with cadre("VerifPanneauTourillons") as (doc, pieces):
        creer_sans_valider(doc, pieces, TOURILLONS)
        form = panneau()
        if form is None:
            return ["panneau non ouvert à la création"]
        nombre = widget(form, "Count")
        problemes = [
            *ecarts("titre", form.windowTitle(), "Nouvel assemblage : Tourillons"),
            *ecarts("diamètre effectif", valeur(widget(form, "Diameter")), 10.0),
            *ecarts("nombre auto", widget(form, "CountAuto").isChecked(), True),
            *ecarts("nombre effectif", nombre.value() >= 1, True),
            *ecarts("nombre inactif", nombre.isEnabled(), False),
        ]
        annuler()
        return problemes


def verifier_case_auto() -> list[str]:
    """E1, E2 : décocher « Auto » fige la valeur effective, la saisie est visible aussitôt,
    recocher remet 0 (automatique)."""
    with cadre("VerifCaseAuto") as (doc, pieces):
        joint = creer_sans_valider(doc, pieces)
        form = panneau()
        widget(form, "TenonThicknessAuto").setChecked(False)
        champ = widget(form, "TenonThickness")
        problemes = [
            *ecarts("valeur figée", joint.TenonThickness.Value, 7.0),
            *ecarts("champ actif", champ.isEnabled(), True),
        ]
        usinee = usinee_de(pieces["T1"])
        volume = usinee.Shape.Volume
        saisir(champ, 9.0)
        problemes += [
            *ecarts("valeur saisie", joint.TenonThickness.Value, 9.0),
            # Aperçu : tenon de 40 x 40 mm épaissi de 2 mm.
            *ecarts("aperçu du tenon", round(usinee.Shape.Volume - volume, 3), 3200.0),
        ]
        widget(form, "TenonThicknessAuto").setChecked(True)
        problemes += [
            *ecarts("automatique", joint.TenonThickness.Value, 0.0),
            *ecarts("valeur effective", valeur(champ), 7.0),
        ]
        annuler()
        return problemes


def verifier_inverser() -> list[str]:
    """E1, E3 : « Inverser » échange les pièces ; l'assemblage impossible est signalé dans le
    panneau, et un second « Inverser » le rétablit."""
    with cadre("VerifInverser") as (doc, pieces):
        joint = creer_sans_valider(doc, pieces)
        form = panneau()
        bouton = widget(form, "invertButton")
        bouton.click()
        erreur = widget(form, "errorLabel")
        problemes = [
            *ecarts("hôte", joint.HostPart.Label, "T1"),
            *ecarts("libellé hôte", texte(form, "hostLabel"), "Pièce hôte : « T1 »"),
            *ecarts("erreur affichée", (erreur.isHidden(), bool(erreur.text())), (False, True)),
        ]
        bouton.click()
        problemes += [
            *ecarts("hôte rétabli", joint.HostPart.Label, "M1"),
            *ecarts("erreur masquée", erreur.isHidden(), True),
        ]
        annuler()
        return problemes


# --- E2 : transactions ------------------------------------------------------------------


def verifier_creation_validee() -> list[str]:
    """E2 : « OK » à la création : une seule entrée « Créer un assemblage tenon-mortaise »."""
    with cadre("VerifCreationValidee") as (doc, pieces):
        doc.clearUndos()
        creer_sans_valider(doc, pieces)
        saisir(widget(panneau(), "MortiseClearance"), 3.0)
        valider()
        return [
            *ecarts("entrées d'annulation", doc.UndoNames, [CREATION]),
            *ecarts("transaction close", transaction_ouverte(), None),
            *ecarts("panneau fermé", bool(Gui.Control.activeDialog()), False),
        ]


def verifier_creation_annulee() -> list[str]:
    """E2 : « Annuler » à la création : ni assemblage, ni pièce usinée, ni entrée ; brutes
    de nouveau visibles."""
    with cadre("VerifCreationAnnulee") as (doc, pieces):
        doc.clearUndos()
        creer_sans_valider(doc, pieces)
        saisir(widget(panneau(), "MortiseClearance"), 3.0)
        annuler()
        return [
            *ecarts("objets", [o.Label for o in doc.Objects], list(CADRE)),
            *ecarts("entrées d'annulation", doc.UndoNames, []),
            *ecarts("brutes visibles", [p.Visibility for p in pieces.values()], [True] * 4),
            *ecarts("transaction close", transaction_ouverte(), None),
        ]


def verifier_libelles_en_texte_brut() -> list[str]:
    """Audit de sécurité J3 : libellés des pièces et message d'erreur en texte brut, titre
    cité tronqué et échappé (libellé de l'assemblage choisi par l'utilisateur ou un fichier)."""
    with cadre("VerifLibellesAssemblage") as (doc, pieces):
        joint = tenon_valide(doc, pieces)
        pieces["M1"].Label = "<b>M1</b>"
        joint.Label = "<i>T</i>\u202e" + "x" * 40
        if not double_cliquer(joint) or panneau() is None:
            return ["double-clic : panneau non ouvert"]
        form = panneau()
        attendu = f"Modifier « {quoted_value(joint.Label)} »"
        problemes = ecarts("titre", form.windowTitle(), attendu)
        for nom in ("hostLabel", "guestLabel", "errorLabel"):
            format_texte = widget(form, nom).textFormat()
            problemes += ecarts(f"{nom} texte brut", format_texte, QtCore.Qt.TextFormat.PlainText)
        annuler()
        return problemes


def verifier_modification() -> list[str]:
    """E2, E5 : double-clic sur l'assemblage ; « OK » crée « Modifier un assemblage »,
    « Annuler » rétablit les valeurs."""
    with cadre("VerifModificationAssemblage") as (doc, pieces):
        joint = tenon_valide(doc, pieces)
        if not double_cliquer(joint) or panneau() is None:
            return ["double-clic : panneau non ouvert"]
        problemes = ecarts("titre", panneau().windowTitle(), "Modifier « Tenon-mortaise »")
        saisir(widget(panneau(), "MortiseClearance"), 5.0)
        annuler()
        problemes += [
            *ecarts("annulé", joint.MortiseClearance.Value, 2.0),
            *ecarts("aucune entrée", doc.UndoNames, []),
            *ecarts("édition terminée", Gui.ActiveDocument.getInEdit(), None),
        ]
        double_cliquer(joint)
        saisir(widget(panneau(), "MortiseClearance"), 5.0)
        valider()
        return [
            *problemes,
            *ecarts("validé", joint.MortiseClearance.Value, 5.0),
            *ecarts("entrées", doc.UndoNames, [MODIFICATION]),
        ]


# --- E3, E4 : erreur et expressions ------------------------------------------------------


def verifier_erreur_affichee() -> list[str]:
    """E3 : tenon trop long : message dans le panneau, « OK » possible, assemblage en erreur."""
    with cadre("VerifErreurAssemblage") as (doc, pieces):
        joint = tenon_valide(doc, pieces)
        double_cliquer(joint)
        widget(panneau(), "TenonLengthAuto").setChecked(False)
        saisir(widget(panneau(), "TenonLength"), 100.0)
        erreur = widget(panneau(), "errorLabel")
        problemes = ecarts("message", (erreur.isHidden(), bool(erreur.text())), (False, True))
        valider()
        return [
            *problemes,
            *ecarts("valeur gardée", joint.TenonLength.Value, 100.0),
            *ecarts("assemblage en erreur", "Invalid" in joint.State, True),
            *ecarts("entrées", doc.UndoNames, [MODIFICATION]),
        ]


def verifier_parametre_pilote() -> list[str]:
    """E4 : paramètre piloté par une expression : champ et case inactifs, jamais écrit."""
    with cadre("VerifParametrePilote") as (doc, pieces):
        joint = tenon_valide(doc, pieces)
        joint.setExpression("TenonWidth", "30 mm")
        doc.recompute()
        double_cliquer(joint)
        form = panneau()
        champ, auto = widget(form, "TenonWidth"), widget(form, "TenonWidthAuto")
        problemes = [
            *ecarts("champ inactif", champ.isEnabled(), False),
            *ecarts("case inactive", auto.isEnabled(), False),
            *ecarts("valeur pilotée", valeur(champ), 30.0),
        ]
        saisir(champ, 12.0)
        auto.setChecked(True)
        valider()
        return [
            *problemes,
            *ecarts("valeur", joint.TenonWidth.Value, 30.0),
            *ecarts("expression", joint.ExpressionEngine, [("TenonWidth", "30 mm")]),
        ]


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
    trouves = [w for w in QtGui.QApplication.allWidgets() if w.objectName() == "WoodPartTaskPanel"]
    return trouves[0].lengthEdit


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


VERIFICATIONS_PANNEAU_ASSEMBLAGE: tuple[Callable[[], list[str]], ...] = (
    verifier_formulaire_du_tenon_mortaise,
    verifier_formulaire_des_tourillons,
    verifier_case_auto,
    verifier_inverser,
    verifier_creation_validee,
    verifier_creation_annulee,
    verifier_modification,
    verifier_libelles_en_texte_brut,
    verifier_erreur_affichee,
    verifier_parametre_pilote,
    verifier_std_undo_pendant_la_creation,
    verifier_fermeture_forcee_depuis_la_piece_usinee,
    verifier_aucun_observateur_apres_le_panneau,
    verifier_refus_visible,
)
