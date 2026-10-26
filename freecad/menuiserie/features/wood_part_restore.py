# SPDX-License-Identifier: LGPL-2.1-or-later
"""Réouverture d'une pièce de bois : contrôle des données relues d'un document.

Un document ``.FCStd`` est une donnée externe : sa ``Version``, le type de chaque propriété et
ses énumérations sont contrôlés avant la migration. Une propriété dont le type n'est pas celui
du schéma est supprimée, quelle que soit la ``Version`` (même sur un document plus récent : noms
et types sont figés par l'ADR 0003), puis recréée par la migration avec sa valeur par défaut ;
elle est donc perdue à l'enregistrement. Le matériau de la migration est retrouvé d'après
``MaterialId``, à défaut d'après le libellé ``Material``. Chaque anomalie est signalée par un
avertissement traduit dont les textes du document sont cités tronqués et échappés.
"""

from __future__ import annotations

from typing import Final

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.materials import Material, MaterialLibrary
from freecad.menuiserie.features import schema
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.library import display_language
from freecad.menuiserie.features.schema import warn
from freecad.menuiserie.features.wood_material import (
    CATEGORIES,
    CATEGORY_BY_KIND,
    GRAIN_DIRECTIONS,
    PREFERRED_GRAIN_DIRECTIONS,
    default_grain,
    material_choices,
    material_kind,
    part_kind,
    preferred_grain_default,
    select_label,
    stored_material,
)
from freecad.menuiserie.features.wood_part_schema import (
    MODEL_VERSION,
    NOUN,
    PROPERTIES,
)

EMPTY_LIBRARY_MIGRATION: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Pièce « {label} » : bibliothèque de matériaux vide, propriétés manquantes recréées avec "
    "des valeurs par défaut (massif si la catégorie manque).",
)
_UNKNOWN_VALUE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Pièce « {label} » : valeur « {value} » inconnue pour {property}, remplacée par "
    "« {replacement} ».",
)
_UNKNOWN_VALUE_KEPT: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Pièce « {label} » : valeur « {value} » inconnue pour {property}, conservée telle quelle "
    "(document d'une version plus récente).",
)
_MISSING_MATERIAL: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Pièce « {label} » : matériau « {id} » absent de la bibliothèque locale, "
    "valeurs enregistrées conservées (masse volumique, catégorie, libellé).",
)


def migration_material(obj: DocumentObject, library: MaterialLibrary) -> Material | None:
    """Matériau de la pièce d'après ``MaterialId`` ; si cette propriété manque (supprimée car
    d'un type inattendu), d'après le libellé ``Material`` (``find_by_name``) ; sinon, ou s'il
    est inconnu localement, le matériau par défaut de la bibliothèque ; ``None`` si la
    bibliothèque est vide."""
    material = stored_material(obj, library)
    if material is None and "MaterialId" not in obj.PropertiesList:
        material = _material_named(obj, library)
    if material is None and len(library):
        material = library.default_material()
    return material


def _material_named(obj: DocumentObject, library: MaterialLibrary) -> Material | None:
    """Matériau dont le libellé est celui de ``Material`` ; ``None`` si la propriété manque ou
    n'est pas un texte."""
    label = obj.Material if "Material" in obj.PropertiesList else None
    return library.find_by_name(label, display_language()) if isinstance(label, str) else None


def restore_material_choices(obj: DocumentObject, library: MaterialLibrary) -> None:
    """Liste ``Material`` de la bibliothèque locale ; un matériau inconnu localement garde son
    libellé enregistré (ajouté à la liste) et ses valeurs, avec un avertissement."""
    material = stored_material(obj, library)
    if material is None:
        label = obj.Material
        warn(obj, _MISSING_MATERIAL, id=obj.MaterialId)
    else:
        label = material.name(display_language())
    select_label(obj, material_choices(library, label), label)


def restore_enumerations(
    obj: DocumentObject, library: MaterialLibrary, *, keep_unknown: bool = False
) -> None:
    """Listes canoniques de ``Category``, ``GrainDirection`` puis ``PreferredGrainDirection``
    (celles du fichier sont des données externes) ; une valeur inconnue devient la catégorie du
    matériau de la pièce (ou ``Solid``), le fil par défaut, puis le sens mémorisable du fil de
    la pièce, avec un avertissement.

    ``keep_unknown`` (document d'une version plus récente) : une valeur inconnue est gardée,
    avec la liste du fichier qui la contient, pour ne pas être perdue à l'enregistrement."""
    material = stored_material(obj, library)
    fallback = CATEGORY_BY_KIND[material_kind(material)]
    _restore_enumeration(obj, "Category", CATEGORIES, fallback, keep_unknown)
    kind = part_kind(obj, material)
    grain = default_grain(kind, material)
    _restore_enumeration(obj, "GrainDirection", GRAIN_DIRECTIONS, grain.value, keep_unknown)
    preferred = preferred_grain_default(obj, kind, material)
    _restore_enumeration(
        obj, "PreferredGrainDirection", PREFERRED_GRAIN_DIRECTIONS, preferred.value, keep_unknown
    )


def _restore_enumeration(
    obj: DocumentObject, name: str, choices: tuple[str, ...], fallback: str, keep_unknown: bool
) -> None:
    """Liste ``choices`` pour l'énumération ``name`` si elle existe ; valeur conservée si elle
    en fait partie, sinon remplacée par ``fallback`` (ou gardée, liste comprise, si
    ``keep_unknown``). N'écrit que ce qui change."""
    if name not in obj.PropertiesList:
        return
    value = getattr(obj, name)
    if value not in choices and keep_unknown:
        warn(obj, _UNKNOWN_VALUE_KEPT, property=name, value=value)
        return
    if obj.getEnumerationsOfProperty(name) != list(choices):
        setattr(obj, name, list(choices))
    if value not in choices:
        setattr(obj, name, fallback)
        warn(obj, _UNKNOWN_VALUE, property=name, value=value, replacement=fallback)
    elif getattr(obj, name) != value:
        setattr(obj, name, value)


def remove_mistyped_properties(obj: DocumentObject) -> list[str]:
    """Supprime chaque propriété de la pièce dont le type n'est pas celui du schéma (donnée
    externe que ni ``record_of`` ni ``onChanged`` ne sauraient lire), avec un avertissement
    citant son type et sa valeur ; renvoie leurs noms, à recréer par la migration."""
    return schema.remove_mistyped_properties(obj, PROPERTIES, NOUN)


def restored_version(obj: DocumentObject) -> int:
    """Version enregistrée de la pièce, 0 si elle est absente. D'un type inattendu, elle est
    supprimée (la migration la recrée) et vaut 0 ; plus récente que l'atelier, elle est gardée.
    Ces deux cas sont signalés par un avertissement."""
    return schema.restored_version(obj, MODEL_VERSION, NOUN)
