# SPDX-License-Identifier: LGPL-2.1-or-later
"""Schéma de la pièce de bois : propriétés, énumérations et valeurs par défaut.

Spécifications des propriétés (type, groupe, mode d'édition, infobulle), valeurs stockées des
énumérations, valeurs par défaut déduites du matériau, ajout des propriétés manquantes et modes
d'édition. Les noms et valeurs écrits dans les documents relèvent du contrat de persistance
(ADR 0003).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Final

import FreeCAD as App

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.materials import Material, MaterialKind, MaterialLibrary
from freecad.menuiserie.core.part_model import Dimensions, GrainDirection, default_allowances
from freecad.menuiserie.features.library import display_language

DocumentObject = Any  # objets FreeCAD, sans annotations de type

DENSITY_UNIT: Final = "kg/m^3"
CATEGORY_BY_KIND: Final[Mapping[MaterialKind, str]] = MappingProxyType(
    {
        MaterialKind.SOLID: "Solid",
        MaterialKind.PLYWOOD: "Plywood",
        MaterialKind.MDF: "MDF",
        MaterialKind.MELAMINE: "Melamine",
    }
)
# Valeurs des énumérations, stockées dans les documents : ordre figé, ajouts en fin seulement.
CATEGORIES: Final = tuple(CATEGORY_BY_KIND.values())
GRAIN_DIRECTIONS: Final = tuple(grain.value for grain in GrainDirection)
KIND_BY_CATEGORY: Final = {category: kind for kind, category in CATEGORY_BY_KIND.items()}

_EDITABLE: Final = 0
_READ_ONLY: Final = 1
_HIDDEN: Final = 2
DEFAULT_DIMENSIONS: Final = Dimensions(800.0, 200.0, 22.0)
# Version du modèle de données (propriété ``Version``), cf. :meth:`WoodPart._migrate`.
MODEL_VERSION: Final = 1


@dataclass(frozen=True)
class _PropertySpec:
    """Propriété de la pièce : type FreeCAD, groupe, mode d'édition et infobulle."""

    name: str
    type_id: str
    group: str
    mode: int
    tooltip: str


_PROPERTIES: Final = (
    _PropertySpec(
        "Length",
        "App::PropertyLength",
        "Dimensions",
        _EDITABLE,
        QT_TRANSLATE_NOOP(
            "App::Property", "Longueur finie de la pièce, mesurée selon l'axe X local."
        ),
    ),
    _PropertySpec(
        "Width",
        "App::PropertyLength",
        "Dimensions",
        _EDITABLE,
        QT_TRANSLATE_NOOP(
            "App::Property", "Largeur finie de la pièce, mesurée selon l'axe Y local."
        ),
    ),
    _PropertySpec(
        "Thickness",
        "App::PropertyLength",
        "Dimensions",
        _EDITABLE,
        QT_TRANSLATE_NOOP(
            "App::Property", "Épaisseur finie de la pièce, mesurée selon l'axe Z local."
        ),
    ),
    _PropertySpec(
        "Material",
        "App::PropertyEnumeration",
        "Matériau",
        _EDITABLE,
        QT_TRANSLATE_NOOP(
            "App::Property", "Essence ou panneau, choisi dans la bibliothèque de matériaux."
        ),
    ),
    _PropertySpec(
        "MaterialId",
        "App::PropertyString",
        "Matériau",
        _READ_ONLY,
        QT_TRANSLATE_NOOP(
            "App::Property",
            "Identifiant stable du matériau dans la bibliothèque. C'est lui qui est enregistré "
            "et utilisé par les calculs.",
        ),
    ),
    _PropertySpec(
        "Category",
        "App::PropertyEnumeration",
        "Matériau",
        _READ_ONLY,
        QT_TRANSLATE_NOOP(
            "App::Property",
            "Type de matériau, déduit du matériau choisi : massif ou panneau (contreplaqué, "
            "MDF, mélaminé).",
        ),
    ),
    _PropertySpec(
        "Density",
        "App::PropertyDensity",
        "Matériau",
        _READ_ONLY,
        QT_TRANSLATE_NOOP(
            "App::Property",
            "Masse volumique recopiée de la bibliothèque au choix du matériau ; sert au calcul "
            "de la masse.",
        ),
    ),
    _PropertySpec(
        "GrainDirection",
        "App::PropertyEnumeration",
        "Matériau",
        _EDITABLE,
        QT_TRANSLATE_NOOP(
            "App::Property",
            "Sens du fil par rapport aux cotes de la pièce : le long de la longueur, de la "
            "largeur, ou sans fil (MDF, mélaminé uni).",
        ),
    ),
    _PropertySpec(
        "Mark",
        "App::PropertyString",
        "Débit",
        _EDITABLE,
        QT_TRANSLATE_NOOP(
            "App::Property",
            "Repère de la pièce sur les plans et dans la liste de débit (ex. « M1 »). Des "
            "pièces identiques peuvent partager le même repère.",
        ),
    ),
    _PropertySpec(
        "LengthAllowance",
        "App::PropertyLength",
        "Débit",
        _EDITABLE,
        QT_TRANSLATE_NOOP(
            "App::Property",
            "Surcote totale ajoutée à la longueur finie pour obtenir la longueur de débit.",
        ),
    ),
    _PropertySpec(
        "WidthAllowance",
        "App::PropertyLength",
        "Débit",
        _EDITABLE,
        QT_TRANSLATE_NOOP(
            "App::Property",
            "Surcote totale ajoutée à la largeur finie pour obtenir la largeur de débit.",
        ),
    ),
    _PropertySpec(
        "ThicknessAllowance",
        "App::PropertyLength",
        "Débit",
        _EDITABLE,
        QT_TRANSLATE_NOOP(
            "App::Property",
            "Surcote totale ajoutée à l'épaisseur finie pour obtenir l'épaisseur de débit.",
        ),
    ),
    _PropertySpec(
        "Version",
        "App::PropertyInteger",
        "Base",
        _HIDDEN,
        QT_TRANSLATE_NOOP(
            "App::Property",
            "Version du modèle de données de la pièce, utilisée pour migrer les anciens fichiers.",
        ),
    ),
)
TYPE_BY_NAME: Final = MappingProxyType({spec.name: spec.type_id for spec in _PROPERTIES})


