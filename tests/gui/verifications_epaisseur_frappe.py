# SPDX-License-Identifier: LGPL-2.1-or-later
"""Épaisseur tapée touche par touche et aperçu 3D des choix (ADR 0060, retours de jv
2026-11-15).

1. Taper « 22 » à la place de « 18 » passe par « 2 » : trop mince, aucun choix ne garde la queue
   d'aronde. Rien n'est écrit (pas d'assemblage en erreur dans la vue rapport), « OK » est
   refusé ; la touche suivante applique « 22 ».
2. Passer de « vers l'intérieur » à « vers l'extérieur » change la vue 3D sans recalcul du
   document : l'autre pièce, allongée, est recalculée par le panneau.
3. Une épaisseur qui ne défait rien propose aussi les choix, « Laisser en l'état » en tête.

Les touches sont envoyées au champ par ``sendEvent`` (pas de clic de souris hors écran). Module
importé par ``verifier_atelier.py``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import FreeCADGui as Gui
from PySide import QtCore, QtGui

from freecad.menuiserie import api
from freecad.menuiserie.features.machined_part import machined_part_of
from tests.gui.verifications_assemblages import cadre
from tests.gui.verifications_epaisseur_cote import encadre
from tests.gui.verifications_panneau import annuler, ecarts, ouvrir_par_double_clic, valider
from tests.gui.verifications_panneau_assemblage import widget
from tests.gui.verifications_queue_aronde import planches


def _touche(champ: Any, code: int, texte: str = "") -> None:
    for genre in (QtCore.QEvent.KeyPress, QtCore.QEvent.KeyRelease):
        evenement = QtGui.QKeyEvent(genre, code, QtCore.Qt.NoModifier, texte)
        QtGui.QApplication.sendEvent(champ, evenement)
    QtGui.QApplication.processEvents()


def _taper(champ: Any, texte: str) -> None:
    """``texte`` tapé à la place du contenu du champ, touche par touche."""
    editeur = champ.lineEdit() if hasattr(champ, "lineEdit") else champ
    editeur.setFocus()
    editeur.selectAll()
    for caractere in texte:
        _touche(editeur, ord(caractere.upper()), caractere)


def _invalides(doc: Any) -> list[str]:
    return [o.Label for o in doc.Objects if "Invalid" in o.State]


def verifier_frappe_passe_par_deux() -> list[str]:
    """« 22 » tapé : l'étape « 2 » n'écrit rien et ne met aucun assemblage en erreur."""
    with cadre("VerifEpaisseurFrappe") as (doc, _pieces):
        hote, invitee = planches(doc)
        api.make_dovetail(hote, invitee)
        doc.recompute()
        form = ouvrir_par_double_clic(invitee)
        if form is None:
            return ["panneau de la pièce non ouvert"]
        problemes: list[str] = []
        _taper(form.thicknessEdit, "2")
        non_appliquee = widget(form, "conflictNotApplied")
        problemes += [
            *ecarts("« 2 » : épaisseur non écrite", invitee.Thickness.Value, 18.0),
            *ecarts(
                "« 2 » : encadré affiché", encadre(form)["thicknessConflict"].isHidden(), False
            ),
            *ecarts("« 2 » : non appliquée dite", non_appliquee.isHidden(), False),
            *ecarts("« 2 » : objets en erreur", _invalides(doc), []),
        ]
        _touche(form.thicknessEdit.lineEdit(), QtCore.Qt.Key_2, "2")
        problemes += [
            *ecarts("« 22 » : épaisseur", invitee.Thickness.Value, 22.0),
            *ecarts("« 22 » : message masqué", non_appliquee.isHidden(), True),
            *ecarts("« 22 » : objets en erreur", _invalides(doc), []),
        ]
        annuler()
        return problemes


def verifier_bloque_refuse_ok() -> list[str]:
    """Épaisseur 2 : « OK » refusé (le panneau reste ouvert), « Revenir » le rend."""
    with cadre("VerifEpaisseurBloquee") as (doc, _pieces):
        hote, invitee = planches(doc)
        api.make_dovetail(hote, invitee)
        doc.recompute()
        form = ouvrir_par_double_clic(invitee)
        if form is None:
            return ["panneau de la pièce non ouvert"]
        _taper(form.thicknessEdit, "2")
        refuse = not Gui.Control.activeTaskDialog().accept()
        encadre(form)["conflict_revert"].click()
        problemes = [
            *ecarts("OK refusé", refuse, True),
            *ecarts(
                "après Revenir : encadré masqué",
                encadre(form)["thicknessConflict"].isHidden(),
                True,
            ),
            *ecarts("épaisseur", invitee.Thickness.Value, 18.0),
        ]
        annuler()
        return problemes


def verifier_choix_change_la_vue_3d() -> list[str]:
    """Intérieur puis extérieur puis intérieur : la forme de H (brute et pièce usinée) suit sans
    recalcul du document."""
    with cadre("VerifEpaisseurApercu") as (doc, _pieces):
        hote, invitee = planches(doc)
        api.make_dovetail(hote, invitee)
        doc.recompute()
        form = ouvrir_par_double_clic(invitee)
        if form is None:
            return ["panneau de la pièce non ouvert"]
        _taper(form.thicknessEdit, "30")
        usinee = machined_part_of(hote)

        def longueurs() -> tuple[float, float]:
            visible = usinee if usinee is not None else hote
            return (round(hote.Shape.BoundBox.XLength, 3), round(visible.Shape.BoundBox.XLength, 3))

        w = encadre(form)
        avant = longueurs()
        w["conflict_extend"].click()
        allongee = longueurs()
        w["conflict_other_side"].click()
        rendue = longueurs()
        problemes = [
            *ecarts("intérieur", avant, (400.0, 400.0)),
            *ecarts("extérieur : H allongée en 3D", allongee, (412.0, 412.0)),
            *ecarts("retour intérieur", rendue, (400.0, 400.0)),
            *ecarts("objets en erreur", _invalides(doc), []),
        ]
        annuler()
        return problemes


def verifier_laisser_en_l_etat() -> list[str]:
    """H épaissie : rien n'est défait (I suit sa face), l'encadré propose quand même les choix,
    « Laisser en l'état » en tête et coché ; « vers l'intérieur » puis « Laisser » (jv)."""
    with cadre("VerifEpaisseurLaisser") as (doc, _pieces):
        hote, invitee = planches(doc)
        api.make_dovetail(hote, invitee)
        doc.recompute()
        form = ouvrir_par_double_clic(hote)
        if form is None:
            return ["panneau de la pièce non ouvert"]
        _taper(form.thicknessEdit, "30")
        laisser = widget(form, "conflict_as_typed")
        w = encadre(form)
        problemes = [
            *ecarts("encadré affiché", w["thicknessConflict"].isHidden(), False),
            *ecarts("laisser visible", laisser.isHidden(), False),
            *ecarts("laisser coché", laisser.isChecked(), True),
            *ecarts("I suit la face", tuple(invitee.Placement.Base), (18.0, 0.0, 30.0)),
            *ecarts("OK accepté", widget(form, "conflictNotApplied").isHidden(), True),
        ]
        w["conflict_other_side"].click()
        problemes += [
            *ecarts("intérieur : I en place", tuple(invitee.Placement.Base), (18.0, 0.0, 18.0)),
            *ecarts("intérieur : H reculée", tuple(hote.Placement.Base), (0.0, 0.0, -12.0)),
        ]
        laisser.click()
        problemes += [
            *ecarts("laisser : H en place", tuple(hote.Placement.Base), (0.0, 0.0, 0.0)),
            *ecarts("objets en erreur", _invalides(doc), []),
        ]
        valider()
        doc.recompute()
        problemes += ecarts("épaisseur gardée", hote.Thickness.Value, 30.0)
        return problemes


VERIFICATIONS_EPAISSEUR_FRAPPE: tuple[Callable[[], list[str]], ...] = (
    verifier_frappe_passe_par_deux,
    verifier_bloque_refuse_ok,
    verifier_choix_change_la_vue_3d,
    verifier_laisser_en_l_etat,
)
