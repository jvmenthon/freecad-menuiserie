# SPDX-License-Identifier: LGPL-2.1-or-later
"""Écriture du ``Placement`` d'une brute et de sa pièce usinée, sans recalcul : commune au
glissement, à la rotation et au recalage des boîtes d'ensemble (ADR 0065). Module de bas niveau,
pour que ``part_drag`` puisse importer ``furniture_reframe`` sans cycle. Aucun import de
``FreeCADGui``."""

from __future__ import annotations

import FreeCAD as App

from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.furniture import writing
from freecad.menuiserie.features.machined_part import machined_part_of

__all__ = ["write_placement"]


def write_placement(raw: DocumentObject, placement: App.Placement) -> None:
    """Écrit ``placement`` dans la brute ``raw``, puis dans sa pièce usinée (affichage sans
    recalcul)."""
    with writing(raw):
        if raw.Placement != placement:
            raw.Placement = placement
    machined = machined_part_of(raw)
    if machined is not None and machined.Placement != placement:
        machined.Placement = placement
