# SPDX-License-Identifier: LGPL-2.1-or-later
"""Validation d'un document JSON de matériaux déjà décodé (format 1)."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path, PurePosixPath
from typing import Final, TypeGuard, TypeVar

from freecad.menuiserie.core._validation import decimal_text, has_forbidden_character
from freecad.menuiserie.core.materials._entry import (
    TEXTURE_KEYS,
    Entry,
    JsonObject,
    duplicated_field,
)
from freecad.menuiserie.core.materials._issues import (
    MAX_LISTED_KEYS,
    LibraryFormatError,
    LibraryIssue,
    Severity,
    capped,
    file_error,
    make_issue,
    unknown_keys_params,
)
from freecad.menuiserie.core.materials._messages import (
    ENTRIES_NOT_OBJECTS,
    ENTRY_DUPLICATE_ID,
    ENTRY_DUPLICATE_KEY,
    ENTRY_INVALID_COLOR,
    ENTRY_INVALID_DENSITY,
    ENTRY_INVALID_GRAIN,
    ENTRY_INVALID_ID,
    ENTRY_INVALID_KIND,
    ENTRY_INVALID_LABEL,
    ENTRY_INVALID_LANGUAGE,
    ENTRY_INVALID_NAME,
    ENTRY_INVALID_TEXTURE,
    ENTRY_INVALID_TEXTURE_IMAGE,
    ENTRY_INVALID_TEXTURE_SIZE,
    ENTRY_INVALID_THICKNESSES,
    ENTRY_MISSING_FIELD,
    ENTRY_TEXTURE_NO_FOLDER,
    ENTRY_TEXTURE_OUTSIDE,
    ROOT_DUPLICATE_KEY,
    ROOT_FORMAT_INVALID,
    ROOT_FORMAT_NEWER,
    ROOT_FORMAT_UNSUPPORTED,
    ROOT_MATERIALS_INVALID,
    ROOT_NOT_OBJECT,
    ROOT_UNKNOWN_KEYS,
    ROOT_UNKNOWN_KEYS_MORE,
    TOO_MANY_MATERIALS,
)
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
    MIN_THICKNESS_MM,
    TEXTURE_EXTENSIONS,
    Material,
    MaterialKind,
    Texture,
    is_language_code,
    normalized_color,
    normalized_density,
    normalized_id,
    normalized_label,
    normalized_texture_size,
    normalized_thicknesses,
)
from freecad.menuiserie.core.text import quoted_value

FORMAT_VERSION: Final = 1
MAX_MATERIALS: Final = 500

_ROOT_KEYS: Final = frozenset({"format", "materials"})
_COLOR_PATTERN: Final = re.compile(r"#[0-9A-Fa-f]{6}")

_T = TypeVar("_T")


def _checked(entry: Entry, value: _T | None, template: str, field: str, **params: str) -> _T:
    """Valeur normalisée par une règle de ``_model`` ; erreur de l'entrée si elle vaut ``None``."""
    if value is None:
        raise entry.error(template, field, **params)
    return value


def _parse_id(entry: Entry) -> str:
    value = normalized_id(entry.require("id"))
    return _checked(entry, value, ENTRY_INVALID_ID, "id", max=str(MAX_ID_LENGTH))


def _parse_kind(entry: Entry) -> MaterialKind:
    value = entry.require("kind")
    for kind in MaterialKind:
        if value == kind.value:
            return kind
    allowed = ", ".join(kind.value for kind in MaterialKind)
    raise entry.error(ENTRY_INVALID_KIND, "kind", allowed=allowed)


def _parse_label(entry: Entry, value: object) -> str:
    label = normalized_label(value)
    return _checked(entry, label, ENTRY_INVALID_LABEL, "name", max=str(MAX_NAME_LENGTH))


def _parse_names(entry: Entry) -> dict[str, str]:
    value = entry.require("name")
    if isinstance(value, str):
        value = {"fr": value}
    if not isinstance(value, dict) or not value:
        raise entry.error(ENTRY_INVALID_NAME, "name")
    names: dict[str, str] = {}
    for language, label in value.items():
        if not is_language_code(language):
            raise entry.error(ENTRY_INVALID_LANGUAGE, "name", language=quoted_value(language))
        names[language] = _parse_label(entry, label)
    return names


def _parse_density(entry: Entry) -> float:
    density = normalized_density(entry.require("density"))
    bounds = {"min": decimal_text(MIN_DENSITY), "max": decimal_text(MAX_DENSITY)}
    return _checked(entry, density, ENTRY_INVALID_DENSITY, "density", **bounds)


