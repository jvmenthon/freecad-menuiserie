# SPDX-License-Identifier: LGPL-2.1-or-later
"""Limites d'un glissement à la souris (B4, B5, B6 bis) : axes qu'une formule de l'utilisateur
fige, cotes qu'une poignée peut tirer. Sorties de ``part_drag`` (taille du module), qui les
réexporte. Aucun import de ``FreeCADGui``."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

import FreeCAD as App

from freecad.menuiserie.core.geometry import ANGLE_TOLERANCE
from freecad.menuiserie.core.magnet import THICKNESS_AXIS
from freecad.menuiserie.features.distance import AXES, distances_touching
from freecad.menuiserie.features.freecad_types import DocumentObject, expressions_of
from freecad.menuiserie.features.furniture_bindings import workshop_expressions
from freecad.menuiserie.features.shaped_part import is_shaped_part
from freecad.menuiserie.features.snap_geometry import to_vec3
from freecad.menuiserie.features.thickness_common import SIZE_PROPS
from freecad.menuiserie.features.wood_part_schema import part_kind

__all__ = ["PLACEMENT_BASE", "DragLimits", "can_resize", "drag_limits"]

PLACEMENT_BASE: Final = ("Placement.Base.x", "Placement.Base.y", "Placement.Base.z")
_WHOLE_PLACEMENT: Final = ("Placement", "Placement.Base")


@dataclass(frozen=True)
class DragLimits:
    """Ce qu'un glissement a le droit de faire sur une pièce brute.

    ``fixed_axes`` : axes de la pièce (0 = X, 1 = Y, 2 = Z) dont une formule **de
    l'utilisateur** pilote la position (aucune flèche) ; ``resizable_axes`` : axes dont une
    poignée est permise (l'axe 2, l'épaisseur, seulement pour le massif), vide si la pièce est
    verrouillée ou si ses cotes ne se tirent pas (:func:`can_resize`)."""

    fixed_axes: frozenset[int] = frozenset()
    resizable_axes: frozenset[int] = frozenset()


def can_resize(part: DocumentObject) -> bool:
    """Vrai si des poignées sont permises sur la brute ``part`` : pas si elle est verrouillée
    (``Locked``, ADR 0019, B5), ni si c'est une pièce en bois : ses cotes sont celles du dessin
    (#87)."""
    return not (bool(getattr(part, "Locked", False)) or is_shaped_part(part))


def _solid(part: DocumentObject) -> bool:
    """Vrai si la brute ``part`` est du massif : seule son épaisseur se tire (Q4). Un panneau
    (contreplaqué, MDF, mélaminé) garde l'épaisseur de la bibliothèque."""
    # is_panel est une propriété : la règle Semgrep la prend à tort pour une méthode non appelée.
    # nosemgrep: python.lang.maintainability.is-function-without-parentheses
    return not part_kind(part, None).is_panel


def _user_expressions(part: DocumentObject) -> set[str]:
    return set(expressions_of(part)) - set(workshop_expressions(part))


def _coordinates(axis: int, rotation: App.Rotation) -> set[int]:
    """Coordonnées du ``Placement`` (0 = x…) que déplacer la pièce sur son axe ``axis`` change."""
    unit = [App.Vector(1, 0, 0), App.Vector(0, 1, 0), App.Vector(0, 0, 1)][axis]
    direction = rotation.multVec(unit)
    return {i for i in range(3) if abs(to_vec3(direction).component(i)) > ANGLE_TOLERANCE}


def _fixed_coordinates(user: set[str]) -> set[int]:
    if user & set(_WHOLE_PLACEMENT):
        return {0, 1, 2}
    return {i for i, path in enumerate(PLACEMENT_BASE) if path in user}


def _driven_gap_coordinates(part: DocumentObject) -> set[int]:
    """Axes (0 = X…) des Distances gardées de ``part`` dont ``Value`` porte une expression : le
    suivi n'y touche pas (:func:`follow_distances`), la pièce glissée reviendrait au recalcul."""
    return {
        AXES.index(distance.Axis)
        for distance in distances_touching(part.Document, {part.Name})
        if "Value" in expressions_of(distance) and distance.Axis in AXES
    }


def drag_limits(part: DocumentObject) -> DragLimits:
    """Limites du glissement de la brute ``part`` (B4, B5, B6 bis) d'après ses formules **de
    l'utilisateur**, sur la pièce ou sur la ``Value`` de l'une de ses Distances gardées (les
    liaisons de l'atelier sont mises de côté, donc ne comptent pas)."""
    user = _user_expressions(part)
    coordinates = _fixed_coordinates(user) | _driven_gap_coordinates(part)
    rotation = part.Placement.Rotation
    fixed = frozenset(i for i in range(3) if _coordinates(i, rotation) & coordinates)
    if not can_resize(part):
        return DragLimits(fixed, frozenset())
    sizes = frozenset(i for i, prop in enumerate(SIZE_PROPS) if prop not in user)
    if not _solid(part):
        sizes -= {THICKNESS_AXIS}
    return DragLimits(fixed, sizes - fixed)
