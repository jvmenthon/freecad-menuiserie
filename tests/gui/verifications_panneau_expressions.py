# SPDX-License-Identifier: LGPL-2.1-or-later
"""Vérifications d'interface du panneau de la « Pièce de bois » : expressions (C6) et
traductions (C8) de ``docs/specs/J1-piece-de-bois.md``. Suite de ``verifications_panneau.py``,
importée par ``verifier_atelier.py``."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from tests.gui.verifications_panneau import (
    avec_document,
    creer_par_la_commande,
    donnees,
    ecarts,
    formulaire,
    ouvrir_par_double_clic,
    piece_validee,
    saisir,
    valeur,
    valider,
)

# --- C6 : expressions --------------------------------------------------------------------


def verifier_expressions() -> list[str]:
    """C6 : une cote pilotée par une expression est affichée comme telle et conservée.

    L'icône d'expression et la lecture seule du champ sont vérifiées à la main (recette) : hors
    écran, le volet des tâches peut être replié et le champ n'est pas affiché."""

    def verification(doc: Any) -> list[str]:
        obj = piece_validee(doc)
        obj.setExpression("Length", "Width * 4")
        obj.setExpression("Thickness", "Width / 10")
        doc.recompute()
        form = ouvrir_par_double_clic(obj)
        problemes = [
            *ecarts("valeur de l'expression", valeur(form.lengthEdit), 800.0),
            *ecarts("expression affichée", form.lengthEdit.property("expression"), "Width * 4"),
            *ecarts("champ sans expression", form.widthEdit.property("expression"), ""),
            *ecarts("menu des épaisseurs inactif", form.standardThicknessButton.isEnabled(), False),
        ]
        saisir(form.widthEdit, 250.0)
        valider()
        expressions = dict(obj.ExpressionEngine)
        return [
            *problemes,
            *ecarts(
                "expressions conservées",
                expressions,
                {"Length": "Width * 4", "Thickness": "Width / 10"},
            ),
            *ecarts("longueur recalculée", obj.Length.Value, 1000.0),
        ]

    return avec_document("VerifExpressions", verification)


# --- C8 : traductions --------------------------------------------------------------------


def verifier_libelles_traduits() -> list[str]:
    """C8 : les libellés du fil sont traduits, la valeur écrite reste la valeur stable."""

    def verification(doc: Any) -> list[str]:
        creer_par_la_commande(doc)
        form = formulaire()
        textes = [form.grainCombo.itemText(i) for i in range(form.grainCombo.count())]
        return [
            *ecarts("libellés du fil", textes, ["Longueur", "Largeur", "Sans fil"]),
            *ecarts("valeurs du fil", donnees(form.grainCombo), ["Length", "Width", "None"]),
            *ecarts("titre", form.windowTitle(), "Nouvelle pièce de bois"),
        ]

    return avec_document("VerifLibelles", verification)


VERIFICATIONS_PANNEAU_EXPRESSIONS: tuple[Callable[[], list[str]], ...] = (
    verifier_expressions,
    verifier_libelles_traduits,
)
