# SPDX-License-Identifier: LGPL-2.1-or-later
"""Écriture du ``Placement`` d'une brute et de sa pièce usinée, sans recalcul : commune au
glissement, à la rotation et au recalage des boîtes d'ensemble (ADR 0065). Module de bas niveau,
pour que ``part_drag`` puisse importer ``furniture_reframe`` sans cycle. Aucun import de
``FreeCADGui``."""

from __future__ import annotations

import FreeCAD as App

from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.furniture import writing
from freecad.menuiserie.features.joints.base import is_joint
from freecad.menuiserie.features.machined_part import is_machined_part, machined_part_of
from freecad.menuiserie.features.shaped_part import is_timber

__all__ = ["carried_along", "place", "write_placement"]


def write_placement(raw: DocumentObject, placement: App.Placement) -> None:
    """Écrit ``placement`` dans la brute ``raw``, puis dans sa pièce usinée (affichage sans
    recalcul)."""
    with writing(raw):
        if raw.Placement != placement:
            raw.Placement = placement
    machined = machined_part_of(raw)
    if machined is not None and machined.Placement != placement:
        machined.Placement = placement


def carried_along(obj: DocumentObject) -> bool:
    """Vrai si la position de ``obj`` suit celle d'un autre objet (pièce usinée et sa brute,
    assemblage, repère d'un conteneur) : on ne la décale pas pour elle-même."""
    return obj.TypeId == "App::Origin" or is_machined_part(obj) or is_joint(obj)


def place(obj: DocumentObject, placement: App.Placement) -> None:
    """Écrit ``placement`` dans ``obj`` : brute avec sa pièce usinée (:func:`write_placement`),
    tout autre objet directement (objet de l'utilisateur, Std Part)."""
    if is_timber(obj):
        write_placement(obj, placement)
    elif obj.Placement != placement:
        obj.Placement = placement
