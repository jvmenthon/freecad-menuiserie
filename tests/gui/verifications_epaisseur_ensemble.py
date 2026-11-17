# SPDX-License-Identifier: LGPL-2.1-or-later
"""Épaisseur d'une pièce d'ensemble assemblée dans son panneau (ADR 0060, jv 2026-11-17).

Bureau assemblé par tourillons et regroupé : l'épaisseur de la joue gauche propose les mêmes
choix qu'une pièce seule. « OK » relie l'ensemble d'après le résultat (boîte à l'enveloppe,
liaisons de l'atelier remises) ; « Annuler » rend tout, liaisons comprises. Module importé par
``verifier_atelier.py``.
"""

from __future__ import annotations

from collections.abc import Callable

from freecad.menuiserie.features.furniture_bindings import workshop_expressions
from tests.gui.verifications_ensemble import pieces_du_bureau, regrouper
from tests.gui.verifications_epaisseur_cote import encadre
from tests.gui.verifications_epaisseur_frappe import invalides, taper
from tests.gui.verifications_panneau import (
    annuler,
    ecarts,
    ouvrir_par_double_clic,
    saisir,
    valider,
)
from tests.integration.bureau import Bureau


def verifier_epaisseur_d_un_membre_ok() -> list[str]:
    """Joue gauche à 30 mm, « vers l'intérieur » : la voile et la joue droite sont poussées,
    l'ensemble s'élargit de 8 mm et reste relié après « OK »."""
    with pieces_du_bureau("VerifEpaisseurMembreOk", assemble=True) as bureau:
        regrouper(bureau)
        joue, voile = bureau.parts["JG"], bureau.parts["V"]
        x_voile = voile.Placement.Base.x
        form = ouvrir_par_double_clic(joue)
        if form is None:
            return ["panneau de la pièce non ouvert"]
        taper(form.thicknessEdit, "30")
        boite = encadre(form)
        problemes = [*ecarts("encadré affiché", boite["thicknessConflict"].isHidden(), False)]
        boite["conflict_other_side"].click()
        valider()
        doc = bureau.doc
        doc.recompute()
        return [
            *problemes,
            *ecarts("épaisseur", joue.Thickness.Value, 30.0),
            *ecarts("voile poussée", round(voile.Placement.Base.x - x_voile, 6), 8.0),
            *ecarts("largeur de l'ensemble", bureau.furniture.Width.Value, 1208.0),
            *ecarts("voile reliée", bool(workshop_expressions(voile)), True),
            *ecarts("objets en erreur", invalides(doc), []),
        ]


def verifier_epaisseur_d_un_membre_annuler() -> list[str]:
    """Joue gauche à 30 mm puis « Annuler » : cotes, placements et liaisons rendus."""
    with pieces_du_bureau("VerifEpaisseurMembreAnnuler", assemble=True) as bureau:
        regrouper(bureau)
        joue, voile = bureau.parts["JG"], bureau.parts["V"]
        avant = dict(workshop_expressions(voile))
        x_voile = voile.Placement.Base.x
        form = ouvrir_par_double_clic(joue)
        if form is None:
            return ["panneau de la pièce non ouvert"]
        taper(form.thicknessEdit, "30")
        encadre(form)["conflict_other_side"].click()
        annuler()
        return [
            *ecarts("épaisseur", joue.Thickness.Value, 22.0),
            *ecarts("voile en place", voile.Placement.Base.x, x_voile),
            *ecarts("largeur de l'ensemble", bureau.furniture.Width.Value, 1200.0),
            *ecarts("liaisons rendues", dict(workshop_expressions(voile)), avant),
        ]


def _etat(bureau: Bureau) -> dict[str, object]:
    """Cotes, placements et liaisons de l'atelier de chaque pièce, boîte de l'ensemble."""
    pieces = {
        repere: (
            tuple(round(v, 6) for v in piece.Placement.Base),
            round(piece.Length.Value, 6),
            round(piece.Width.Value, 6),
            round(piece.Thickness.Value, 6),
            dict(workshop_expressions(piece)),
        )
        for repere, piece in bureau.parts.items()
    }
    return {**pieces, "ensemble": round(bureau.furniture.Width.Value, 6)}


