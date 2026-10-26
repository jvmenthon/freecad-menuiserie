# SPDX-License-Identifier: LGPL-2.1-or-later
"""Matériau, fil, repère et surcotes d'une pièce : propriétés et règles partagées par la pièce de
bois (``WoodPart``) et la pièce en bois (``ShapedPart``), par composition (ADR 0020, décision 6).

Extrait de ``wood_part_schema`` et ``wood_part`` sans changer leur comportement : spécifications
des propriétés de matériau (``MATERIAL_PROPERTIES``), valeurs stockées des énumérations, valeurs
par défaut déduites du matériau, modes d'édition, recopie d'un matériau dans une pièce et
mémoire du sens du fil (ADR 0005). Les fonctions prennent l'objet, jamais un proxy. Les noms et
valeurs écrits dans les documents relèvent du contrat de persistance (ADR 0003). Le proxy qui
branche ces fonctions sur ``onChanged`` est dans :mod:`.wood_material_proxy`.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any, Final, TypeVar

import FreeCAD as App

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.materials import Material, MaterialKind, MaterialLibrary
from freecad.menuiserie.core.part_model import (
    Allowances,
    GrainDirection,
    allowances_after_material_change,
    default_allowances,
    grain_after_material_change,
    material_has_grain,
    remembered_grain,
)
from freecad.menuiserie.core.text import quoted_value
from freecad.menuiserie.features import schema
from freecad.menuiserie.features.freecad_types import EDITABLE, HIDDEN, READ_ONLY, DocumentObject
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.features.library import display_language
from freecad.menuiserie.features.schema import LENGTH, PropertySpec

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
GRAIN_BY_VALUE: Final[Mapping[str, GrainDirection]] = {g.value: g for g in GrainDirection}

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
# Propriété ``Version`` des deux sortes de pièces (chacune fournit sa valeur par défaut).
VERSION_SPEC: Final = PropertySpec(
    "Version",
    "App::PropertyInteger",
    "Base",
    QT_TRANSLATE_NOOP(
        "App::Property",
        "Version du modèle de données de la pièce, utilisée pour migrer les anciens fichiers.",
    ),
    mode=HIDDEN,
)
_T = TypeVar("_T")

# Propriétés de matériau, de fil, de repère et de surcotes, dans l'ordre d'ajout (le même pour
# les deux sortes de pièces : mêmes noms, types, groupes, énumérations et infobulles).
MATERIAL_PROPERTIES: Final = (
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
            "Repère de la pièce sur les plans et dans la liste de débit (ex. « M1 ») ; c'est "
            "aussi son nom dans l'arborescence. Des pièces identiques peuvent partager le même "
            "repère.",
        ),
    ),
    PropertySpec(
        "LengthAllowance",
        LENGTH,
        "Débit",
        QT_TRANSLATE_NOOP(
            "App::Property",
            "Surcote totale ajoutée à la longueur finie pour obtenir la longueur de débit.",
        ),
    ),
    PropertySpec(
        "WidthAllowance",
        LENGTH,
        "Débit",
        QT_TRANSLATE_NOOP(
            "App::Property",
            "Surcote totale ajoutée à la largeur finie pour obtenir la largeur de débit.",
        ),
    ),
    PropertySpec(
        "ThicknessAllowance",
        LENGTH,
        "Débit",
        QT_TRANSLATE_NOOP(
            "App::Property",
            "Surcote totale ajoutée à l'épaisseur finie pour obtenir l'épaisseur de débit.",
        ),
    ),
)


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


def allowances_of(obj: DocumentObject) -> Allowances:
    """Surcotes de débit de la pièce en mm."""
    return Allowances(
        obj.LengthAllowance.Value, obj.WidthAllowance.Value, obj.ThicknessAllowance.Value
    )


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


def material_default_values(obj: DocumentObject, material: Material | None) -> dict[str, object]:
    """Valeurs par défaut des propriétés de matériau : ``material``, puis catégorie, fil, repère
    vide et surcotes de la famille de la pièce (:func:`part_kind`).

    Sans matériau (bibliothèque vide), ``Material``, ``MaterialId`` et ``Density`` n'ont pas de
    valeur par défaut : une propriété absente garde la valeur vide de son type.
    """
    kind = part_kind(obj, material)
    allowances = default_allowances(kind)
    values: dict[str, object] = {
        "Category": CATEGORY_BY_KIND[kind],
        "GrainDirection": default_grain(kind, material).value,
        "PreferredGrainDirection": preferred_grain_default(obj, kind, material).value,
        "Mark": "",
        "LengthAllowance": allowances.length,
        "WidthAllowance": allowances.width,
        "ThicknessAllowance": allowances.thickness,
    }
    if material is not None:
        values["Material"] = material.name(display_language())
        values["MaterialId"] = material.id
        values["Density"] = density_quantity(material.density)
    return values


def material_enumerations(library: MaterialLibrary) -> dict[str, list[str]]:
    """Listes de choix des quatre énumérations de matériau, pour ``add_missing_properties``."""
    return {
        "Material": material_choices(library),
        "Category": list(CATEGORIES),
        "GrainDirection": list(GRAIN_DIRECTIONS),
        "PreferredGrainDirection": list(PREFERRED_GRAIN_DIRECTIONS),
    }


def apply_material_modes(
    obj: DocumentObject, *, show_grain: bool, material_read_only: bool
) -> None:
    """Modes d'édition des propriétés de matériau présentes, ceux de ``MATERIAL_PROPERTIES``,
    sauf deux cas qui dépendent de la pièce : ``GrainDirection`` est masquée si ``show_grain``
    est faux (matériau sans fil) et ``Material`` est en lecture seule si ``material_read_only``
    est vrai (pièce d'un document plus récent). ``setEditorMode`` n'est appelé que si le mode
    change."""
    specs = [
        spec for spec in MATERIAL_PROPERTIES if spec.name not in ("GrainDirection", "Material")
    ]
    schema.apply_editor_modes(obj, specs)
    show_grain_direction(obj, show_grain)
    if "Material" in obj.PropertiesList:
        schema.set_editor_mode(obj, "Material", READ_ONLY if material_read_only else EDITABLE)


def is_newer_version(obj: DocumentObject, current: int) -> bool:
    """Vrai si ``Version`` de la pièce dépasse ``current`` : document créé par une version plus
    récente de l'atelier, dont le matériau n'est pas modifiable ici (issue #13)."""
    version = getattr(obj, "Version", 0) if "Version" in obj.PropertiesList else 0
    return isinstance(version, int) and version > current


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


def stored_material(obj: DocumentObject, library: MaterialLibrary) -> Material | None:
    """Matériau de la bibliothèque désigné par ``MaterialId`` ; ``None`` si la propriété manque
    ou si le matériau est inconnu localement."""
    material_id = obj.MaterialId if "MaterialId" in obj.PropertiesList else ""
    return library.find(material_id)


def shows_grain(obj: DocumentObject, library: MaterialLibrary) -> bool:
    """Visibilité du fil d'après le matériau de la pièce dans ``library`` : son matériau (ou,
    inconnu localement, sa famille) a un fil."""
    material = stored_material(obj, library)
    return material_has_grain(material, part_kind(obj, material))


def apply_material(obj: DocumentObject, material: Material) -> None:
    """Recopie le matériau dans la pièce ; fil et surcotes suivent les règles de ``core``.
    ``UnsupportedPartError`` (rien n'est écrit) si la catégorie ou le fil actuel est inconnu."""
    old_kind = known_value(obj, "Category", KIND_BY_CATEGORY)
    grain = grain_after_material_change(
        material, known_value(obj, "GrainDirection", GRAIN_BY_VALUE), preferred_grain(obj)
    )
    allowances = allowances_after_material_change(old_kind, material.kind, allowances_of(obj))
    obj.MaterialId = material.id
    obj.Category = CATEGORY_BY_KIND[material.kind]
    obj.Density = density_quantity(material.density)
    obj.GrainDirection = grain.value
    obj.LengthAllowance = allowances.length
    obj.WidthAllowance = allowances.width
    obj.ThicknessAllowance = allowances.thickness


def preferred_grain(obj: DocumentObject) -> GrainDirection:
    """Sens mémorisé de la pièce ; ``LENGTH`` s'il est absent ou inconnu (jamais d'erreur)."""
    value = getattr(obj, "PreferredGrainDirection", None)
    if value == GrainDirection.WIDTH.value:
        return GrainDirection.WIDTH
    return GrainDirection.LENGTH


def remember_grain(obj: DocumentObject) -> None:
    """Mémorise le sens du fil choisi (``Length`` ou ``Width``) ; « Sans fil » ne l'efface pas.
    Écrit dans la transaction de l'appelant, seulement si la mémoire change."""
    if "PreferredGrainDirection" not in obj.PropertiesList:
        return
    try:
        grain = GrainDirection(obj.GrainDirection)
    except ValueError:  # valeur d'une version plus récente, gardée à la réouverture
        return
    if grain is GrainDirection.NONE:  # la mémoire reste telle quelle, même illisible
        return
    remembered = remembered_grain(grain, preferred_grain(obj)).value
    if obj.PreferredGrainDirection != remembered:
        obj.PreferredGrainDirection = remembered
