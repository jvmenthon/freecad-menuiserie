# SPDX-License-Identifier: LGPL-2.1-or-later
"""Bibliothèque de matériaux : essences massives et panneaux (ADR 0002).

Lecture, validation et fusion des fichiers JSON de matériaux (format 1). Les fonctions
de lecture ne lèvent jamais d'exception pour un fichier invalide : chaque anomalie est
renvoyée sous forme de :class:`LibraryIssue`, dont le message est un gabarit français
marqué pour la traduction.

Ce module est une façade : il ré-exporte l'API publique des sous-modules privés
(``_model``, ``_issues``, ``_parser``, ``_reader``, ``_merge``) et ne contient aucune logique.
"""

from __future__ import annotations

from freecad.menuiserie.core.materials._issues import (
    MAX_ISSUES,
    MAX_LISTED_KEYS,
    LibraryFormatError,
    LibraryIssue,
    Severity,
)
from freecad.menuiserie.core.materials._merge import load_library, merge_materials
from freecad.menuiserie.core.materials._messages import BUILTIN_SOURCE
from freecad.menuiserie.core.materials._model import (
    MAX_DENSITY,
    MAX_ID_LENGTH,
    MAX_NAME_LENGTH,
    MAX_TEXTURE_PATH_LENGTH,
    MAX_TEXTURE_SIZE_MM,
    MAX_THICKNESS_MM,
    MAX_THICKNESSES,
    MIN_DENSITY,
    MIN_TEXTURE_SIZE_MM,
    TEXTURE_EXTENSIONS,
    Material,
    MaterialKind,
    MaterialLibrary,
    Texture,
    UnknownMaterialError,
    is_inside_folder,
)
from freecad.menuiserie.core.materials._parser import (
    FORMAT_VERSION,
    MAX_MATERIALS,
    parse_materials,
)
from freecad.menuiserie.core.materials._reader import MAX_FILE_BYTES, read_materials_file

__all__ = [
    "BUILTIN_SOURCE",
    "FORMAT_VERSION",
    "MAX_DENSITY",
    "MAX_FILE_BYTES",
    "MAX_ID_LENGTH",
    "MAX_ISSUES",
    "MAX_LISTED_KEYS",
    "MAX_MATERIALS",
    "MAX_NAME_LENGTH",
    "MAX_TEXTURE_PATH_LENGTH",
    "MAX_TEXTURE_SIZE_MM",
    "MAX_THICKNESSES",
    "MAX_THICKNESS_MM",
    "MIN_DENSITY",
    "MIN_TEXTURE_SIZE_MM",
    "TEXTURE_EXTENSIONS",
    "LibraryFormatError",
    "LibraryIssue",
    "Material",
    "MaterialKind",
    "MaterialLibrary",
    "Severity",
    "Texture",
    "UnknownMaterialError",
    "is_inside_folder",
    "load_library",
    "merge_materials",
    "parse_materials",
    "read_materials_file",
]