def density_quantity(value_kg_m3: float) -> Any:
    """Masse volumique en unités FreeCAD (``Quantity``), depuis des kg/m³."""
    return App.Units.Quantity(f"{value_kg_m3} {DENSITY_UNIT}")


def part_kind(obj: DocumentObject, material: Material | None) -> MaterialKind:
    """Famille de la pièce : sa catégorie, sinon celle de ``material``, sinon le massif."""
    if "Category" in obj.PropertiesList:
        return KIND_BY_CATEGORY[obj.Category]
    return material.kind if material is not None else MaterialKind.SOLID


def default_grain(kind: MaterialKind, material: Material | None) -> GrainDirection:
    """Fil par défaut d'une pièce de famille ``kind`` : celui de ``material`` s'il est de cette
    famille, sinon celui de la famille."""
    if material is not None and material.kind is kind:
        has_grain = material.has_grain
    else:
        has_grain = kind.has_grain_by_default
    return GrainDirection.LENGTH if has_grain else GrainDirection.NONE


def _default_values(obj: DocumentObject, material: Material | None) -> dict[str, object]:
    """Valeurs par défaut des propriétés : cotes de 800 x 200 x 22 mm, ``material``, puis
    catégorie, fil et surcotes de la famille de la pièce (:func:`part_kind`).

    Sans matériau (bibliothèque vide), ``Material``, ``MaterialId`` et ``Density`` n'ont pas de
    valeur par défaut : une propriété absente garde la valeur vide de son type.
    """
    kind = part_kind(obj, material)
    allowances = default_allowances(kind)
    values: dict[str, object] = {
        "Length": DEFAULT_DIMENSIONS.length,
        "Width": DEFAULT_DIMENSIONS.width,
        "Thickness": DEFAULT_DIMENSIONS.thickness,
        "Category": CATEGORY_BY_KIND[kind],
        "GrainDirection": default_grain(kind, material).value,
        "Mark": "",
        "LengthAllowance": allowances.length,
        "WidthAllowance": allowances.width,
        "ThicknessAllowance": allowances.thickness,
        "Version": MODEL_VERSION,
    }
    if material is not None:
        values["Material"] = material.name(display_language())
        values["MaterialId"] = material.id
        values["Density"] = density_quantity(material.density)
    return values


def add_missing_properties(
    obj: DocumentObject, library: MaterialLibrary, material: Material | None
) -> None:
    """Ajoute les propriétés absentes de ``obj``, à leur valeur par défaut (cf.
    :func:`_default_values`)."""
    defaults = _default_values(obj, material)
    enumerations = {
        "Material": material_choices(library),
        "Category": list(CATEGORIES),
        "GrainDirection": list(GRAIN_DIRECTIONS),
    }
    for spec in _PROPERTIES:
        if spec.name in obj.PropertiesList:
            continue
        obj.addProperty(spec.type_id, spec.name, spec.group, spec.tooltip)
        if spec.name in enumerations:
            setattr(obj, spec.name, enumerations[spec.name])
        if spec.name in defaults:
            setattr(obj, spec.name, defaults[spec.name])


def apply_editor_modes(obj: DocumentObject) -> None:
    for spec in _PROPERTIES:
        obj.setEditorMode(spec.name, spec.mode)


def material_choices(library: MaterialLibrary, current: str | None = None) -> list[str]:
    """Libellés de la bibliothèque, plus ``current`` s'il n'en fait pas partie."""
    lang = display_language()
    labels = [material.name(lang) for material in library]
    if current is not None and current not in labels:
        labels.append(current)
    return labels


def select_label(obj: DocumentObject, choices: list[str], label: str) -> None:
    """Liste et valeur de ``Material``, écrites seulement si elles changent."""
    if obj.getEnumerationsOfProperty("Material") != choices:
        obj.Material = choices
    if obj.Material != label:
        obj.Material = label
