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
from freecad.menuiserie.core.materials import MaterialKind, normalized_rough_thicknesses
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
from freecad.menuiserie.core.shaped import ShapeSignature
from freecad.menuiserie.core.text import quoted_value

NO_MARK_DISPLAY: Final = "—"
_MM2_PER_M2: Final = 1e6
NO_ADDITIONS: Final = Allowances()
MIN_PLANING_MM: Final = 3.0  # marge de rabotage minimale d'une pièce massive (ADR 0015)
_EPSILON_MM: Final = 1e-6

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
_BAD_ROUGH_THICKNESSES: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Entrée de débit invalide : {field} = {value} (liste de nombres entre {min} et {max} mm "
    "attendue).",
)
_FIELDS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "record": QT_TRANSLATE_NOOP("Menuiserie", "pièce"),
        "quantity": QT_TRANSLATE_NOOP("Menuiserie", "quantité"),
        "additions": QT_TRANSLATE_NOOP("Menuiserie", "ajouts"),
        "diameter": QT_TRANSLATE_NOOP("Menuiserie", "diamètre"),
        "length": QT_TRANSLATE_NOOP("Menuiserie", "longueur"),
        "kind": QT_TRANSLATE_NOOP("Menuiserie", "nature"),
        "rough_thicknesses": QT_TRANSLATE_NOOP("Menuiserie", "épaisseurs de brut"),
        "shape": QT_TRANSLATE_NOOP("Menuiserie", "empreinte de forme"),
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
    qu'à l'affichage et aux avertissements. ``shape`` : empreinte de forme d'une pièce en bois
    (PD-c), ``None`` pour une pièce de bois ; elle sépare les deux familles au regroupement."""

    record: PartRecord
    quantity: int = 1
    additions: Allowances = NO_ADDITIONS
    furniture: str = ""
    source: str = ""
    rough_thicknesses: tuple[float, ...] = ()
    shape: ShapeSignature | None = None

    def __post_init__(self) -> None:
        _require_instance(self.record, PartRecord, "record")
        if self.shape is not None:
            _require_instance(self.shape, ShapeSignature, "shape")
        _require_instance(self.additions, Allowances, "additions")
        _require_count(self.quantity, "quantity")
        self._normalize_rough_thicknesses()
        try:
            _ = self.rough
        except InvalidDimensionsError as error:
            params = {"max": decimal_text(MAX_DIMENSION_MM)}
            raise InvalidCutEntryError(_BAD_ROUGH, params) from error

    def _normalize_rough_thicknesses(self) -> None:
        """Épaisseurs de brut du matériau (ADR 0015) : vides, ou liste valide triée."""
        value = self.rough_thicknesses
        rough: tuple[float, ...] | None = ()
        if not (isinstance(value, (list, tuple)) and not value):
            rough = normalized_rough_thicknesses(value)
        if rough is None:
            bounds = {"min": decimal_text(MIN_DIMENSION_MM), "max": decimal_text(MAX_DIMENSION_MM)}
            raise _refuse(_BAD_ROUGH_THICKNESSES, "rough_thicknesses", value, **bounds)
        object.__setattr__(self, "rough_thicknesses", rough)

    def _requested_thickness(self) -> float:
        """Épaisseur demandée d'une pièce massive : finie + max(surcote + ajouts, rabotage)."""
        margin = self.record.allowances.thickness + self.additions.thickness
        return self.record.finished.thickness + max(margin, MIN_PLANING_MM)

    @property
    def standard_thickness(self) -> float | None:
        """Plus petite épaisseur de brut qui couvre l'épaisseur demandée ; ``None`` sans
        épaisseurs de brut, ou au-delà de la plus grande (:attr:`over_standard`)."""
        if not self.rough_thicknesses:
            return None
        wanted = self._requested_thickness() - _EPSILON_MM
        return next((value for value in self.rough_thicknesses if value >= wanted), None)

    @property
    def over_standard(self) -> bool:
        """Vrai si l'épaisseur demandée dépasse la plus grande épaisseur de brut."""
        return bool(self.rough_thicknesses) and self.standard_thickness is None

    @property
    def rough(self) -> Dimensions:
        """Cotes de débit : finies + ajouts des assemblages + surcotes ; l'épaisseur est celle
        du brut standard du matériau s'il en a (ADR 0015)."""
        rough = rough_dimensions(
            self.record.finished, _sum_allowances(self.record.allowances, self.additions)
        )
        if not self.rough_thicknesses:
            return rough
        thickness = self.standard_thickness
        return Dimensions(
            rough.length,
            rough.width,
            thickness if thickness is not None else self._requested_thickness(),
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
    ``marks`` : repères distincts non vides des pièces du groupe, en ordre naturel (C1').
    ``source`` : nom interne de la première pièce du groupe (clé de la miniature, vide si
    inconnu). ``shape`` : empreinte de forme d'un groupe de pièces en bois, ``None`` pour du
    bois (la ligne porte alors la mention « forme »)."""

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
    source: str = ""
    over_standard: bool = False
    shape: ShapeSignature | None = None

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
    """Totaux d'un matériau dans une épaisseur de débit : volume de débit (m³), masse de débit
    (kg), surface de débit (m², massif comme panneaux : on achète au m² par épaisseur)."""

    material_id: str
    material_name: str
    kind: MaterialKind
    thickness: float  # épaisseur de débit (mm)
    quantity: int
    volume_m3: float
    mass_kg: float
    area_m2: float


class CutNoticeKind(Enum):
    """Nature d'un avertissement de la liste de débit."""

    REPEATED_MARK = "RepeatedMark"
    MISSING_MARK = "MissingMark"
    ROUGH_THICKNESS_OVER_STANDARD = "RoughThicknessOverStandard"

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
        CutNoticeKind.ROUGH_THICKNESS_OVER_STANDARD: QT_TRANSLATE_NOOP(
            "Menuiserie",
            "Épaisseur de débit de {thickness} mm au-delà des épaisseurs de brut du {material} : "
            "à commander ou à contrecoller.",
        ),
    }
)
