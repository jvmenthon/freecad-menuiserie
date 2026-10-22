# SPDX-License-Identifier: LGPL-2.1-or-later
"""Objets valeur de la liste de débit, validés à la construction (J2b, critères C1 à C8).

Module privé : la façade ``core.cutlist`` ré-exporte l'API publique. Longueurs en mm, volumes en
m³, surfaces en m², masses en kg ; repère local de la pièce : X = longueur, Y = largeur,
Z = épaisseur.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Final

from freecad.menuiserie.core._validation import (
    MAX_DIMENSION_MM,
    MIN_DIMENSION_MM,
    bounded_float,
    decimal_text,
    to_finite_float,
)
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP, TemplatedError
from freecad.menuiserie.core.materials import MaterialKind
from freecad.menuiserie.core.part_model import (
    Allowances,
    Dimensions,
    GrainDirection,
    InvalidDimensionsError,
    PartRecord,
    mass_kg,
    rough_dimensions,
    volume_m3,
)
from freecad.menuiserie.core.text import quoted_value

NO_MARK_DISPLAY: Final = "—"
_MM2_PER_M2: Final = 1e6
NO_ADDITIONS: Final = Allowances()

_BAD_COUNT: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Entrée de débit invalide : {field} = {value} (entier supérieur à 0 attendu)."
)
_BAD_TYPE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Entrée de débit invalide : {field} = {value} (type de valeur inattendu)."
)
_BAD_LENGTH: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Fourniture invalide : {field} = {value} mm (valeur finie, entre {min} et {max} mm attendue).",
)
_BAD_ROUGH: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Entrée de débit invalide : cotes finies, ajouts et surcotes dépassent {max} mm.",
)
_FIELDS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "record": QT_TRANSLATE_NOOP("Menuiserie", "pièce"),
        "quantity": QT_TRANSLATE_NOOP("Menuiserie", "quantité"),
        "additions": QT_TRANSLATE_NOOP("Menuiserie", "ajouts"),
        "diameter": QT_TRANSLATE_NOOP("Menuiserie", "diamètre"),
        "length": QT_TRANSLATE_NOOP("Menuiserie", "longueur"),
        "kind": QT_TRANSLATE_NOOP("Menuiserie", "nature"),
    }
)


class InvalidCutEntryError(TemplatedError):
    """Entrée de débit ou fourniture invalide ; message = gabarit français rempli."""


def _refuse(template: str, field: str, value: object, **extra: str) -> InvalidCutEntryError:
    params = {"field": _FIELDS[field], "value": quoted_value(value)}
    return InvalidCutEntryError(template, params | extra)


def _require_count(value: object, field: str) -> int:
    """Entier strictement positif (pas booléen), sinon ``InvalidCutEntryError``."""
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    raise _refuse(_BAD_COUNT, field, value)


def _require_length(value: object, field: str) -> float:
    """Longueur finie entre ``MIN_DIMENSION_MM`` et ``MAX_DIMENSION_MM``."""
    number = bounded_float(value, MIN_DIMENSION_MM, MAX_DIMENSION_MM)
    if number is not None:
        return number
    finite = to_finite_float(value)
    shown = decimal_text(finite) if finite is not None else value
    bounds = {"min": decimal_text(MIN_DIMENSION_MM), "max": decimal_text(MAX_DIMENSION_MM)}
    raise _refuse(_BAD_LENGTH, field, shown, **bounds)


def _require_instance(value: object, expected: type, field: str) -> None:
    if not isinstance(value, expected):
        raise _refuse(_BAD_TYPE, field, value)


@dataclass(frozen=True)
class CutEntry:
    """Une pièce brute vue ``quantity`` fois : ``additions`` (mm, le long de L, l, e) s'ajoute
    aux cotes de débit, jamais aux cotes finies ; ``furniture`` et ``source`` ne servent
    qu'à l'affichage et aux avertissements."""

    record: PartRecord
    quantity: int = 1
    additions: Allowances = NO_ADDITIONS
    furniture: str = ""
    source: str = ""

    def __post_init__(self) -> None:
        _require_instance(self.record, PartRecord, "record")
        _require_instance(self.additions, Allowances, "additions")
        _require_count(self.quantity, "quantity")
        try:
            _ = self.rough
        except InvalidDimensionsError as error:
            params = {"max": decimal_text(MAX_DIMENSION_MM)}
            raise InvalidCutEntryError(_BAD_ROUGH, params) from error

    @property
    def rough(self) -> Dimensions:
        """Cotes de débit : finies + ajouts des assemblages + surcotes."""
        return rough_dimensions(
            self.record.finished, _sum_allowances(self.record.allowances, self.additions)
        )


def _sum_allowances(first: Allowances, second: Allowances) -> Allowances:
    return Allowances(
        first.length + second.length,
        first.width + second.width,
        first.thickness + second.thickness,
    )


class HardwareKind(str, Enum):
    """Famille de fourniture ; ajouts en fin seulement."""

    DOWEL = "Dowel"


@dataclass(frozen=True)
class Hardware:
    """Fourniture : ``quantity`` tourillons de ``diameter`` sur ``length`` (mm)."""

    kind: HardwareKind
    diameter: float
    length: float
    quantity: int

    def __post_init__(self) -> None:
        if not isinstance(self.kind, HardwareKind):
            raise _refuse(_BAD_TYPE, "kind", self.kind)
        object.__setattr__(self, "diameter", _require_length(self.diameter, "diameter"))
        object.__setattr__(self, "length", _require_length(self.length, "length"))
        _require_count(self.quantity, "quantity")


@dataclass(frozen=True)
class CutLine:
    """Un groupe de pièces identiques ; volumes et masses = unitaires fois ``quantity``.
    ``marks`` : repères distincts non vides des pièces du groupe, en ordre naturel (C1')."""

    marks: tuple[str, ...]
    quantity: int
    material_id: str
    material_name: str
    kind: MaterialKind
    finished: Dimensions
    rough: Dimensions
    grain: GrainDirection
    density: float
    additions: Allowances
    allowances: Allowances
    furniture: tuple[str, ...] = ()

    @property
    def display_mark(self) -> str:
        """Repères affichés (« M1, M3 »), ou « — » pour un groupe sans repère."""
        return ", ".join(self.marks) or NO_MARK_DISPLAY

    def volume_m3(self, rough: bool = False) -> float:
        """Volume du groupe en m³, en cotes finies ou (``rough``) de débit."""
        return volume_m3(self.rough if rough else self.finished) * self.quantity

    def mass_kg(self, rough: bool = False) -> float:
        """Masse du groupe en kg, en cotes finies ou (``rough``) de débit."""
        return mass_kg(self.rough if rough else self.finished, self.density) * self.quantity

    def area_m2(self) -> float:
        """Surface du groupe en m² : longueur par largeur de débit, fois la quantité."""
        return self.rough.length * self.rough.width / _MM2_PER_M2 * self.quantity


@dataclass(frozen=True)
class MaterialTotal:
    """Totaux d'un matériau : volume de débit (m³), masse de débit (kg), surface (panneaux)."""

    material_id: str
    material_name: str
    kind: MaterialKind
    quantity: int
    volume_m3: float
    mass_kg: float
    area_m2: float | None  # ``None`` hors panneau


class CutNoticeKind(Enum):
    """Nature d'un avertissement de la liste de débit."""

    REPEATED_MARK = "RepeatedMark"
    MISSING_MARK = "MissingMark"

    @property
    def template(self) -> str:
        """Gabarit français marqué pour la traduction."""
        return _NOTICE_TEMPLATES[self]


_NOTICE_TEMPLATES: Final[Mapping[CutNoticeKind, str]] = MappingProxyType(
    {
        CutNoticeKind.REPEATED_MARK: QT_TRANSLATE_NOOP(
            "Menuiserie", "Repère {mark} utilisé pour des pièces différentes."
        ),
        CutNoticeKind.MISSING_MARK: QT_TRANSLATE_NOOP(
            "Menuiserie", "{count} pièce(s) sans repère, regroupées par cotes."
        ),
    }
)
