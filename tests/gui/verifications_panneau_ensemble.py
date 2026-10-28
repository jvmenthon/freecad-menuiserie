# SPDX-License-Identifier: LGPL-2.1-or-later
"""Vérifications d'interface du panneau de l'ensemble (J4c, critères P3 à P5, et partie
automatisable du scénario P7 de ``docs/specs/J4-ensembles.md``).

Module importé par ``verifier_atelier.py`` (lancé par FreeCAD hors écran). Les champs sont
manipulés comme par l'utilisateur, par leurs propriétés et signaux Qt ; « OK » et « Annuler »
passent par le dialogue actif de FreeCAD.
"""

from __future__ import annotations

import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui

from freecad.menuiserie import api
from tests.gui.verifications_ensemble import (
    FORM,
    VP_ENSEMBLE,
    classe_du_proxy,
    pieces_du_bureau,
    regrouper,
)
from tests.gui.verifications_panneau import annuler, ecarts, formulaire_nomme, saisir, valider
from tests.gui.verifications_panneau_assemblage import widget
from tests.integration.bureau import LAYOUT, Bureau

MODIFIER = "Modifier l'ensemble"
BORDS = ("Left", "Right", "Front", "Back", "Bottom", "Top")
ROLE = QtCore.Qt.ItemDataRole.UserRole


def panneau() -> Any:
    return formulaire_nomme(FORM)


def ouvrir(ensemble: Any) -> Any:
    """Double-clic sur l'ensemble : formulaire du panneau (``None`` s'il ne s'ouvre pas)."""
    vobj = ensemble.ViewObject
    vobj.Proxy.doubleClicked(vobj)
    return panneau()


def lignes(form: Any) -> list[tuple[str, ...]]:
    arbre = widget(form, "membersTree")
    items = [arbre.topLevelItem(i) for i in range(arbre.topLevelItemCount())]
    return [tuple(item.text(c) for c in range(3)) for item in items]


def choisir_membre(form: Any, obj: Any) -> None:
    arbre = widget(form, "membersTree")
    for i in range(arbre.topLevelItemCount()):
        item = arbre.topLevelItem(i)
        item.setSelected(item.data(0, ROLE) == obj.Name)


def distances(form: Any) -> dict[str, float]:
    return {b: round(float(widget(form, f"distance{b}").property("rawValue")), 3) for b in BORDS}


def cases(form: Any) -> dict[str, bool]:
    return {b: bool(widget(form, f"fixed{b}").isChecked()) for b in BORDS}


def bouton_ok() -> Any:
    """Bouton « OK » du panneau de tâche ouvert (``None`` s'il n'est pas trouvé)."""
    for boite in Gui.getMainWindow().findChildren(QtGui.QDialogButtonBox):
        if isinstance(boite.parent(), QtGui.QMessageBox):  # boîte de refus, pas le panneau
            continue
        bouton = boite.button(QtGui.QDialogButtonBox.Ok)
        if bouton is not None:
            return bouton
    return None


@contextmanager
def bureau_regroupe(nom: str) -> Iterator[Bureau]:
    """Bureau sans assemblage regroupé dans « Bureau », historique vidé."""
    with pieces_du_bureau(nom) as bureau:
        regrouper(bureau)
        yield bureau


# --- P3 : formulaire ------------------------------------------------------------------------


def verifier_formulaire_de_l_ensemble() -> list[str]:
    """P3 : cotes, liste des membres (position, « Suit »), six distances et cases « fixe » du
    membre choisi, bouton « Relier les pièces »."""
    with bureau_regroupe("VerifPanneauEnsemble") as bureau:
        form = ouvrir(bureau.furniture)
        if form is None:
            return ["panneau non ouvert"]
        cotes = [
            round(float(widget(form, n).property("rawValue"))) for n in ("Width", "Depth", "Height")
        ]
        choisir_membre(form, bureau.parts["JG"])
        return [
            *ecarts("titre", form.windowTitle(), "Modifier « Bureau »"),
            *ecarts("cotes", cotes, [1200, 600, 750]),
            *ecarts(
                "membres",
                sorted(lignes(form)),
                sorted(
                    [
                        ("Plateau", "Reste en place", "étirée, déplacée"),
                        # Sa position suit sa propre épaisseur (ADR 0019).
                        ("Joue gauche", "Reste en place", "étirée, déplacée"),
                        ("Joue droite", "Reste en place", "étirée, déplacée"),
                        ("Voile", "Reste en place", "étirée, déplacée"),
                    ]
                ),
            ),
            *ecarts(
                "pièce choisie",
                widget(form, "memberLabel").text(),
                "Pièce choisie : « Joue gauche »",
            ),
            *ecarts(
                "distances",
                distances(form),
                {
                    "Left": 0.0,
                    "Right": 1178.0,
                    "Front": 0.0,
                    "Back": 40.0,
                    "Bottom": 0.0,
                    "Top": 30.0,
                },
            ),
            *ecarts(
                "cases",
                cases(form),
                {
                    "Left": True,
                    "Right": False,
                    "Front": True,
                    "Back": True,
                    "Bottom": True,
                    "Top": True,
                },
            ),
            *ecarts("bouton Relier", widget(form, "rebindButton").text(), "Relier les pièces"),
        ]


