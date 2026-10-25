# SPDX-License-Identifier: LGPL-2.1-or-later
"""Vérifications d'interface de la Distance gardée (DI-c, critère F8, ADR 0022).

Module importé par ``verifier_atelier.py`` (lancé par FreeCAD hors écran) : chaque
vérification renvoie la liste de ses problèmes. Aucun clic de souris : sélection par script,
double-clic = appel de ``doubleClicked`` du ViewProvider, boutons = ``click()``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import FreeCADGui as Gui
from PySide import QtGui

from freecad.menuiserie import api
from tests.elements_choisis import Point, element_name
from tests.gui.verifications_distance import COMMANDE, FORM, TRANSACTION
from tests.gui.verifications_ensemble import pieces_du_bureau, regrouper
from tests.gui.verifications_panneau import (
    annuler,
    ecarts,
    formulaire_nomme,
    saisir,
    valider,
)

FORM_GARDEE = "KeptDistancePanel"
BAS_JOUE: Point = (11, 280, 0)
BAS_VOILE: Point = (600, 450, 320)


def distances(doc: Any) -> list[Any]:
    return [o for o in doc.Objects if o.Name.startswith("Distance")]


def haut_du_voile(bureau: Any) -> float:
    return float(bureau.bounds("V")[2][1])


def bas_du_voile(bureau: Any) -> float:
    return float(bureau.bounds("V")[2][0])


def ouvrir(bureau: Any) -> Any:
    """Bas de la joue gauche et bas du voile sélectionnés, commande lancée ; le formulaire."""
    Gui.Selection.clearSelection()
    for repere, proche in (("JG", BAS_JOUE), ("V", BAS_VOILE)):
        piece = bureau.parts[repere]
        Gui.Selection.addSelection(piece, element_name(piece, "Face", proche))
    bureau.doc.clearUndos()
    Gui.Command.get(COMMANDE).run()
    return formulaire_nomme(FORM)


def enfant(form: Any, genre: type, nom: str) -> Any:
    return form.findChild(genre, nom)


def verifier_case_garder() -> list[str]:
    """F8 : case cochée et active dans un ensemble ; grisée avec infobulle hors ensemble."""
    problemes: list[str] = []
    with pieces_du_bureau("GardeCase") as bureau:
        regrouper(bureau)
        form = ouvrir(bureau)
        if form is None:
            return ["panneau absent (ensemble)"]
        case = enfant(form, QtGui.QCheckBox, "keepCheck")
        problemes += ecarts("case active", case.isEnabled(), True)
        problemes += ecarts("case cochée", case.isChecked(), True)
        annuler()
    with pieces_du_bureau("GardeHorsEnsemble") as bureau:
        form = ouvrir(bureau)
        if form is None:
            return [*problemes, "panneau absent (hors ensemble)"]
        case = enfant(form, QtGui.QCheckBox, "keepCheck")
        problemes += ecarts("case grisée", case.isEnabled(), False)
        problemes += ecarts("case décochée", case.isChecked(), False)
        problemes += ecarts("infobulle de la raison", bool(case.toolTip().strip()), True)
        annuler()
    return problemes


def verifier_creation_de_la_distance() -> list[str]:
    """F5/F8 : « OK » crée la Distance en une seule entrée d'annulation, dans l'ensemble."""
    problemes: list[str] = []
    with pieces_du_bureau("GardeCreation") as bureau:
        regrouper(bureau)
        form = ouvrir(bureau)
        saisir(enfant(form, QtGui.QWidget, "distanceEdit"), 340)
        valider()
        trouvees = distances(bureau.doc)
        problemes += ecarts("une Distance", len(trouvees), 1)
        problemes += ecarts("entrées d'annulation", bureau.doc.UndoNames, [TRANSACTION])
        problemes += ecarts("voile déplacé", bas_du_voile(bureau), 340.0)
        if trouvees:
            problemes += ecarts("valeur", round(trouvees[0].Value.Value, 3), 340.0)
            problemes += ecarts("libellé", trouvees[0].Label.startswith("Distance : "), True)
        bureau.doc.undo()
        problemes += ecarts("après annulation", len(distances(bureau.doc)), 0)
        problemes += ecarts("voile revenu", bas_du_voile(bureau), 320.0)
    return problemes


def verifier_double_clic_sur_la_distance() -> list[str]:
    """F8 : double-clic = panneau (valeur, case cochée) ; la saisie déplace les pièces ;
    décocher puis « OK » supprime la Distance."""
    problemes: list[str] = []
    with pieces_du_bureau("GardeDoubleClic") as bureau:
        regrouper(bureau)
        form = ouvrir(bureau)
        valider()
        trouvees = distances(bureau.doc)
        if not trouvees or form is None:
            return ["Distance non créée"]
        distance = trouvees[0]
        bureau.doc.clearUndos()
        vobj = distance.ViewObject
        problemes += ecarts("ViewProvider", vobj.Proxy is not None, True)
        vobj.Proxy.doubleClicked(vobj)
        form = formulaire_nomme(FORM_GARDEE)
        if form is None:
            return [*problemes, "panneau de la Distance absent"]
        champ = enfant(form, QtGui.QWidget, "distanceEdit")
        case = enfant(form, QtGui.QCheckBox, "keepCheck")
        problemes += ecarts("valeur", round(float(champ.property("rawValue")), 3), 320.0)
        problemes += ecarts("case cochée", case.isChecked(), True)
        entre = enfant(form, QtGui.QLabel, "betweenLabel").text()
        problemes += ecarts("entre", "Joue gauche" in entre and "Voile" in entre, True)
        saisir(champ, 360)
        problemes += ecarts("voile suit la saisie", bas_du_voile(bureau), 360.0)
        valider()
        problemes += ecarts("panneau fermé", bool(Gui.Control.activeDialog()), False)
        problemes += ecarts("valeur gardée", round(distance.Value.Value, 3), 360.0)
        problemes += ecarts("entrées d'annulation", len(bureau.doc.UndoNames), 1)
        vobj.Proxy.doubleClicked(vobj)
        case = enfant(formulaire_nomme(FORM_GARDEE), QtGui.QCheckBox, "keepCheck")
        case.setChecked(False)
        valider()
        problemes += ecarts("Distance supprimée", len(distances(bureau.doc)), 0)
        problemes += ecarts("voile resté", bas_du_voile(bureau), 360.0)
    return problemes


def verifier_annuler_le_panneau_de_la_distance() -> list[str]:
    """F8 : « Annuler » rétablit la valeur et les pièces."""
    problemes: list[str] = []
    with pieces_du_bureau("GardeAnnule") as bureau:
        regrouper(bureau)
        ouvrir(bureau)
        valider()
        distance = distances(bureau.doc)[0]
        vobj = distance.ViewObject
        vobj.Proxy.doubleClicked(vobj)
        form = formulaire_nomme(FORM_GARDEE)
        saisir(enfant(form, QtGui.QWidget, "distanceEdit"), 400)
        annuler()
        problemes += ecarts("valeur", round(distance.Value.Value, 3), 320.0)
        problemes += ecarts("voile", bas_du_voile(bureau), 320.0)
    return problemes


def verifier_rangee_bloquee() -> list[str]:
    """F4 : voile verrouillé : message, bouton « Ne plus garder et appliquer » ; ce bouton
    applique la distance sans objet Distance."""
    problemes: list[str] = []
    with pieces_du_bureau("GardeBloquee") as bureau:
        regrouper(bureau)
        api.set_member_options(bureau.parts["V"], locked=True)
        form = ouvrir(bureau)
        if form is None:
            return ["panneau absent"]
        bouton = enfant(form, QtGui.QPushButton, "noKeepButton")
        problemes += ecarts("bouton caché d'abord", bouton.isVisibleTo(form), False)
        saisir(enfant(form, QtGui.QWidget, "distanceEdit"), 340)
        valider()
        erreur = enfant(form, QtGui.QLabel, "errorLabel")
        problemes += ecarts("panneau resté ouvert", bool(Gui.Control.activeDialog()), True)
        problemes += ecarts("message", bool(erreur.text().strip()), True)
        problemes += ecarts("bouton visible", bouton.isVisibleTo(form), True)
        problemes += ecarts("aucune Distance", len(distances(bureau.doc)), 0)
        bouton.click()
        problemes += ecarts("panneau fermé", bool(Gui.Control.activeDialog()), False)
        problemes += ecarts("aucune Distance (après)", len(distances(bureau.doc)), 0)
        problemes += ecarts("voile déplacé", haut_du_voile(bureau) > 0, True)
    return problemes


VERIFICATIONS_DISTANCE_GARDEE: tuple[Callable[[], list[str]], ...] = (
    verifier_case_garder,
    verifier_creation_de_la_distance,
    verifier_double_clic_sur_la_distance,
    verifier_annuler_le_panneau_de_la_distance,
    verifier_rangee_bloquee,
)
