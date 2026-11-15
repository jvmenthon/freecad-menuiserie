# SPDX-License-Identifier: LGPL-2.1-or-later
"""Côté où ajouter l'épaisseur d'une pièce assemblée (ADR 0060). Logique pure : aucun import
FreeCAD.

Le repère d'une pièce a son origine sur sa face basse : une épaisseur saisie déplace sa face haute
(z = épaisseur). Si un assemblage demande qu'une autre pièce arrive **à fleur** de cette face
(queue d'aronde, par exemple), il est défait. Deux réponses, calculées ici :

- ajouter l'épaisseur de l'autre côté : la pièce recule de l'écart le long de son épaisseur, sa
  face haute ne bouge pas (:func:`other_side_shift`) ;
- prolonger l'autre pièce du même écart, jusqu'à la face haute déplacée
  (:func:`flush_extension`).

:func:`grows_toward` dit si l'autre côté est celui de l'autre pièce (« vers l'intérieur »).
"""

from __future__ import annotations

from dataclasses import dataclass

from freecad.menuiserie.core.geometry import (
    CONTACT_TOLERANCE_MM,
    PlacedBlock,
    Vec3,
    moved_box,
    relative_transform,
)

__all__ = ["Extension", "flush_extension", "grows_toward", "other_side_shift"]

_THICKNESS_AXIS = 2


@dataclass(frozen=True)
class Extension:
    """Prolongement d'une pièce le long de son axe local ``axis`` (0 longueur, 1 largeur,
    2 épaisseur). ``at_end`` : c'est son bout de fin (coordonnée locale maximale) qui est à fleur ;
    sinon c'est son bout de début, et son origine recule de l'écart."""

    axis: int
    at_end: bool

    def origin_shift(self, delta: float) -> Vec3:
        """Décalage de l'origine (repère local de la pièce prolongée) pour un écart ``delta``."""
        if self.at_end:
            return Vec3(0.0, 0.0, 0.0)
        return Vec3(0.0, 0.0, 0.0).with_component(self.axis, -delta)


def _box_in(changed: PlacedBlock, other: PlacedBlock) -> tuple[Vec3, Vec3] | None:
    """Bornes de ``other`` dans le repère de ``changed`` ; ``None`` si elle est oblique."""
    try:
        box = moved_box(other.local_box(), relative_transform(changed, other))
    except ValueError:
        return None
    return box.min, box.max


def flush_extension(
    changed: PlacedBlock, other: PlacedBlock, *, lowered: bool = False
) -> Extension | None:
    """Prolongement de ``other`` qui la garde à fleur de la face haute de ``changed`` (prise à
    son épaisseur d'avant) quand cette face se déplace ; ``lowered`` : de sa face basse (poignée
    de début, ADR 0060). ``None`` si ``other`` n'y arrive pas à fleur (elle s'arrête avant, la
    dépasse, repose dessus) ou si elle est oblique."""
    bounds = _box_in(changed, other)
    if bounds is None:
        return None
    low, high = bounds
    top = changed.dimensions.thickness
    if lowered:
        flush = abs(low.z) <= CONTACT_TOLERANCE_MM and high.z > CONTACT_TOLERANCE_MM
    else:
        flush = abs(high.z - top) <= CONTACT_TOLERANCE_MM and low.z < top - CONTACT_TOLERANCE_MM
    if not flush:
        return None
    rotation = relative_transform(changed, other).rotation
    axis = max(range(3), key=lambda column: abs(rotation[_THICKNESS_AXIS][column]))
    outward = rotation[_THICKNESS_AXIS][axis] > 0  # l'axe de other va vers la face haute
    return Extension(axis, outward != lowered)


def grows_toward(changed: PlacedBlock, other: PlacedBlock) -> bool:
    """Vrai si ajouter l'épaisseur du côté de la face basse de ``changed`` va vers ``other`` :
    le centre de ``other`` est sous le milieu de l'épaisseur de ``changed``. Faux pour une pièce
    oblique."""
    bounds = _box_in(changed, other)
    if bounds is None:
        return False
    low, high = bounds
    return (low.z + high.z) / 2.0 < changed.dimensions.thickness / 2.0


def other_side_shift(changed: PlacedBlock, delta: float) -> Vec3:
    """Translation (repère du document) qui garde la face haute de ``changed`` en place quand son
    épaisseur augmente de ``delta`` mm : l'écart est ajouté du côté de sa face basse."""
    return changed.placement.rotate(Vec3(0.0, 0.0, -delta))