def verifier_saisies_de_l_ensemble() -> list[str]:
    """P3 : profondeur 600 → 800 (les joues suivent), « fixe » décoché puis recoché, voile en
    proportion, distance saisie sans toucher à la case, refus effacé au changement de pièce ;
    « OK » = une entrée."""
    with bureau_regroupe("VerifSaisiesEnsemble") as bureau:
        form = ouvrir(bureau.furniture)
        saisir(widget(form, "Depth"), 800.0)
        problemes = [
            *ecarts("profondeur", bureau.furniture.Depth.Value, 800.0),
            *ecarts("joue suit", bureau.sizes("JG")[1], 760.0),
            *ecarts("voile suit", bureau.bounds("V")[1], (641.0, 659.0)),
        ]
        choisir_membre(form, bureau.parts["JG"])
        widget(form, "fixedBack").setChecked(False)
        problemes += [
            *ecarts("FixedBack décoché", bureau.parts["JG"].FixedBack, False),
            *ecarts("liaison retirée", "Width" in bureau.expressions("JG"), False),
        ]
        widget(form, "fixedBack").setChecked(True)
        problemes += ecarts(
            "liaison reposée", bureau.expressions("JG").get("Width"), "<<Bureau>>.Depth - 40 mm"
        )
        choisir_membre(form, bureau.parts["V"])
        widget(form, "fixedBack").setChecked(False)
        combo = widget(form, "modeCombo")
        combo.setCurrentIndex(combo.findData("Proportional"))
        saisir(widget(form, "distanceLeft"), 30.0)
        problemes += [
            *ecarts("mode", bureau.parts["V"].PositionMode, "Proportional"),
            *ecarts("voile déplacé", bureau.bounds("V")[0], (30.0, 1178.0)),
            *ecarts("case inchangée", widget(form, "fixedLeft").isChecked(), True),
            *ecarts(
                "colonne Suit",
                ("Voile", "Proportion", "étirée, déplacée, proportion") in lignes(form),
                True,
            ),
        ]
        choisir_membre(form, bureau.parts["P"])
        saisir(widget(form, "distanceLeft"), 1199.95)
        refus = widget(form, "editErrorLabel").text()
        choisir_membre(form, bureau.parts["JG"])
        problemes += [
            *ecarts("refus affiché", "trop petite" in refus, True),
            *ecarts("refus effacé (autre pièce)", widget(form, "editErrorLabel").text(), ""),
        ]
        valider()
        problemes += ecarts("entrées", bureau.doc.UndoNames, [MODIFIER])
        form = ouvrir(bureau.furniture)
        saisir(widget(form, "Depth"), 900.0)
        annuler()
        bureau.doc.recompute()
        return [
            *problemes,
            *ecarts("Annuler : profondeur", bureau.furniture.Depth.Value, 800.0),
            *ecarts("Annuler : entrées", bureau.doc.UndoNames, [MODIFIER]),
        ]


# --- P4 : refus et avertissements -----------------------------------------------------------


@contextmanager
def vue_rapport() -> Iterator[list[str]]:
    """Avertissements écrits dans la vue rapport pendant le bloc."""
    messages: list[str] = []
    original = App.Console.PrintWarning
    App.Console.PrintWarning = lambda texte: messages.append(str(texte))
    try:
        yield messages
    finally:
        App.Console.PrintWarning = original


def verifier_refus_d_une_cote() -> list[str]:
    """P4 : cote refusée affichée sous les champs, rien d'écrit, « OK » inactif ; une cote
    acceptée efface le refus."""
    with bureau_regroupe("VerifRefusEnsemble") as bureau:
        form = ouvrir(bureau.furniture)
        saisir(widget(form, "Depth"), 30.0)
        refus = widget(form, "refusalLabel")
        ok = bouton_ok()
        problemes = [
            *ecarts(
                "refus affiché", (refus.isHidden(), "Joue gauche" in refus.text()), (False, True)
            ),
            *ecarts("rien d'écrit", bureau.furniture.Depth.Value, 600.0),
            *ecarts("OK trouvé", ok is not None, True),
            *ecarts("OK inactif", ok is not None and ok.isEnabled(), False),
            *ecarts("OK refusé", bool(Gui.Control.activeTaskDialog().accept()), False),
            *ecarts("panneau resté ouvert", panneau() is not None, True),
        ]
        saisir(widget(form, "Depth"), 700.0)
        return [
            *problemes,
            *ecarts("refus effacé", refus.isHidden(), True),
            *ecarts("OK actif", ok is not None and ok.isEnabled(), True),
            *ecarts("cote écrite", bureau.furniture.Depth.Value, 700.0),
        ]


