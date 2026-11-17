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
from freecad.menuiserie.gui.task_panels.unlock_widgets import OkGate
from tests.gui.verifications_assemblages import cadre
from tests.gui.verifications_epaisseur_cote import encadre
from tests.gui.verifications_panneau import (
    annuler,
    ecarts,
    ouvrir_par_double_clic,
    saisir,
    valeur,
    valider,
)
from tests.gui.verifications_panneau_assemblage import widget
from tests.gui.verifications_queue_aronde import planches


def _touche(champ: Any, code: int, texte: str = "") -> None:
    for genre in (QtCore.QEvent.KeyPress, QtCore.QEvent.KeyRelease):
        evenement = QtGui.QKeyEvent(genre, code, QtCore.Qt.NoModifier, texte)
        QtGui.QApplication.sendEvent(champ, evenement)
    QtGui.QApplication.processEvents()


def taper(champ: Any, texte: str) -> None:
    """``texte`` tapé à la place du contenu du champ, touche par touche."""
    editeur = champ.lineEdit() if hasattr(champ, "lineEdit") else champ
    editeur.setFocus()
    editeur.selectAll()
    for caractere in texte:
        _touche(editeur, ord(caractere.upper()), caractere)


def invalides(doc: Any) -> list[str]:
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
        taper(form.thicknessEdit, "2")
        non_appliquee = widget(form, "conflictNotApplied")
        problemes += [
            *ecarts("« 2 » : épaisseur non écrite", invitee.Thickness.Value, 18.0),
            *ecarts(
                "« 2 » : encadré affiché", encadre(form)["thicknessConflict"].isHidden(), False
            ),
            *ecarts("« 2 » : non appliquée dite", non_appliquee.isHidden(), False),
            *ecarts("« 2 » : objets en erreur", invalides(doc), []),
        ]
        _touche(form.thicknessEdit.lineEdit(), QtCore.Qt.Key_2, "2")
        problemes += [
            *ecarts("« 22 » : épaisseur", invitee.Thickness.Value, 22.0),
            *ecarts("« 22 » : message masqué", non_appliquee.isHidden(), True),
            *ecarts("« 22 » : objets en erreur", invalides(doc), []),
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
        taper(form.thicknessEdit, "2")
        Gui.Control.activeTaskDialog().accept()
        refuse = bool(Gui.Control.activeDialog())  # panneau resté ouvert
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
        taper(form.thicknessEdit, "30")
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
            *ecarts("objets en erreur", invalides(doc), []),
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
        taper(form.thicknessEdit, "30")
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
            *ecarts("objets en erreur", invalides(doc), []),
        ]
        valider()
        doc.recompute()
        problemes += ecarts("épaisseur gardée", hote.Thickness.Value, 30.0)
        return problemes


def verifier_saisies_successives_laisser() -> list[str]:
    """« 30 » puis « 24 » puis retour à « 18 » avec l'encadré affiché : chaque saisie repart du
    départ ; Annuler du panneau rend tout, sans objet en erreur."""
    with cadre("VerifEpaisseurSuccessives") as (doc, _pieces):
        hote, invitee = planches(doc)
        api.make_dovetail(hote, invitee)
        doc.recompute()
        form = ouvrir_par_double_clic(hote)
        if form is None:
            return ["panneau de la pièce non ouvert"]
        w = encadre(form)
        problemes: list[str] = []
        for texte, valeur in (("30", 30.0), ("24", 24.0)):
            taper(form.thicknessEdit, texte)
            problemes += [
                *ecarts(f"{texte} : encadré affiché", w["thicknessConflict"].isHidden(), False),
                *ecarts(
                    f"{texte} : laisser coché", widget(form, "conflict_as_typed").isChecked(), True
                ),
                *ecarts(f"{texte} : I suit", invitee.Placement.Base.z, valeur),
                *ecarts(f"{texte} : objets en erreur", invalides(doc), []),
            ]
        taper(form.thicknessEdit, "18")
        problemes += [
            *ecarts("18 : encadré masqué", w["thicknessConflict"].isHidden(), True),
            *ecarts("18 : I en place", invitee.Placement.Base.z, 18.0),
        ]
        taper(form.thicknessEdit, "30")
        annuler()
        problemes += [
            *ecarts("Annuler : épaisseur", hote.Thickness.Value, 18.0),
            *ecarts("Annuler : I en place", invitee.Placement.Base.z, 18.0),
            *ecarts("Annuler : objets en erreur", invalides(doc), []),
        ]
        return problemes


