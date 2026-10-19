# SPDX-License-Identifier: LGPL-2.1-or-later
"""Modèle pur de la pièce de bois : cotes, surcotes, fil et calculs (ADR 0003).

Toutes les longueurs sont en mm et les masses volumiques en kg/m³. Le repère local
de la pièce est : X = longueur, Y = largeur, Z = épaisseur.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, fields
from enum import Enum
from types import MappingProxyType
from typing import Final

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.materials import Material, MaterialKind, to_finite_float

MAX_DIMENSION_MM: Final = 20_000.0
STANDARD_THICKNESS_TOLERANCE_MM: Final = 0.05
_MM3_PER_M3: Final = 1e9
# Marge d'arrondi : une épaisseur exactement à la tolérance reste reconnue.
_ROUNDING_MARGIN_MM: Final = 1e-9

_INVALID_DIMENSION: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Cote invalide : {field} = {value} mm (valeur finie, supérieure à 0 et au plus {max} mm "
    "attendue).",
)
_INVALID_ALLOWANCE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Surcote invalide : {field} = {value} mm (valeur finie, entre 0 et {max} mm attendue).",
)
_FIELD_LABELS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "length": QT_TRANSLATE_NOOP("Menuiserie", "longueur"),
        "width": QT_TRANSLATE_NOOP("Menuiserie", "largeur"),
        "thickness": QT_TRANSLATE_NOOP("Menuiserie", "épaisseur"),
    }
)


class GrainDirection(str, Enum):
    """Sens du fil relatif au repère local ; valeurs stockées dans les documents, figées."""

    LENGTH = "Length"
    WIDTH = "Width"
    NONE = "None"


class InvalidDimensionsError(ValueError):
    """Cote ou surcote hors bornes ; message = gabarit français rempli."""

    def __init__(self, template: str, params: Mapping[str, str]) -> None:
        self.template = template
        self.params: Mapping[str, str] = MappingProxyType(dict(params))
        super().__init__(template.format_map(self.params))


def _short_repr(value: object) -> str:
    """Représentation courte d'une valeur refusée, pour le message d'erreur."""
    try:
        return repr(value)[:20]
    except ValueError:  # entier trop long pour être converti en texte
        return "?"


def _validated(value: object, field: str, *, allow_zero: bool, template: str) -> float:
    """Valeur convertie en flottant si elle est finie et dans ses bornes, sinon erreur."""
    number = to_finite_float(value)
    lower_ok = number is not None and (number >= 0 if allow_zero else number > 0)
    if number is not None and lower_ok and number <= MAX_DIMENSION_MM:
        return number
    shown = f"{number:g}" if number is not None else _short_repr(value)
    params = {"field": _FIELD_LABELS[field], "value": shown, "max": f"{MAX_DIMENSION_MM:g}"}
    raise InvalidDimensionsError(template, params)


@dataclass(frozen=True)
class Dimensions:
    """Cotes finies en mm : finies, strictement positives et au plus ``MAX_DIMENSION_MM``."""

    length: float
    width: float
    thickness: float

    def __post_init__(self) -> None:
        for item in fields(self):
            value = getattr(self, item.name)
            number = _validated(value, item.name, allow_zero=False, template=_INVALID_DIMENSION)
            object.__setattr__(self, item.name, number)


@dataclass(frozen=True)
class Allowances:
    """Surcotes de débit TOTALES (pas par face) en mm : finies, entre 0 et ``MAX_DIMENSION_MM``."""

    length: float = 0.0
    width: float = 0.0
    thickness: float = 0.0

    def __post_init__(self) -> None:
        for item in fields(self):
            value = getattr(self, item.name)
            number = _validated(value, item.name, allow_zero=True, template=_INVALID_ALLOWANCE)
            object.__setattr__(self, item.name, number)


DEFAULT_SOLID_ALLOWANCES: Final = Allowances(20.0, 5.0, 0.0)
DEFAULT_PANEL_ALLOWANCES: Final = Allowances()


def default_allowances(kind: MaterialKind) -> Allowances:
    """Surcotes par défaut de la famille : massif 20 / 5 / 0 mm, panneaux 0 / 0 / 0 mm."""
    # is_panel est une propriété : la règle Semgrep la prend à tort pour une méthode non appelée.
    return DEFAULT_PANEL_ALLOWANCES if kind.is_panel else DEFAULT_SOLID_ALLOWANCES  # nosemgrep


def rough_dimensions(finished: Dimensions, allowances: Allowances) -> Dimensions:
    """Cotes de débit = cotes finies + surcotes (``InvalidDimensionsError`` si hors bornes)."""
    return Dimensions(
        finished.length + allowances.length,
        finished.width + allowances.width,
        finished.thickness + allowances.thickness,
    )


def volume_m3(dimensions: Dimensions) -> float:
    """Volume en m³ d'un parallélépipède de cotes données en mm."""
    return dimensions.length * dimensions.width * dimensions.thickness / _MM3_PER_M3


def mass_kg(dimensions: Dimensions, density_kg_m3: float) -> float:
    """Masse en kg pour une masse volumique en kg/m³."""
    return volume_m3(dimensions) * density_kg_m3


def is_standard_thickness(
    material: Material, thickness: float, tolerance: float = STANDARD_THICKNESS_TOLERANCE_MM
) -> bool:
    """Vrai si l'épaisseur (mm) est une épaisseur standard du matériau, à la tolérance près."""
    margin = tolerance + _ROUNDING_MARGIN_MM
    return any(abs(standard - thickness) <= margin for standard in material.thicknesses)


def grain_after_material_change(new: Material, current: GrainDirection) -> GrainDirection:
    """Sens du fil après un changement de matériau.

    Matériau sans fil : ``NONE`` ; matériau avec fil alors que le fil valait ``NONE`` :
    ``LENGTH`` ; sinon le fil choisi est conservé.
    """
    if not new.has_grain:
        return GrainDirection.NONE
    if current is GrainDirection.NONE:
        return GrainDirection.LENGTH
    return current


def allowances_after_material_change(
    old_kind: MaterialKind | None, new_kind: MaterialKind, current: Allowances
) -> Allowances:
    """Surcotes après un changement de matériau.

    Elles prennent les valeurs par défaut de la nouvelle famille seulement si elles valent
    encore exactement celles de l'ancienne famille ; sinon, elles ont été choisies par
    l'utilisateur et sont conservées. Si l'ancienne famille est inconnue (``None``), les
    valeurs par défaut de toutes les familles sont considérées comme non modifiées.
    """
    kinds = list(MaterialKind) if old_kind is None else [old_kind]
    untouched = {default_allowances(kind) for kind in kinds}
    return default_allowances(new_kind) if current in untouched else current


@dataclass(frozen=True)
class PartRecord:
    """Pièce de bois vue par la liste de débit (J2), indépendante de son orientation."""

    mark: str
    material_id: str
    material_name: str
    kind: MaterialKind
    finished: Dimensions
    allowances: Allowances
    grain: GrainDirection
    density: float

    @property
    def rough(self) -> Dimensions:
        """Cotes de débit (finies + surcotes)."""
        return rough_dimensions(self.finished, self.allowances)

    def volume_m3(self, rough: bool = False) -> float:
        """Volume fini (ou de débit si ``rough``) en m³."""
        return volume_m3(self.rough if rough else self.finished)

    def mass_kg(self, rough: bool = False) -> float:
        """Masse finie (ou de débit si ``rough``) en kg."""
        return mass_kg(self.rough if rough else self.finished, self.density)