def verifier_avertissements_de_l_ensemble() -> list[str]:
    """P4 : formule de l'utilisateur et pièce qui dépasse, dans le panneau et la vue rapport."""
    with pieces_du_bureau("VerifAvertissementsEnsemble") as bureau:
        bureau.parts["V"].setExpression("Placement.Base.y", "<<Plateau>>.Width - 141 mm")
        regrouper(bureau)
        for joue in ("JG", "JD"):
            api.set_member_options(bureau.parts[joue], fixed={"Back": False})
        form = ouvrir(bureau.furniture)
        avis = widget(form, "noticesLabel")
        problemes = ecarts("formule", "Placement.Base.y" in avis.text(), True)
        with vue_rapport() as messages:
            saisir(widget(form, "Depth"), 500.0)
        return [
            *problemes,
            *ecarts("dépasse : panneau", "dépasserait" in avis.text(), True),
            *ecarts("dépasse : vue rapport", any("dépasserait" in m for m in messages), True),
        ]


# --- P5 : champs pilotés --------------------------------------------------------------------


def verifier_champs_pilotes() -> list[str]:
    """P5 : cote d'un sous-ensemble pilotée par le bureau, inactive et jamais écrite ; distance
    d'une face pilotée par une formule, champ et case inactifs, infobulle « formule »."""
    with pieces_du_bureau("VerifChampsPilotes") as bureau:
        bureau.parts["V"].setExpression("Placement.Base.y", "<<Plateau>>.Width - 141 mm")
        caisson, _ = api.make_furniture([bureau.parts[m] for m in ("JG", "JD", "V")], "Caisson")
        api.make_furniture([bureau.parts["P"], caisson], label="Bureau")
        form = ouvrir(caisson)
        largeur = widget(form, "Width")
        saisir(largeur, 500.0)
        choisir_membre(form, bureau.parts["V"])
        arriere = widget(form, "distanceBack")
        problemes = [
            *ecarts("cote pilotée inactive", largeur.isEnabled(), False),
            *ecarts("cote pilotée non écrite", caisson.Width.Value, 1200.0),
            *ecarts("distance pilotée inactive", arriere.isEnabled(), False),
            *ecarts("case pilotée inactive", widget(form, "fixedBack").isEnabled(), False),
            *ecarts("infobulle", "formule" in arriere.toolTip().lower(), True),
            *ecarts("distance libre active", widget(form, "distanceLeft").isEnabled(), True),
        ]
        annuler()
        return problemes


# --- P7 : scénario du livrable (partie automatisable) ---------------------------------------


def verifier_scenario_du_bureau() -> list[str]:
    """P7 : profondeur 800 par le panneau, annuler, rétablir, enregistrer, rouvrir."""
    with bureau_regroupe("VerifScenarioBureau") as bureau:
        form = ouvrir(bureau.furniture)
        saisir(widget(form, "Depth"), 800.0)
        valider()
        doc = bureau.doc
        doc.undo()
        doc.recompute()
        problemes = ecarts("annulé", bureau.sizes("JG")[1], 560.0)
        doc.redo()
        doc.recompute()
        problemes += ecarts("rétabli", bureau.sizes("JG")[1], 760.0)
        chemin = Path(tempfile.mkdtemp()) / "bureau.FCStd"
        doc.saveAs(str(chemin))
        App.closeDocument(doc.Name)
        rouvert = App.openDocument(str(chemin))
        try:
            ensemble = rouvert.getObjectsByLabel("Bureau")[0]
            enfants = ensemble.ViewObject.Proxy.claimChildren()
            problemes += [
                *ecarts("ViewProvider rouvert", classe_du_proxy(ensemble.ViewObject), VP_ENSEMBLE),
                *ecarts("enfants rouverts", len(enfants), len(LAYOUT)),
                *ecarts("non modifié", Gui.getDocument(rouvert.Name).Modified, False),
            ]
        finally:
            App.closeDocument(rouvert.Name)
        return problemes


VERIFICATIONS_PANNEAU_ENSEMBLE: tuple[Callable[[], list[str]], ...] = (
    verifier_formulaire_de_l_ensemble,
    verifier_saisies_de_l_ensemble,
    verifier_refus_d_une_cote,
    verifier_avertissements_de_l_ensemble,
    verifier_champs_pilotes,
    verifier_scenario_du_bureau,
)
