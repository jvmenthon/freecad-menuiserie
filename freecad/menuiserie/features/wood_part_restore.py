# SPDX-License-Identifier: LGPL-2.1-or-later
"""Réouverture d'une pièce de bois : contrôle des données relues d'un document.

Un document ``.FCStd`` est une donnée externe : sa ``Version`` et ses énumérations sont
contrôlées avant la migration, le matériau de la migration est retrouvé d'après
``MaterialId``, et chaque anomalie est signalée par un avertissement traduit dont les textes
du document sont cités tronqués et échappés.
"""

from __future__ import annotations

from typing import Final

import FreeCAD as App

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.materials import Material, MaterialLibrary
from freecad.menuiserie.core.text import quoted_value
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.features.library import display_language
from freecad.menuiserie.features.wood_part_schema import (
    CATEGORIES,
    CATEGORY_BY_KIND,
    GRAIN_DIRECTIONS,
    MODEL_VERSION,
    PREFERRED_GRAIN_DIRECTIONS,
    TYPE_BY_NAME,
    default_grain,
    material_choices,
    material_kind,
    part_kind,
    preferred_grain_default,
    select_label,
)

EMPTY_LIBRARY_MIGRATION: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Pièce « {label} » : bibliothèque de matériaux vide, propriétés manquantes recréées avec "
    "des valeurs par défaut (massif si la catégorie manque).",
)
_INVALID_VERSION: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Pièce « {label} » : version du modèle illisible (« {value} »), document traité comme un "
    "ancien fichier (version 0).",
)
_NEWER_VERSION: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Pièce « {label} » : document créé par une version plus récente de l'atelier (modèle "
    "{version}, {supported} au plus ici) ; mettez l'atelier à jour avant de le modifier.",
)
_UNKNOWN_VALUE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Pièce « {label} » : valeur « {value} » inconnue pour {property}, remplacée par "
    "« {replacement} ».",
)
_UNEXPECTED_TYPE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Pièce « {label} » : propriété {property} d'un type inattendu (« {type} », valeur "
    "« {value} »), recréée avec sa valeur par défaut.",
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


def stored_material(obj: DocumentObject, library: MaterialLibrary) -> Material | None:
    """Matériau de la bibliothèque désigné par ``MaterialId`` ; ``None`` si la propriété manque
    ou si le matériau est inconnu localement."""
    material_id = obj.MaterialId if "MaterialId" in obj.PropertiesList else ""
    return library.find(material_id)


def migration_material(obj: DocumentObject, library: MaterialLibrary) -> Material | None:
    """Matériau de la pièce d'après ``MaterialId`` ; s'il est absent ou inconnu localement, le
    matériau par défaut de la bibliothèque ; ``None`` si la bibliothèque est vide."""
    material = stored_material(obj, library)
    if material is None and len(library):
        material = library.default_material()
    return material


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


def warn(obj: DocumentObject, template: str, **params: object) -> None:
    """Avertissement traduit dans la vue rapport. Le libellé de la pièce (``{label}``) et les
    ``params``, lus dans un document, y sont cités tronqués et échappés (``quoted_value``)."""
    quoted = {name: quoted_value(value) for name, value in params.items()}
    quoted["label"] = quoted_value(obj.Label)
    App.Console.PrintWarning(f"Menuiserie : {translated(template, quoted)}\n")


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
    mistyped = [
        name
        for name, type_id in TYPE_BY_NAME.items()
        if name in obj.PropertiesList and obj.getTypeIdOfProperty(name) != type_id
    ]
    for name in mistyped:
        type_id = obj.getTypeIdOfProperty(name)
        warn(obj, _UNEXPECTED_TYPE, property=name, type=type_id, value=getattr(obj, name))
        obj.removeProperty(name)
    return mistyped


def restored_version(obj: DocumentObject) -> int:
    """Version enregistrée de la pièce, 0 si elle est absente. D'un type inattendu, elle est
    supprimée (la migration la recrée) et vaut 0 ; plus récente que l'atelier, elle est gardée.
    Ces deux cas sont signalés par un avertissement."""
    if "Version" not in obj.PropertiesList:
        return 0
    if obj.getTypeIdOfProperty("Version") != TYPE_BY_NAME["Version"]:
        warn(obj, _INVALID_VERSION, value=obj.Version)
        obj.removeProperty("Version")
        return 0
    version: int = obj.Version
    if version > MODEL_VERSION:
        warn(obj, _NEWER_VERSION, version=version, supported=MODEL_VERSION)
    return version
