# SPDX-License-Identifier: LGPL-2.1-or-later
"""Vérifications d'interface de la répétition jusqu'à une butée (ADR 0047) : bouton « Butée… »
par axe, choix dans la vue 3D (sélection simulée par ``Gui.Selection.addSelection``), nom de la
butée et bouton pour l'enlever, longueur calculée en lecture seule, case « Déduire l'épaisseur de
la pièce », « Modifier la répétition » prérempli. Module importé par ``verifier_atelier.py`` :
chaque vérification renvoie la liste de ses problèmes.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from freecad.menuiserie import api
from tests.gui.verifications_ensemble import lancer
from tests.gui.verifications_panneau import avec_document, choisir, ecarts, saisir, valider
from tests.gui.verifications_panneau_assemblage import widget
from tests.gui.verifications_panneau_ensemble import bouton_ok
from tests.gui.verifications_repetition import (
    MODIFIER,
    REPETER,
    copies_de,
    panneau,
    positions_x,
    source,
)

MUR_X = 1300.0  # face avant du mur : le barreau (300 mm) en part à X = 0


def mur(doc: Any) -> tuple[Any, str]:
    """Mur de 20 mm sur X dont la face avant (X = 1300) est le deuxième élément choisi."""
    piece = api.make_wood_part(20, 200, 200, "chene", mark="Mur", doc=doc)
    piece.Placement = App.Placement(App.Vector(MUR_X, 0, 0), App.Rotation())
    doc.recompute()
    for index, face in enumerate(piece.Shape.Faces, start=1):
        if face.BoundBox.XMin == face.BoundBox.XMax == MUR_X:
            return piece, f"Face{index}"
    raise AssertionError("face avant introuvable")


def cliquer_dans_la_vue(doc: Any, piece: Any, sous_element: str = "") -> None:
    """Clic simulé dans la vue 3D, puis traitement des événements différés du panneau."""
    Gui.Selection.addSelection(doc.Name, piece.Name, sous_element)
    QtCore.QCoreApplication.processEvents()


def _pas(rep: Any) -> list[float]:
    return [round(x, 2) for x in positions_x(rep)]


def _butee(doc: Any) -> list[str]:
    piece, face = mur(doc)
    lancer(REPETER, source(doc))
    form, rep = panneau(), doc.getObject("Repeat")
    if form is None or rep is None:
        return ["panneau « Répéter » non ouvert"]
    choisir(widget(form, "spacing"), "CountOnSpan")
    widget(form, "countX").setValue(4)
    saisir(widget(form, "spanX"), 600.0)
    problemes = ecarts(
        "bouton Butée visible",
        widget(form, "stopX").isHidden() or widget(form, "deductThickness").isHidden(),
        False,
    )
    widget(form, "stopX").click()
    cliquer_dans_la_vue(doc, piece, face)
    problemes += [
        *ecarts("nom de la butée", "Mur" in widget(form, "stopNameX").text(), True),
        *ecarts("longueur calculée", round(rep.Span.Value, 3), MUR_X),
        *ecarts("longueur en lecture seule", widget(form, "spanX").isEnabled(), False),
        *ecarts("à fleur", _pas(rep), [333.33, 666.67, 1000.0]),
        *ecarts("dernière copie à X = 1300", round(copies_de(rep)[-1].Shape.BoundBox.XMax), 1300),
        *ecarts("pas de collision", widget(form, "warningLabel").isHidden(), True),
    ]
    widget(form, "deductThickness").setChecked(False)
    problemes += [
        *ecarts("sans déduction", _pas(rep), [433.33, 866.67, 1300.0]),
        *ecarts("collision signalée", "collision" in widget(form, "warningLabel").text(), True),
        *ecarts("« OK » reste actif", bouton_ok().isEnabled(), True),
    ]
    widget(form, "deductThickness").setChecked(True)
    widget(form, "stopClearX").click()
    problemes += [
        *ecarts("butée enlevée", widget(form, "stopNameX").text(), ""),
        *ecarts("longueur de nouveau saisie", widget(form, "spanX").isEnabled(), True),
        *ecarts("longueur gardée", round(rep.Span.Value, 3), MUR_X),
    ]
    widget(form, "stopX").click()
    widget(form, "stopX").click()  # second clic : choix annulé
    cliquer_dans_la_vue(doc, piece, face)
    problemes += ecarts("choix annulé : rien de choisi", widget(form, "stopNameX").text(), "")
    widget(form, "stopX").click()
    cliquer_dans_la_vue(doc, piece, "Edge1")
    problemes += [
        *ecarts(
            "arête refusée", "ni une face ni un sommet" in widget(form, "errorLabel").text(), True
        ),
        *ecarts("« OK » grisé", bouton_ok().isEnabled(), False),
    ]
    widget(form, "stopClearX").click()
    widget(form, "stopX").click()
    cliquer_dans_la_vue(doc, piece, face)
    valider()
    rep = doc.getObject("Repeat")
    return [
        *problemes,
        *ecarts("butée enregistrée", (rep.Stop[0].Name, rep.Stop[1]), (piece.Name, [face])),
        *ecarts("entrées", doc.UndoNames, ["Répéter"]),
    ]


def verifier_butee_dans_le_panneau() -> list[str]:
    """Bouton « Butée… », sélection simulée, longueur calculée en lecture seule, case d'épaisseur,
    retrait de la butée, arête refusée, une seule entrée d'annulation."""
    return avec_document("VerifButee", _butee)


def _modifier(doc: Any) -> list[str]:
    piece, face = mur(doc)
    params = api.RepeatParams(
        spacing=api.SpacingMode.COUNT_ON_SPAN,
        deduct_thickness=False,
        grid=(api.AxisRepeat(api.RepeatAxis.X, 4, span=1000.0),),
    )
    rep = api.make_repeat([source(doc)], params, stops={api.RepeatAxis.X: api.Stop(piece, face)})
    doc.clearUndos()
    lancer(MODIFIER, copies_de(rep)[0])
    form = panneau()
    if form is None:
        return ["panneau « Modifier la répétition » non ouvert"]
    problemes = [
        *ecarts("butée préremplie", "Mur" in widget(form, "stopNameX").text(), True),
        *ecarts("case décochée préremplie", widget(form, "deductThickness").isChecked(), False),
        *ecarts("mode préservé", widget(form, "spacing").currentData(), "CountOnSpan"),
    ]
    widget(form, "countX").setValue(5)
    problemes += ecarts("5 éléments jusqu'à la butée", _pas(rep), [325.0, 650.0, 975.0, 1300.0])
    choisir(widget(form, "spacing"), "CountAndStep")
    saisir(widget(form, "stepX"), 400.0)
    problemes += ecarts("nombre et pas : butée retirée", rep.Stop is None, True)
    valider()
    return problemes + ecarts("entrées", doc.UndoNames, ["Modifier la répétition"])


def verifier_modifier_une_repetition_a_butee() -> list[str]:
    """« Modifier la répétition » rouvre la butée et la case d'épaisseur ; le mode nombre et pas
    retire la butée."""
    return avec_document("VerifButeeModifie", _modifier)


VERIFICATIONS_REPETITION_BUTEE: tuple[Callable[[], list[str]], ...] = (
    verifier_butee_dans_le_panneau,
    verifier_modifier_une_repetition_a_butee,
)