def verifier_epaisseur_d_un_membre_saisies_successives() -> list[str]:
    """30 puis 25 « vers l'intérieur » : la voile et la joue droite sont poussées de 3 mm (pas de
    cumul) ; « OK » ; une seule annulation rend tout, le rétablissement remet le résultat."""
    with pieces_du_bureau("VerifEpaisseurMembreSaisies", assemble=True) as bureau:
        regrouper(bureau)
        joue, voile = bureau.parts["JG"], bureau.parts["V"]
        depart = _etat(bureau)
        form = ouvrir_par_double_clic(joue)
        if form is None:
            return ["panneau de la pièce non ouvert"]
        taper(form.thicknessEdit, "30")
        encadre(form)["conflict_other_side"].click()
        taper(form.thicknessEdit, "25")  # chaque saisie reprend le premier choix possible
        encadre(form)["conflict_other_side"].click()
        valider()
        doc = bureau.doc
        doc.recompute()
        problemes = [
            *ecarts("épaisseur", joue.Thickness.Value, 25.0),
            *ecarts("voile poussée de 3 mm", round(voile.Placement.Base.x - 22.0, 6), 3.0),
            *ecarts("largeur de l'ensemble", bureau.furniture.Width.Value, 1203.0),
            *ecarts("voile reliée", bool(workshop_expressions(voile)), True),
            *ecarts("objets en erreur", invalides(doc), []),
        ]
        final = _etat(bureau)
        doc.undo()
        problemes += ecarts("une annulation rend tout", _etat(bureau), depart)
        doc.redo()
        return [*problemes, *ecarts("rétablissement", _etat(bureau), final)]


def verifier_epaisseur_d_un_membre_revenir_puis_ok() -> list[str]:
    """30 puis « Revenir à 22 mm » puis « OK » : cotes, placements et liaisons identiques à ceux
    du départ."""
    with pieces_du_bureau("VerifEpaisseurMembreRevenir", assemble=True) as bureau:
        regrouper(bureau)
        depart = _etat(bureau)
        form = ouvrir_par_double_clic(bureau.parts["JG"])
        if form is None:
            return ["panneau de la pièce non ouvert"]
        taper(form.thicknessEdit, "30")
        boite = encadre(form)
        boite["conflict_other_side"].click()
        boite["conflict_revert"].click()
        valider()
        bureau.doc.recompute()
        return [
            *ecarts("état rendu", _etat(bureau), depart),
            *ecarts("objets en erreur", invalides(bureau.doc), []),
        ]


def verifier_epaisseur_d_un_membre_puis_autre_cote() -> list[str]:
    """30 « vers l'intérieur » puis une autre saisie (largeur) : l'ensemble est relié d'après
    l'état écrit (largeur 1208, liaisons remises) ; une nouvelle épaisseur repart de cet état."""
    with pieces_du_bureau("VerifEpaisseurMembreAutreCote", assemble=True) as bureau:
        regrouper(bureau)
        joue, voile = bureau.parts["JG"], bureau.parts["V"]
        form = ouvrir_par_double_clic(joue)
        if form is None:
            return ["panneau de la pièce non ouvert"]
        taper(form.thicknessEdit, "30")
        encadre(form)["conflict_other_side"].click()
        saisir(form.widthEdit, 300)  # autre cote : l'encadré est oublié, l'ensemble relié
        problemes = [
            *ecarts("encadré oublié", encadre(form)["thicknessConflict"].isHidden(), True),
            *ecarts("largeur de l'ensemble", bureau.furniture.Width.Value, 1208.0),
            *ecarts("voile reliée", bool(workshop_expressions(voile)), True),
        ]
        taper(form.thicknessEdit, "34")  # nouvelle suite de saisies, depuis 30 mm
        encadre(form)["conflict_other_side"].click()
        valider()
        bureau.doc.recompute()
        return [
            *problemes,
            *ecarts("épaisseur", joue.Thickness.Value, 34.0),
            *ecarts("largeur de la joue (liée à l'ensemble)", joue.Width.Value, 560.0),
            *ecarts("largeur de l'ensemble", bureau.furniture.Width.Value, 1212.0),
            *ecarts("voile reliée", bool(workshop_expressions(voile)), True),
            *ecarts("objets en erreur", invalides(bureau.doc), []),
        ]


VERIFICATIONS_EPAISSEUR_ENSEMBLE: tuple[Callable[[], list[str]], ...] = (
    verifier_epaisseur_d_un_membre_ok,
    verifier_epaisseur_d_un_membre_annuler,
    verifier_epaisseur_d_un_membre_saisies_successives,
    verifier_epaisseur_d_un_membre_revenir_puis_ok,
    verifier_epaisseur_d_un_membre_puis_autre_cote,
)
