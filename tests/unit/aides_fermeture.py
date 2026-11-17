# SPDX-License-Identifier: LGPL-2.1-or-later
"""Aides des tests de « Fermer le caisson » (ADR 0064) : ancre de référence, lecture du gabarit."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from freecad.menuiserie.core.geometry import PlacedBlock
from freecad.menuiserie.core.part_model import Dimensions
from freecad.menuiserie.core.templates import Layout
from freecad.menuiserie.core.templates.closing import closing_layout, wanted_extents
from freecad.menuiserie.core.templates.closing_params import ClosingParams

ANCHOR = Dimensions(600.0, 400.0, 18.0)  # dessous de référence (critère FC1)
Spans = list[tuple[float, float]]


def params(**changes: Any) -> ClosingParams:
    """Paramètres de référence (ancre 600 x 400 x 18, hauteur 720, valeurs par défaut)."""
    return ClosingParams(ANCHOR, "cp-bouleau", **changes)


def layout(**changes: Any) -> Layout:
    """Gabarit de la fermeture de référence, avec ``changes`` sur les paramètres."""
    return closing_layout(params(**changes))


def spans(result: Layout, key: str) -> Spans:
    """Étendues (X, Y, Z) de la pièce ``key`` dans le repère du caisson."""
    return list(wanted_extents(result, key))


def sizes(piece: PlacedBlock) -> tuple[float, float, float]:
    """Cotes L x l x e d'un bloc."""
    size = piece.dimensions
    return size.length, size.width, size.thickness


def pairs(result: Layout) -> list[tuple[str, str, str]]:
    """(type, hôte, invitée) de chaque assemblage, dans l'ordre du gabarit."""
    return [(joint.kind.name, joint.host, joint.guest) for joint in result.joints]


def without(base: ClosingParams, *elements: object) -> ClosingParams:
    """``base`` privé de ces éléments."""
    return replace(base, elements=base.elements - frozenset(elements))
