# SPDX-License-Identifier: LGPL-2.1-or-later
"""Cas limites de l'encadré « où ajouter l'épaisseur ? » (ADR 0060) : saisie revenue à
l'épaisseur d'origine, « Annuler » du panneau, autre pièce pilotée par une expression."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from freecad.menuiserie import api
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
from tests.gui.verifications_queue_aronde import planches


def _ouvrir(invitee: Any) -> Any:
    return ouvrir_par_double_clic(invitee)


def verifier_saisie_revenue_a_l_origine() -> list[str]:
    """Épaisseur retapée à 18 après 30 : l'encadré disparaît, tout est à l'état de départ."""
    with cadre("VerifEpaisseurOrigine") as (doc, _pieces):
        hote, invitee = planches(doc)
        api.make_dovetail(hote, invitee)
        doc.recompute()
        form = _ouvrir(invitee)
        if form is None:
            return ["panneau de la pièce non ouvert"]
        saisir(form.thicknessEdit, 30.0)
        saisir(form.thicknessEdit, 18.0)
        return [
            *ecarts("encadré masqué", encadre(form)["thicknessConflict"].isHidden(), True),
            *ecarts("épaisseur", invitee.Thickness.Value, 18.0),
            *ecarts("H", (hote.Length.Value, tuple(hote.Placement.Base)), (400.0, (0.0, 0.0, 0.0))),
            *ecarts("I", tuple(invitee.Placement.Base), (18.0, 0.0, 18.0)),
        ]


def verifier_annuler_rend_tout() -> list[str]:
    """« Annuler » après « allonger » : H et I rendues, aucune entrée d'annulation."""
    with cadre("VerifEpaisseurAnnuler") as (doc, _pieces):
        hote, invitee = planches(doc)
        api.make_dovetail(hote, invitee)
        doc.recompute()
        doc.clearUndos()
        form = _ouvrir(invitee)
        if form is None:
            return ["panneau de la pièce non ouvert"]
        saisir(form.thicknessEdit, 30.0)
        encadre(form)["conflict_extend"].click()
        annuler()
        doc.recompute()
        return [
            *ecarts("H", (hote.Length.Value, tuple(hote.Placement.Base)), (400.0, (0.0, 0.0, 0.0))),
            *ecarts(
                "I",
                (invitee.Thickness.Value, tuple(invitee.Placement.Base)),
                (18.0, (18.0, 0.0, 18.0)),
            ),
            *ecarts("entrées", doc.UndoNames, []),
        ]


def verifier_saisies_successives_sans_cumul() -> list[str]:
    """30 puis 24 puis « allonger » : H de 406 mm, pas de 418."""
    with cadre("VerifEpaisseurSuccessives") as (doc, _pieces):
        hote, invitee = planches(doc)
        api.make_dovetail(hote, invitee)
        doc.recompute()
        form = _ouvrir(invitee)
        if form is None:
            return ["panneau de la pièce non ouvert"]
        saisir(form.thicknessEdit, 30.0)
        encadre(form)["conflict_extend"].click()
        saisir(form.thicknessEdit, 24.0)
        encadre(form)["conflict_extend"].click()
        problemes = ecarts("H", hote.Length.Value, 406.0)
        problemes += ecarts("champ", valeur(form.thicknessEdit), 24.0)
        valider()
        return problemes


def verifier_autre_piece_pilotee() -> list[str]:
    """Longueur de H pilotée par une expression : « allonger » grisé, raison affichée."""
    with cadre("VerifEpaisseurExpression") as (doc, _pieces):
        hote, invitee = planches(doc)
        api.make_dovetail(hote, invitee)
        hote.setExpression("Length", "400 mm")
        doc.recompute()
        form = _ouvrir(invitee)
        if form is None:
            return ["panneau de la pièce non ouvert"]
        saisir(form.thicknessEdit, 30.0)
        w = encadre(form)
        return [
            *ecarts("allonger grisé", w["conflict_extend"].isEnabled(), False),
            *ecarts("raison", "expression" in w["conflictReason_extend"].text(), True),
            *ecarts("intérieur coché", w["conflict_other_side"].isChecked(), True),
        ]


VERIFICATIONS_EPAISSEUR_COTE_LIMITES: tuple[Callable[[], list[str]], ...] = (
    verifier_saisie_revenue_a_l_origine,
    verifier_annuler_rend_tout,
    verifier_saisies_successives_sans_cumul,
    verifier_autre_piece_pilotee,
)
