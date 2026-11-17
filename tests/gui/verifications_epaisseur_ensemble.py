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
from tests.gui.verifications_panneau import annuler, ecarts, ouvrir_par_double_clic, valider


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


VERIFICATIONS_EPAISSEUR_ENSEMBLE: tuple[Callable[[], list[str]], ...] = (
    verifier_epaisseur_d_un_membre_ok,
    verifier_epaisseur_d_un_membre_annuler,
)
