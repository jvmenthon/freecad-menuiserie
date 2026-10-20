# SPDX-License-Identifier: LGPL-2.1-or-later
"""Schéma générique des objets du document : propriétés décrites par des données.

Chaque objet de l'atelier (pièce de bois, pièce usinée, assemblage) décrit ses propriétés par des
:class:`PropertySpec` ; les aides de ce module les ajoutent, contrôlent leurs types et leur
``Version`` à la réouverture et appliquent leurs modes d'édition (règles de l'ADR 0003). Les
avertissements citent le genre de l'objet (« Pièce », « Pièce usinée », « Assemblage »).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

import FreeCAD as App

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.text import quoted_value
from freecad.menuiserie.features.freecad_types import EDITABLE, HIDDEN, READ_ONLY, DocumentObject
from freecad.menuiserie.features.i18n import translated

__all__ = [
    "PropertySpec",
    "add_missing_properties",
    "apply_editor_modes",
    "remove_mistyped_properties",
    "restore_schema",
    "restored_version",
    "set_editor_mode",
    "warn",
]

_INVALID_VERSION: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "{noun} « {label} » : version du modèle illisible (« {value} »), document traité comme un "
    "ancien fichier (version 0).",
)
_NEWER_VERSION: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "{noun} « {label} » : document créé par une version plus récente de l'atelier (modèle "
    "{version}, {supported} au plus ici) ; mettez l'atelier à jour avant de le modifier.",
)
_UNEXPECTED_TYPE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "{noun} « {label} » : propriété {property} d'un type inattendu (« {type} », valeur "
    "« {value} »), recréée avec sa valeur par défaut.",
)
# Mode d'édition tel que le renvoie ``getEditorMode``.
_MODE_NAMES: Final[Mapping[int, list[str]]] = MappingProxyType(
    {EDITABLE: [], READ_ONLY: ["ReadOnly"], HIDDEN: ["Hidden"]}
)


@dataclass(frozen=True)
class PropertySpec:
    """Propriété d'un objet : type FreeCAD, groupe, infobulle, défaut (``None`` : aucun, la
    propriété garde la valeur vide de son type) et mode d'édition."""

    name: str
    type_id: str
    group: str
    tooltip: str
    default: object = None
    mode: int = EDITABLE


def warn(obj: DocumentObject, template: str, **params: object) -> None:
    """Avertissement traduit dans la vue rapport. Le libellé de l'objet (``{label}``) et les
    ``params``, lus dans un document, y sont cités tronqués et échappés (``quoted_value``) ;
    ``noun`` (genre de l'objet, gabarit traduisible) est traduit."""
    quoted = {name: quoted_value(value) for name, value in params.items() if name != "noun"}
    if "noun" in params:
        quoted["noun"] = translated(str(params["noun"]))
    quoted["label"] = quoted_value(obj.Label)
    App.Console.PrintWarning(f"Menuiserie : {translated(template, quoted)}\n")


def add_missing_properties(
    obj: DocumentObject,
    specs: Iterable[PropertySpec],
    defaults: Mapping[str, object] | None = None,
    choices: Mapping[str, list[str]] | None = None,
) -> None:
    """Ajoute les propriétés absentes de ``obj`` ; une énumération reçoit sa liste ``choices``,
    puis chaque propriété sa valeur de ``defaults`` (à défaut, celle de sa spécification)."""
    for spec in specs:
        if spec.name in obj.PropertiesList:
            continue
        obj.addProperty(spec.type_id, spec.name, spec.group, spec.tooltip)
        if choices and spec.name in choices:
            setattr(obj, spec.name, choices[spec.name])
        value = (defaults or {}).get(spec.name, spec.default)
        if value is not None:
            setattr(obj, spec.name, value)


def apply_editor_modes(obj: DocumentObject, specs: Iterable[PropertySpec]) -> None:
    """Modes d'édition des propriétés présentes, écrits seulement s'ils changent."""
    for spec in specs:
        if spec.name in obj.PropertiesList:
            set_editor_mode(obj, spec.name, spec.mode)


def set_editor_mode(obj: DocumentObject, name: str, mode: int) -> None:
    """Mode d'édition de la propriété ``name``, écrit seulement s'il change."""
    if obj.getEditorMode(name) != _MODE_NAMES[mode]:
        obj.setEditorMode(name, mode)


def remove_mistyped_properties(
    obj: DocumentObject, specs: Iterable[PropertySpec], noun: str
) -> list[str]:
    """Supprime chaque propriété dont le type n'est pas celui du schéma (donnée externe
    illisible), avec un avertissement citant son type et sa valeur ; renvoie leurs noms, à
    recréer par la migration."""
    mistyped = [
        spec.name
        for spec in specs
        if spec.name in obj.PropertiesList and obj.getTypeIdOfProperty(spec.name) != spec.type_id
    ]
    for name in mistyped:
        type_id = obj.getTypeIdOfProperty(name)
        warn(
            obj, _UNEXPECTED_TYPE, noun=noun, property=name, type=type_id, value=getattr(obj, name)
        )
        obj.removeProperty(name)
    return mistyped


def restored_version(obj: DocumentObject, current: int, noun: str) -> int:
    """Version enregistrée de l'objet, 0 si elle est absente. D'un type inattendu, elle est
    supprimée (la migration la recrée) et vaut 0 ; plus récente que ``current``, elle est
    gardée. Ces deux cas sont signalés par un avertissement."""
    if "Version" not in obj.PropertiesList:
        return 0
    if obj.getTypeIdOfProperty("Version") != "App::PropertyInteger":
        warn(obj, _INVALID_VERSION, noun=noun, value=obj.Version)
        obj.removeProperty("Version")
        return 0
    version: int = obj.Version
    if version > current:
        warn(obj, _NEWER_VERSION, noun=noun, version=version, supported=current)
    return version


def restore_schema(
    obj: DocumentObject, specs: tuple[PropertySpec, ...], current: int, noun: str
) -> None:
    """Réouverture d'un objet sans énumération ni défaut calculé : ``Version`` et types
    contrôlés, propriétés manquantes recréées (``Version`` portée à ``current`` si elle est
    plus ancienne ; une version plus récente n'est pas migrée), modes d'édition."""
    version = restored_version(obj, current, noun)
    mistyped = remove_mistyped_properties(obj, specs, noun)
    if version < current or mistyped:
        add_missing_properties(obj, specs)
    if version < current:
        obj.Version = current
    apply_editor_modes(obj, specs)
