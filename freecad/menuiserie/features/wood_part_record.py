# SPDX-License-Identifier: LGPL-2.1-or-later
"""Lecture d'une pièce de bois par la liste de débit (J2) et pièces illisibles (issue #13).

Un document créé par une version plus récente peut porter une catégorie ou un sens du fil
inconnus, et son matériau n'est pas modifiable ici : les accès de :mod:`.wood_part` lèvent
alors :class:`UnsupportedPartError`, au message traduit, au lieu d'une ``KeyError``.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final, TypeVar

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.part_model import (
    Allowances,
    Dimensions,
    GrainDirection,
    PartRecord,
)
from freecad.menuiserie.core.text import quoted_value
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.features.wood_part_schema import KIND_BY_CATEGORY, density_kg_m3

__all__ = [
    "GRAIN_BY_VALUE",
    "UnsupportedPartError",
    "allowances_of",
    "dimensions_of",
    "known_value",
    "newer_version_error",
    "record_of",
]

_UNREADABLE_VALUE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Pièce « {label} » : valeur « {value} » inconnue pour {property} (document d'une version "
    "plus récente de l'atelier ?) ; mettez l'atelier à jour.",
)
_NEWER_VERSION_READ_ONLY: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Pièce « {label} » : document créé par une version plus récente de l'atelier, le matériau "
    "n'est pas modifiable ici ; mettez l'atelier à jour.",
)
GRAIN_BY_VALUE: Final[Mapping[str, GrainDirection]] = {g.value: g for g in GrainDirection}
_T = TypeVar("_T")


class UnsupportedPartError(ValueError):
    """Pièce que cette version de l'atelier ne sait pas lire ou modifier (valeur inconnue d'un
    document plus récent, matériau en lecture seule) ; le message est déjà traduit."""


def known_value(obj: DocumentObject, prop: str, known: Mapping[str, _T]) -> _T:
    """Valeur associée à celle de la propriété ``prop`` dans ``known`` ;
    ``UnsupportedPartError`` si la propriété a une valeur inconnue."""
    value = getattr(obj, prop)
    if value not in known:
        params = {"label": quoted_value(obj.Label), "property": prop, "value": quoted_value(value)}
        raise UnsupportedPartError(translated(_UNREADABLE_VALUE, params))
    return known[value]


def newer_version_error(obj: DocumentObject) -> UnsupportedPartError:
    """Erreur d'une modification du matériau d'une pièce d'un document plus récent."""
    return UnsupportedPartError(
        translated(_NEWER_VERSION_READ_ONLY, {"label": quoted_value(obj.Label)})
    )


def dimensions_of(obj: DocumentObject) -> Dimensions:
    """Cotes finies de la pièce en mm (``InvalidDimensionsError`` si l'une est invalide)."""
    return Dimensions(obj.Length.Value, obj.Width.Value, obj.Thickness.Value)


def allowances_of(obj: DocumentObject) -> Allowances:
    """Surcotes de débit de la pièce en mm."""
    return Allowances(
        obj.LengthAllowance.Value, obj.WidthAllowance.Value, obj.ThicknessAllowance.Value
    )


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