def _parse_thicknesses(entry: Entry) -> tuple[float, ...]:
    thicknesses = normalized_thicknesses(entry.require("thicknesses"))
    params = {
        "count": str(MAX_THICKNESSES),
        "min": decimal_text(MIN_THICKNESS_MM),
        "max": decimal_text(MAX_THICKNESS_MM),
    }
    return _checked(entry, thicknesses, ENTRY_INVALID_THICKNESSES, "thicknesses", **params)


def _hex_color(value: object) -> tuple[int, int, int] | None:
    """Triplet RVB d'une couleur « #RRGGBB », sinon ``None``."""
    if not isinstance(value, str) or not _COLOR_PATTERN.fullmatch(value):
        return None
    return int(value[1:3], 16), int(value[3:5], 16), int(value[5:7], 16)


def _parse_color(entry: Entry) -> tuple[int, int, int]:
    color = normalized_color(_hex_color(entry.require("color")))
    return _checked(entry, color, ENTRY_INVALID_COLOR, "color")


def _parse_has_grain(entry: Entry, kind: MaterialKind) -> bool:
    value = entry.data.get("has_grain", kind.has_grain_by_default)
    if not isinstance(value, bool):
        raise entry.error(ENTRY_INVALID_GRAIN, "has_grain")
    return value


def _is_safe_image_path(value: object) -> TypeGuard[str]:
    """Chemin relatif portable vers une image : ni absolu, ni « .. », ni « \\ », ni « : »."""
    if not isinstance(value, str) or not 1 <= len(value) <= MAX_TEXTURE_PATH_LENGTH:
        return False
    if has_forbidden_character(value) or "\\" in value or ":" in value:
        return False
    parts = value.split("/")
    if parts[0] == "" or ".." in parts:
        return False
    return PurePosixPath(parts[-1]).suffix.lower() in TEXTURE_EXTENSIONS


def _resolve_in_folder(entry: Entry, relative: str) -> tuple[Path, Path]:
    """Dossier résolu du fichier et chemin absolu résolu de l'image, qui doit y rester."""
    if entry.folder is None:
        raise entry.error(ENTRY_TEXTURE_NO_FOLDER, "texture.image")
    try:
        folder = entry.folder.resolve()
        image = (folder / relative).resolve()
    except (OSError, RuntimeError, ValueError) as error:  # boucle de liens, chemin invalide
        raise entry.error(ENTRY_TEXTURE_OUTSIDE, "texture.image") from error
    if image == folder or not image.is_relative_to(folder):
        raise entry.error(ENTRY_TEXTURE_OUTSIDE, "texture.image")
    return folder, image


def _parse_texture_image(entry: Entry, value: object) -> tuple[Path, Path]:
    if not _is_safe_image_path(value):
        raise entry.error(
            ENTRY_INVALID_TEXTURE_IMAGE,
            "texture.image",
            max=str(MAX_TEXTURE_PATH_LENGTH),
            extensions=", ".join(TEXTURE_EXTENSIONS),
        )
    return _resolve_in_folder(entry, value)


def _parse_texture_size(entry: Entry, value: object) -> tuple[float, float]:
    size = normalized_texture_size(value)
    bounds = {"min": decimal_text(MIN_TEXTURE_SIZE_MM), "max": decimal_text(MAX_TEXTURE_SIZE_MM)}
    return _checked(entry, size, ENTRY_INVALID_TEXTURE_SIZE, "texture.size", **bounds)


def _parse_texture(entry: Entry) -> Texture | None:
    """Texture facultative ; toute anomalie rejette l'entrée, comme pour les autres champs."""
    if "texture" not in entry.data:
        return None
    value = entry.data["texture"]
    if not isinstance(value, dict):
        raise entry.error(ENTRY_INVALID_TEXTURE, "texture")
    for key in TEXTURE_KEYS:
        if key not in value:
            raise entry.error(ENTRY_MISSING_FIELD, f"texture.{key}")
    folder, image = _parse_texture_image(entry, value["image"])
    return Texture(image, _parse_texture_size(entry, value["size"]), folder)


def _build_material(entry: Entry, material_id: str) -> Material:
    kind = _parse_kind(entry)
    return Material(
        id=material_id,
        kind=kind,
        names=_parse_names(entry),
        density=_parse_density(entry),
        thicknesses=_parse_thicknesses(entry),
        color=_parse_color(entry),
        has_grain=_parse_has_grain(entry, kind),
        texture=_parse_texture(entry),
    )


def _identified(entry: Entry) -> tuple[Entry, str]:
    """Entrée munie de son identifiant ; :class:`LibraryFormatError` s'il est invalide ou répété."""
    if isinstance(entry.data, JsonObject) and "id" in entry.data.duplicate_keys:
        raise entry.error(ENTRY_DUPLICATE_KEY, "id")
    material_id = _parse_id(entry)
    return replace(entry, material_id=material_id), material_id