def verifier_annuler_apres_exterieur() -> list[str]:
    """Épaisseur de I, « vers l'extérieur » (H allongée), Annuler du panneau : tout est rendu."""
    with cadre("VerifEpaisseurAnnuler") as (doc, _pieces):
        hote, invitee = planches(doc)
        api.make_dovetail(hote, invitee)
        doc.recompute()
        form = ouvrir_par_double_clic(invitee)
        if form is None:
            return ["panneau de la pièce non ouvert"]
        taper(form.thicknessEdit, "30")
        encadre(form)["conflict_extend"].click()
        annuler()
        return [
            *ecarts("épaisseur", invitee.Thickness.Value, 18.0),
            *ecarts(
                "H rendue",
                (hote.Length.Value, tuple(hote.Placement.Base)),
                (400.0, (0.0, 0.0, 0.0)),
            ),
            *ecarts("objets en erreur", invalides(doc), []),
        ]


def verifier_piece_sans_assemblage() -> list[str]:
    """Pièce sans assemblage : pas d'encadré, épaisseur écrite à chaque frappe, « OK » accepté."""
    with cadre("VerifEpaisseurSeule") as (doc, _pieces):
        piece = api.make_wood_part(400, 150, 18, "chene", mark="S", doc=doc)
        doc.recompute()
        form = ouvrir_par_double_clic(piece)
        if form is None:
            return ["panneau de la pièce non ouvert"]
        taper(form.thicknessEdit, "22")
        problemes = [
            *ecarts("encadré masqué", encadre(form)["thicknessConflict"].isHidden(), True),
            *ecarts("épaisseur", piece.Thickness.Value, 22.0),
            *ecarts("aucun message", widget(form, "conflictNotApplied").text(), ""),
        ]
        valider()
        return problemes


def verifier_autre_cote_pendant_blocage() -> list[str]:
    """« 2 » non appliqué, puis longueur modifiée : le champ remontre 18 et « OK » est accepté
    (jamais de « 2 » affiché pour une épaisseur restée à 18)."""
    with cadre("VerifEpaisseurAutreCote") as (doc, _pieces):
        hote, invitee = planches(doc)
        api.make_dovetail(hote, invitee)
        doc.recompute()
        form = ouvrir_par_double_clic(invitee)
        if form is None:
            return ["panneau de la pièce non ouvert"]
        taper(form.thicknessEdit, "2")
        saisir(form.lengthEdit, 390.0)
        problemes = [
            *ecarts("champ rendu", valeur(form.thicknessEdit), 18.0),
            *ecarts("épaisseur", invitee.Thickness.Value, 18.0),
        ]
        valider()
        return [*problemes, *ecarts("fermé par OK", bool(Gui.Control.activeDialog()), False)]


def verifier_ok_partage() -> list[str]:
    """« OK » bloqué par deux sources (refus, encadré) : il ne revient qu'une fois les deux
    levées."""
    boite = QtGui.QDialogButtonBox(QtGui.QDialogButtonBox.Ok | QtGui.QDialogButtonBox.Cancel)
    ok = boite.button(QtGui.QDialogButtonBox.Ok)
    gate = OkGate()
    gate.attach(boite)
    gate.update(True)
    gate.update(True, "thicknessConflict")
    etats = [ok.isEnabled()]
    gate.update(False, "thicknessConflict")
    etats.append(ok.isEnabled())
    gate.update(False)
    etats.append(ok.isEnabled())
    return ecarts("OK", etats, [False, False, True])


VERIFICATIONS_EPAISSEUR_FRAPPE: tuple[Callable[[], list[str]], ...] = (
    verifier_frappe_passe_par_deux,
    verifier_bloque_refuse_ok,
    verifier_choix_change_la_vue_3d,
    verifier_laisser_en_l_etat,
    verifier_saisies_successives_laisser,
    verifier_annuler_apres_exterieur,
    verifier_piece_sans_assemblage,
    verifier_autre_cote_pendant_blocage,
    verifier_ok_partage,
)
