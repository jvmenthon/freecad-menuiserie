# SPDX-License-Identifier: LGPL-2.1-or-later
"""Vérifications d'interface : assemblage entre pièces de conteneurs différents (issue #209,
ADR 0054).

Cas de jv : une planche libre (à la racine du document) assemblée au côté d'un caisson rangé dans
son Std Part. Les commandes sont lancées sur la sélection, comme à la souris ; le déplacement du
Std Part passe par l'écriture de son ``Placement``, que l'observateur de l'atelier (actif) suit.
Module importé par ``verifier_atelier.py``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import FreeCAD as App

from tests.gui.verifications_assemblages import (
    TENON_MORTAISE,
    assembler,
    cadre,
    usinee_de,
)
from tests.gui.verifications_panneau import ecarts
from tests.gui.verifications_souris import preparer

TOURILLONS = "Menuiserie_Dowels"
DECALAGE = 100.0  # mm : Std Part du « caisson » décalé en x, place globale de T1 inchangée
TRAVERSE_A_TENON = 280 * 60 * 22 + 40 * 40 * 7  # T1 avec un seul tenon (côté M1)


def _dans_un_caisson(doc: Any, piece: Any) -> Any:
    """Range ``piece`` dans un Std Part décalé de ``DECALAGE`` sans changer sa place globale."""
    caisson = doc.addObject("App::Part", "Caisson")
    caisson.Placement = App.Placement(App.Vector(DECALAGE, 0, 0), App.Rotation())
    globale = piece.Placement
    caisson.addObject(piece)
    piece.Placement = caisson.Placement.inverse() * globale
    doc.recompute()
    return caisson


def _etat(doc: Any, mot: str) -> list[str]:
    return [obj.Name for obj in doc.Objects if mot in obj.State]


def verifier_tenon_entre_piece_libre_et_caisson() -> list[str]:
    with cadre("Conteneurs1") as (doc, pieces):
        preparer(doc)
        _dans_un_caisson(doc, pieces["T1"])
        joint = assembler(doc, pieces["M1"], pieces["T1"], commande=TENON_MORTAISE)
        doc.recompute()
        problemes = ecarts("assemblage créé", joint is not None, True)
        if joint is None:
            return problemes
        problemes += ecarts("conteneur de l'assemblage", joint.getParentGeoFeatureGroup(), None)
        volume = round(float(usinee_de(pieces["T1"]).Shape.Volume), 3)
        problemes += ecarts("tenon usiné dans T1", volume, float(TRAVERSE_A_TENON))
        problemes += ecarts("rien d'invalide", _etat(doc, "Invalid"), [])
        problemes += ecarts("rien de modifié après recalcul", _etat(doc, "Touched"), [])
        return problemes


def verifier_tourillons_entre_piece_libre_et_caisson() -> list[str]:
    """Cas de jv (2026-11-13) : tourillons refusés, puis cycle « The graph must be a DAG »."""
    with cadre("Conteneurs2") as (doc, pieces):
        preparer(doc)
        _dans_un_caisson(doc, pieces["T1"])
        joint = assembler(doc, pieces["M1"], pieces["T1"], commande=TOURILLONS)
        doc.recompute()
        problemes = ecarts("tourillons créés", joint is not None, True)
        problemes += ecarts("rien d'invalide", _etat(doc, "Invalid"), [])
        problemes += ecarts("rien de modifié après recalcul", _etat(doc, "Touched"), [])
        usinee = usinee_de(pieces["T1"])
        problemes += ecarts(
            "pièce usinée de T1 dans le caisson",
            usinee.getParentGeoFeatureGroup().Name,
            "Caisson",
        )
        return problemes


def verifier_assemblage_suit_le_caisson_deplace() -> list[str]:
    """Std Part du caisson déplacé (atelier actif) : l'assemblage est recalculé. Les pièces ne se
    touchent plus, il devient donc invalide."""
    with cadre("Conteneurs3") as (doc, pieces):
        preparer(doc)
        caisson = _dans_un_caisson(doc, pieces["T1"])
        joint = assembler(doc, pieces["M1"], pieces["T1"], commande=TENON_MORTAISE)
        doc.recompute()
        if joint is None:
            return ["assemblage non créé"]
        caisson.Placement = App.Placement(App.Vector(DECALAGE, 0, 500), App.Rotation())
        problemes = ecarts("assemblage touché par le déplacement", "Touched" in joint.State, True)
        doc.recompute()
        problemes += ecarts(
            "assemblage recalculé (plus de contact)", "Invalid" in joint.State, True
        )
        caisson.Placement = App.Placement(App.Vector(DECALAGE, 0, 0), App.Rotation())
        doc.recompute()
        problemes += ecarts("de nouveau valide une fois revenu", _etat(doc, "Invalid"), [])
        return problemes


VERIFICATIONS_ASSEMBLAGE_CONTENEURS: tuple[Callable[[], list[str]], ...] = (
    verifier_tenon_entre_piece_libre_et_caisson,
    verifier_tourillons_entre_piece_libre_et_caisson,
    verifier_assemblage_suit_le_caisson_deplace,
)