def _parse_entry(entry: Entry) -> tuple[Material | None, list[LibraryIssue]]:
    """Valide une entrée ; s'arrête à la première règle violée (entrée rejetée)."""
    try:
        entry, material_id = _identified(entry)
    except LibraryFormatError as error:
        return None, [error.issue]
    issues = entry.unknown_keys_issues()
    duplicated = duplicated_field(entry.data)
    if duplicated is not None:
        error_issue = entry.issue(Severity.ERROR, ENTRY_DUPLICATE_KEY, quoted_value(duplicated))
        return None, [*issues, error_issue]
    try:
        material = _build_material(entry, material_id)
    except LibraryFormatError as error:
        return None, [*issues, error.issue]
    return material, issues


def _check_format(value: object, source: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise file_error(source, ROOT_FORMAT_INVALID)
    if value != FORMAT_VERSION:
        template = ROOT_FORMAT_NEWER if value > FORMAT_VERSION else ROOT_FORMAT_UNSUPPORTED
        shown = quoted_value(value)
        raise file_error(source, template, format=shown, supported=str(FORMAT_VERSION))


def _select_entries(
    raw_entries: list[object], source: str, folder: Path | None
) -> tuple[list[Entry], list[LibraryIssue]]:
    """Entrées objets parmi les ``MAX_MATERIALS`` premières ; une erreur par règle violée."""
    issues: list[LibraryIssue] = []
    if len(raw_entries) > MAX_MATERIALS:
        issues.append(
            make_issue(
                Severity.ERROR,
                source,
                TOO_MANY_MATERIALS,
                count=str(len(raw_entries)),
                max=str(MAX_MATERIALS),
            )
        )
    kept = list(enumerate(raw_entries[:MAX_MATERIALS], start=1))
    rejected = [str(position) for position, raw in kept if not isinstance(raw, dict)]
    if rejected:
        positions = ", ".join(rejected)
        issues.append(make_issue(Severity.ERROR, source, ENTRIES_NOT_OBJECTS, positions=positions))
    entries = [
        Entry(source, position, raw, folder) for position, raw in kept if isinstance(raw, dict)
    ]
    return entries, issues


def _root_unknown_keys_issues(data: Mapping[object, object], source: str) -> list[LibraryIssue]:
    """Au plus un avertissement, qui liste les clés inconnues de la racine."""
    keys = [quoted_value(key) for key in data if key not in _ROOT_KEYS]
    if not keys:
        return []
    template = ROOT_UNKNOWN_KEYS_MORE if len(keys) > MAX_LISTED_KEYS else ROOT_UNKNOWN_KEYS
    return [make_issue(Severity.WARNING, source, template, **unknown_keys_params(keys))]


def _parse_root(
    data: object, source: str, folder: Path | None
) -> tuple[list[Entry], list[LibraryIssue]]:
    """Vérifie la racine ; lève :class:`LibraryFormatError` si le fichier doit être ignoré."""
    if not isinstance(data, dict):
        raise file_error(source, ROOT_NOT_OBJECT)
    if isinstance(data, JsonObject):
        raise file_error(source, ROOT_DUPLICATE_KEY, field=quoted_value(data.duplicate_keys[0]))
    _check_format(data.get("format"), source)
    raw_entries = data.get("materials")
    if not isinstance(raw_entries, list):
        raise file_error(source, ROOT_MATERIALS_INVALID)
    warnings = _root_unknown_keys_issues(data, source)
    entries, issues = _select_entries(raw_entries, source, folder)
    return entries, [*warnings, *issues]


def parse_materials(
    data: object, source: str, folder: Path | None = None
) -> tuple[list[Material], list[LibraryIssue]]:
    """Valide un document JSON déjà décodé (format 1) et en extrait les matériaux valides.

    ``folder`` est le dossier du fichier, auquel les chemins des textures sont relatifs ; sans
    lui, une entrée qui déclare une texture est rejetée. Au plus ``MAX_ISSUES`` anomalies sont
    renvoyées, suivies d'une anomalie de synthèse.
    """
    try:
        entries, issues = _parse_root(data, source, folder)
    except LibraryFormatError as error:
        return [], [error.issue]
    materials: dict[str, Material] = {}
    for entry in entries:
        material, entry_issues = _parse_entry(entry)
        issues.extend(entry_issues)
        if material is None:
            continue
        if material.id in materials:
            duplicate = replace(entry, material_id=material.id)
            issues.append(duplicate.issue(Severity.ERROR, ENTRY_DUPLICATE_ID, "id"))
            continue
        materials[material.id] = material
    return list(materials.values()), capped(issues)
