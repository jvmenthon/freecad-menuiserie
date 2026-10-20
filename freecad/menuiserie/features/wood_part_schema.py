# SPDX-License-Identifier: LGPL-2.1-or-later
"""Schéma de la pièce de bois : propriétés, énumérations et valeurs par défaut.

Spécifications des propriétés (type, groupe, mode d'édition, infobulle), valeurs stockées des
énumérations, valeurs par défaut déduites du matériau, ajout des propriétés manquantes et modes
d'édition. Les noms et valeurs écrits dans les documents relèvent du contrat de persistance
(ADR 0003).
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any, Final

import FreeCAD as App

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.materials import Material, MaterialKind, MaterialLibrary
from freecad.menuiserie.core.part_model import (
    Dimensions,
    GrainDirection,
    default_allowances,
    remembered_grain,
)
from freecad.menuiserie.features import schema
from freecad.menuiserie.features.freecad_types import EDITABLE, HIDDEN, READ_ONLY, DocumentObject
from freecad.menuiserie.features.library import display_language
from freecad.menuiserie.features.schema import PropertySpec

DENSITY_UNIT: Final = "kg/m^3"
# Décimales de la masse volumique relue (kg/m³). FreeCAD la stocke en kg/mm³ : l'aller-retour
# laisse une erreur relative de l'ordre de 1e-16 (709,9999999999999 pour 710), soit moins de
# 1e-12 kg/m³ jusqu'à MAX_DENSITY. Six décimales (1 mg/m³) l'effacent, tout en restant bien
# plus fines que la précision d'une masse volumique de bois (de l'ordre du kg/m³).
DENSITY_DECIMALS: Final = 6
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
# Sens mémorisables (ADR 0005) : mêmes chaînes que ``GrainDirection``, sans ``None``.
PREFERRED_GRAIN_DIRECTIONS: Final = (GrainDirection.LENGTH.value, GrainDirection.WIDTH.value)
KIND_BY_CATEGORY: Final = {category: kind for kind, category in CATEGORY_BY_KIND.items()}

DEFAULT_DIMENSIONS: Final = Dimensions(800.0, 200.0, 22.0)
# Version du modèle de données (propriété ``Version``), cf. :meth:`WoodPart._migrate`.
MODEL_VERSION: Final = 2


PROPERTIES: Final = (
    PropertySpec(
        "Length",
        "App::PropertyLength",
        "Dimensions",
        QT_TRANSLATE_NOOP(
            "App::Property", "Longueur finie de la pièce, mesurée selon l'axe X local."
        ),
    ),
    PropertySpec(
        "Width",
        "App::PropertyLength",
        "Dimensions",
        QT_TRANSLATE_NOOP(
            "App::Property", "Largeur finie de la pièce, mesurée selon l'axe Y local."
        ),
    ),
    PropertySpec(
        "Thickness",
        "App::PropertyLength",
        "Dimensions",
        QT_TRANSLATE_NOOP(
            "App::Property", "Épaisseur finie de la pièce, mesurée selon l'axe Z local."
        ),
    ),
    PropertySpec(
        "Material",
        "App::PropertyEnumeration",
        "Matériau",
        QT_TRANSLATE_NOOP(
            "App::Property", "Essence ou panneau, choisi dans la bibliothèque de matériaux."
        ),
    ),
    PropertySpec(
        "MaterialId",
        "App::PropertyString",
        "Matériau",
        QT_TRANSLATE_NOOP(
            "App::Property",
            "Identifiant stable du matériau dans la bibliothèque. C'est lui qui est enregistré "
            "et utilisé par les calculs.",
        ),
        mode=READ_ONLY,
    ),
    PropertySpec(
        "Category",
        "App::PropertyEnumeration",
        "Matériau",
        QT_TRANSLATE_NOOP(
            "App::Property",
            "Type de matériau, déduit du matériau choisi : massif ou panneau (contreplaqué, "
            "MDF, mélaminé).",
        ),
        mode=READ_ONLY,
    ),
    PropertySpec(
        "Density",
        "App::PropertyDensity",
        "Matériau",
        QT_TRANSLATE_NOOP(
            "App::Property",
            "Masse volumique recopiée de la bibliothèque au choix du matériau ; sert au calcul "
            "de la masse.",
        ),
        mode=READ_ONLY,
    ),
    PropertySpec(
        "GrainDirection",
        "App::PropertyEnumeration",
        "Matériau",
        QT_TRANSLATE_NOOP(
            "App::Property",
            "Sens du fil par rapport aux cotes de la pièce : le long de la longueur, de la "
            "largeur, ou sans fil (MDF, mélaminé uni).",
        ),
    ),
    PropertySpec(
        "PreferredGrainDirection",
        "App::PropertyEnumeration",
        "Matériau",
        QT_TRANSLATE_NOOP(
            "App::Property",
            "Dernier sens du fil choisi pour la pièce, repris quand elle revient à un matériau "
            "avec fil.",
        ),
        mode=HIDDEN,
    ),
    PropertySpec(
        "Mark",
        "App::PropertyString",
        "Débit",
        QT_TRANSLATE_NOOP(
            "App::Property",
            "Repère de la pièce sur les plans et dans la liste de débit (ex. « M1 »). Des "
            "pièces identiques peuvent partager le même repère.",
        ),
    ),
    PropertySpec(
        "LengthAllowance",
        "App::PropertyLength",
        "Débit",
        QT_TRANSLATE_NOOP(
            "App::Property",
            "Surcote totale ajoutée à la longueur finie pour obtenir la longueur de débit.",
        ),
    ),
    PropertySpec(
        "WidthAllowance",
        "App::PropertyLength",
        "Débit",
        QT_TRANSLATE_NOOP(
            "App::Property",
            "Surcote totale ajoutée à la largeur finie pour obtenir la largeur de débit.",
        ),
    ),
    PropertySpec(
        "ThicknessAllowance",
        "App::PropertyLength",
        "Débit",
        QT_TRANSLATE_NOOP(
            "App::Property",
            "Surcote totale ajoutée à l'épaisseur finie pour obtenir l'épaisseur de débit.",
        ),
    ),
    PropertySpec(
        "Version",
        "App::PropertyInteger",
        "Base",
        QT_TRANSLATE_NOOP(
            "App::Property",
            "Version du modèle de données de la pièce, utilisée pour migrer les anciens fichiers.",
        ),
        mode=HIDDEN,
    ),
)
# Genre de l'objet cité par les avertissements de la réouverture.
NOUN: Final = QT_TRANSLATE_NOOP("Menuiserie", "Pièce")


def density_quantity(value_kg_m3: float) -> Any:
    """Masse volumique en unités FreeCAD (``Quantity``), depuis des kg/m³."""
    return App.Units.Quantity(f"{value_kg_m3} {DENSITY_UNIT}")


def density_kg_m3(obj: DocumentObject) -> float:
    """Masse volumique de la pièce en kg/m³, arrondie à ``DENSITY_DECIMALS`` décimales."""
    return round(float(obj.Density.getValueAs(DENSITY_UNIT)), DENSITY_DECIMALS)


def part_kind(obj: DocumentObject, material: Material | None) -> MaterialKind:
    """Famille de la pièce : sa catégorie si elle est connue (une valeur d'une version plus
    récente est gardée telle quelle), sinon celle de ``material``, sinon le massif."""
    kind = KIND_BY_CATEGORY.get(obj.Category) if "Category" in obj.PropertiesList else None
    return kind if kind is not None else material_kind(material)


def material_kind(material: Material | None) -> MaterialKind:
    """Famille de ``material`` ; le massif sans matériau (bibliothèque vide, matériau inconnu)."""
    return material.kind if material is not None else MaterialKind.SOLID


def default_grain(kind: MaterialKind, material: Material | None) -> GrainDirection:
    """Fil par défaut d'une pièce de famille ``kind`` : celui de ``material`` s'il est de cette
    famille, sinon celui de la famille."""
    if material is not None and material.kind is kind:
        has_grain = material.has_grain
    else:
        has_grain = kind.has_grain_by_default
    return GrainDirection.LENGTH if has_grain else GrainDirection.NONE


def preferred_grain_default(
    obj: DocumentObject, kind: MaterialKind, material: Material | None
) -> GrainDirection:
    """Sens à mémoriser d'après le fil de la pièce (son fil par défaut s'il est absent ou
    inconnu) : ``LENGTH`` pour une pièce sans fil (ADR 0005)."""
    value = obj.GrainDirection if "GrainDirection" in obj.PropertiesList else None
    grain = GrainDirection(value) if value in GRAIN_DIRECTIONS else default_grain(kind, material)
    return remembered_grain(grain)


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
        "PreferredGrainDirection": preferred_grain_default(obj, kind, material).value,
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
    enumerations = {
        "Material": material_choices(library),
        "Category": list(CATEGORIES),
        "GrainDirection": list(GRAIN_DIRECTIONS),
        "PreferredGrainDirection": list(PREFERRED_GRAIN_DIRECTIONS),
    }
    schema.add_missing_properties(obj, PROPERTIES, _default_values(obj, material), enumerations)


def apply_editor_modes(obj: DocumentObject, *, show_grain: bool = True) -> None:
    """Modes d'édition du schéma ; ``GrainDirection`` est masquée si ``show_grain`` est faux
    (matériau sans fil). ``setEditorMode`` n'est appelé que si le mode change."""
    schema.apply_editor_modes(obj, [spec for spec in PROPERTIES if spec.name != "GrainDirection"])
    show_grain_direction(obj, show_grain)


def show_grain_direction(obj: DocumentObject, visible: bool) -> None:
    """Affiche ou masque ``GrainDirection`` dans l'éditeur de propriétés, si elle existe."""
    if "GrainDirection" in obj.PropertiesList:
        schema.set_editor_mode(obj, "GrainDirection", EDITABLE if visible else HIDDEN)


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
