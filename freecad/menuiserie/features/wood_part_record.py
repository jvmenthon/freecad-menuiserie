# SPDX-License-Identifier: LGPL-2.1-or-later
"""Lecture d'une pièce de bois par la liste de débit (J2) et pièces illisibles (issue #13).

Un document créé par une version plus récente peut porter une catégorie ou un sens du fil
inconnus, et son matériau n'est pas modifiable ici : les accès de :mod:`.wood_part` lèvent
alors :class:`UnsupportedPartError`, au message traduit, au lieu d'une ``KeyError``. Cette
erreur et les lectures de valeurs sont définies dans :mod:`.wood_material` (partagées avec la
pièce en bois, ADR 0020) et ré-exportées ici. :func:`dimensions_of` et :func:`record_of` valent
pour les deux sortes de pièces : elles ne lisent que des propriétés de mêmes noms.
"""

from __future__ import annotations

from freecad.menuiserie.core.part_model import Dimensions, PartRecord
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.wood_material import (
    GRAIN_BY_VALUE,
    KIND_BY_CATEGORY,
    UnsupportedPartError,
    allowances_of,
    density_kg_m3,
    known_value,
    newer_version_error,
)

__all__ = [
    "GRAIN_BY_VALUE",
    "UnsupportedPartError",
    "allowances_of",
    "dimensions_of",
    "known_value",
    "newer_version_error",
    "record_of",
]


def dimensions_of(obj: DocumentObject) -> Dimensions:
    """Cotes finies de la pièce en mm (``InvalidDimensionsError`` si l'une est invalide)."""
    return Dimensions(obj.Length.Value, obj.Width.Value, obj.Thickness.Value)


def record_of(obj: DocumentObject) -> PartRecord:
    """Pièce vue par la liste de débit (J2), d'après ses seules propriétés.

    ``UnsupportedPartError`` (message traduit) si la catégorie ou le sens du fil est une valeur
    inconnue, par exemple d'un document créé par une version plus récente de l'atelier."""
    return PartRecord(
        mark=obj.Mark,
        material_id=obj.MaterialId,
        material_name=obj.Material,
        kind=known_value(obj, "Category", KIND_BY_CATEGORY),
        finished=dimensions_of(obj),
        allowances=allowances_of(obj),
        grain=known_value(obj, "GrainDirection", GRAIN_BY_VALUE),
        density=density_kg_m3(obj),
    )
