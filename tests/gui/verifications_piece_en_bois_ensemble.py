# SPDX-License-Identifier: LGPL-2.1-or-later
"""Vérification d'interface de la pièce en bois dans un ensemble (PD-f, critère F2).

Module importé par ``verifier_atelier.py`` (lancé par FreeCAD hors écran) : dans le panneau de
l'ensemble, la case « Cotes fixes » d'une pièce en bois est cochée et grisée, avec une infobulle
qui dit pourquoi ; celle d'une pièce de bois reste libre.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import FreeCAD as App

from freecad.menuiserie import api
from tests.gui.verifications_panneau import avec_document, ecarts
from tests.gui.verifications_panneau_assemblage import widget
from tests.gui.verifications_panneau_ensemble import choisir_membre, lignes, ouvrir


def table(doc: Any) -> tuple[Any, Any, Any]:
    """Plateau (pièce de bois) et pied (pièce en bois) réunis dans l'ensemble « Table »."""
    plateau = api.make_wood_part(600, 400, 30, "chene", mark="Plateau", doc=doc)
    plateau.Placement = App.Placement(App.Vector(0, 0, 720), App.Rotation())
    source = doc.addObject("Part::Box", "SourcePied")
    source.Length, source.Width, source.Height = 45.0, 95.0, 720.0
    doc.recompute()
    pied = api.make_shaped_part(source, mark="Pied")
    ensemble, _ = api.make_furniture([plateau, pied], label="Table")
    doc.clearUndos()
    return ensemble, plateau, pied


def cotes_fixes_dans_le_panneau(doc: Any) -> list[str]:
    ensemble, plateau, pied = table(doc)
    form = ouvrir(ensemble)
    if form is None:
        return ["panneau non ouvert"]
    choisir_membre(form, pied)
    case = widget(form, "lockedCheck")
    problemes = [
        *ecarts("pièce en bois : cochée", case.isChecked(), True),
        *ecarts("pièce en bois : grisée", case.isEnabled(), False),
        *ecarts("infobulle : dessin", "dessin" in case.toolTip(), True),
        *ecarts("infobulle : étire", "ne s'étirent jamais" in case.toolTip(), True),
        *ecarts(
            "colonne Suit",
            any(ligne[0] == "Pied" and "cotes fixes" in ligne[2] for ligne in lignes(form)),
            True,
        ),
    ]
    choisir_membre(form, plateau)
    return [
        *problemes,
        *ecarts("pièce de bois : libre", case.isEnabled(), True),
        *ecarts("pièce de bois : décochée", case.isChecked(), False),
        *ecarts("pièce de bois : infobulle", "dessin" in case.toolTip(), False),
    ]


def verifier_cotes_fixes_grisees() -> list[str]:
    """F2 : case « Cotes fixes » grisée et expliquée pour une pièce en bois, libre pour une
    pièce de bois."""
    return avec_document("VerifCotesDessinees", cotes_fixes_dans_le_panneau)


VERIFICATIONS_PIECE_EN_BOIS_ENSEMBLE: tuple[Callable[[], list[str]], ...] = (
    verifier_cotes_fixes_grisees,
)
