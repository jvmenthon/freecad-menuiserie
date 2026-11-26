# SPDX-License-Identifier: LGPL-2.1-or-later
"""Vérifications d'interface de l'encadré « où ajouter l'épaisseur ? » (ADR 0060, maquette C).

Angle à queue d'aronde (H à plat, I debout) ; épaissir I dans son panneau défait l'assemblage :
l'encadré apparaît sous les cotes, le premier choix possible est coché et appliqué, un choix
impossible est grisé avec sa raison, « Revenir » remet l'ancienne épaisseur dans le champ. Une
seule entrée d'annulation à la validation. Module importé par ``verifier_atelier.py``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import FreeCAD as App

from freecad.menuiserie import api
from freecad.menuiserie.features.repeat import copies_of
from tests.gui.verifications_assemblages import cadre
from tests.gui.verifications_panneau import ecarts, ouvrir_par_double_clic, saisir, valeur, valider
from tests.gui.verifications_panneau_assemblage import widget
from tests.gui.verifications_queue_aronde import planches

DEBOUT = App.Rotation(App.Vector(0, 1, 0), -90)


def encadre(form: Any) -> dict[str, Any]:
    """Widgets de l'encadré, par nom court."""
    noms = (
        "thicknessConflict",
        "conflictTitle",
        "conflict_other_side",
        "conflict_extend",
        "conflict_revert",
        "conflictReason_extend",
    )
    return {nom: widget(form, nom) for nom in noms}


def verifier_encadre_et_choix() -> list[str]:
    """Encadré affiché, « vers l'intérieur » coché et appliqué ; « allonger » puis validation."""
    with cadre("VerifEpaisseurCote") as (doc, _pieces):
        hote, invitee = planches(doc)
        api.make_dovetail(hote, invitee)
        doc.recompute()
        doc.clearUndos()
        form = ouvrir_par_double_clic(invitee)
        if form is None:
            return ["panneau de la pièce non ouvert"]
        saisir(form.thicknessEdit, 30.0)
        w = encadre(form)
        problemes = [
            *ecarts("encadré masqué", w["thicknessConflict"].isHidden(), False),
            *ecarts("titre", w["conflictTitle"].text(), "Queue d'aronde avec « H »."),
            *ecarts("intérieur coché", w["conflict_other_side"].isChecked(), True),
            *ecarts("allonger actif", w["conflict_extend"].isEnabled(), True),
            *ecarts("placement intérieur", tuple(invitee.Placement.Base), (30.0, 0.0, 18.0)),
        ]
        w["conflict_extend"].click()
        problemes += [
            *ecarts("H allongée", hote.Length.Value, 412.0),
            *ecarts("I revenue", tuple(invitee.Placement.Base), (18.0, 0.0, 18.0)),
        ]
        valider()
        doc.recompute()
        problemes += [
            *ecarts("entrées", doc.UndoNames, ["Modifier une pièce de bois"]),
            *ecarts(
                "assemblage",
                [j.State for j in doc.Objects if "Dovetail" in j.Name],
                [["Up-to-date"]],
            ),
        ]
        doc.undo()
        problemes += ecarts("annulé", (hote.Length.Value, invitee.Thickness.Value), (400.0, 18.0))
        return problemes


def verifier_revenir() -> list[str]:
    """« Revenir à 18 mm » : épaisseur rendue, champ remis, encadré masqué."""
    with cadre("VerifEpaisseurRevenir") as (doc, _pieces):
        hote, invitee = planches(doc)
        api.make_dovetail(hote, invitee)
        doc.recompute()
        form = ouvrir_par_double_clic(invitee)
        if form is None:
            return ["panneau de la pièce non ouvert"]
        saisir(form.thicknessEdit, 30.0)
        encadre(form)["conflict_revert"].click()
        return [
            *ecarts("épaisseur", invitee.Thickness.Value, 18.0),
            *ecarts("champ", valeur(form.thicknessEdit), 18.0),
            *ecarts("encadré masqué", encadre(form)["thicknessConflict"].isHidden(), True),
        ]


def verifier_copie_non_modifiable() -> list[str]:
    """Autre pièce = copie d'une répétition : « allonger » grisé, avec la raison."""
    with cadre("VerifEpaisseurCopie") as (doc, _pieces):
        hote, _ = planches(doc)
        params = api.RepeatParams(count=1, step=500.0, axis=api.RepeatAxis.Y)
        copie = copies_of(api.make_repeat([hote], params))[0]
        invitee = api.make_wood_part(400.0, 150.0, 18.0, "chene", mark="J", doc=doc)
        invitee.Placement = App.Placement(App.Vector(18, 500, 18), DEBOUT)
        doc.recompute()
        api.make_dovetail(copie, invitee)
        doc.recompute()
        form = ouvrir_par_double_clic(invitee)
        if form is None:
            return ["panneau de la pièce non ouvert"]
        saisir(form.thicknessEdit, 30.0)
        w = encadre(form)
        return [
            *ecarts("allonger grisé", w["conflict_extend"].isEnabled(), False),
            *ecarts("raison", "copie" in w["conflictReason_extend"].text(), True),
            *ecarts("intérieur coché", w["conflict_other_side"].isChecked(), True),
        ]


VERIFICATIONS_EPAISSEUR_COTE: tuple[Callable[[], list[str]], ...] = (
    verifier_encadre_et_choix,
    verifier_revenir,
    verifier_copie_non_modifiable,
)
