# SPDX-License-Identifier: LGPL-2.1-or-later
"""Réouverture d'une pièce de bois : contrôle des données relues d'un document.

Un document ``.FCStd`` est une donnée externe : sa ``Version`` et ses énumérations sont
contrôlées avant la migration, le matériau de la migration est retrouvé d'après
``MaterialId``, et chaque anomalie est signalée par un avertissement traduit dont les textes
du document sont cités tronqués et échappés.
"""

from __future__ import annotations

from typing import Any, Final

import FreeCAD as App

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.materials import Material, MaterialKind, MaterialLibrary
from freecad.menuiserie.core.text import quoted_value
from freecad.menuiserie.features.library import display_language, translated
from freecad.menuiserie.features.wood_part_schema import (
    CATEGORIES,
    CATEGORY_BY_KIND,
    GRAIN_DIRECTIONS,
    MODEL_VERSION,
    TYPE_BY_NAME,
    default_grain,
    material_choices,
    part_kind,
    select_label,
)

DocumentObject = Any  # objets FreeCAD, sans annotations de type

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
_MISSING_MATERIAL: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Pièce « {label} » : matériau « {id} » absent de la bibliothèque locale, "
    "valeurs enregistrées conservées (masse volumique, catégorie, libellé).",
)


def migration_material(obj: DocumentObject, library: MaterialLibrary) -> Material | None:
    """Matériau de la pièce d'après ``MaterialId`` ; s'il est absent ou inconnu localement, le
    matériau par défaut de la bibliothèque ; ``None`` si la bibliothèque est vide."""
    material_id = obj.MaterialId if "MaterialId" in obj.PropertiesList else ""
    material = library.find(material_id)
    if material is None and len(library):
        material = library.default_material()
    return material


def restore_material_choices(obj: DocumentObject, library: MaterialLibrary) -> None:
    """Liste ``Material`` de la bibliothèque locale ; un matériau inconnu localement garde son
    libellé enregistré (ajouté à la liste) et ses valeurs, avec un avertissement."""
    material = library.find(obj.MaterialId)
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


def restore_enumerations(obj: DocumentObject, library: MaterialLibrary) -> None:
    """Listes canoniques de ``Category`` et ``GrainDirection`` (celles du fichier sont des
    données externes) ; une valeur inconnue devient la catégorie du matériau de la pièce (ou
    ``Solid``) et le fil par défaut, avec un avertissement."""
    material_id = obj.MaterialId if "MaterialId" in obj.PropertiesList else ""
    material = library.find(material_id)
    kind = material.kind if material is not None else MaterialKind.SOLID
    _restore_enumeration(obj, "Category", CATEGORIES, CATEGORY_BY_KIND[kind])
    grain = default_grain(part_kind(obj, material), material)
    _restore_enumeration(obj, "GrainDirection", GRAIN_DIRECTIONS, grain.value)


def _restore_enumeration(
    obj: DocumentObject, name: str, choices: tuple[str, ...], fallback: str
) -> None:
    """Liste ``choices`` pour l'énumération ``name`` si elle existe ; valeur conservée si elle
    en fait partie, sinon remplacée par ``fallback``. N'écrit que ce qui change."""
    if name not in obj.PropertiesList:
        return
    value = getattr(obj, name)
    if obj.getEnumerationsOfProperty(name) != list(choices):
        setattr(obj, name, list(choices))
    if value not in choices:
        setattr(obj, name, fallback)
        warn(obj, _UNKNOWN_VALUE, property=name, value=value, replacement=fallback)
    elif getattr(obj, name) != value:
        setattr(obj, name, value)


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
