# SPDX-License-Identifier: LGPL-2.1-or-later
"""Export et import des réglages d'un catalogue, en JSON versionné (ADR 0069).

Python pur : ni FreeCAD ni Qt. Le fichier est ``{"format": 1, "settings": {clé: valeur},
<section>: {…}}``. Les sections supplémentaires (par exemple « dimensions ») sont opaques pour
ce module : l'appelant fournit le validateur de chacune. La lecture est stricte (taille bornée,
JSON strict, valeurs bornées par le catalogue) ; un fichier invalide est refusé en entier par
:class:`ExchangeError`, dont la raison codée (:class:`ExchangeReason`) est traduite par l'atelier.
Une clé inconnue est ignorée et signalée dans :attr:`ImportResult.ignored`.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Final

from .catalog import REMEMBER_SUFFIX, Catalog, Reason, SettingError, Value
from .folder import write_text_atomic
from .store import Settings

__all__ = [
    "FORMAT_VERSION",
    "MAX_FILE_BYTES",
    "Change",
    "ExchangeError",
    "ExchangeReason",
    "ImportResult",
    "SectionValidator",
    "apply",
    "export_payload",
    "preview",
    "read_import",
    "write_export",
]

FORMAT_VERSION: Final = 1
MAX_FILE_BYTES: Final = 65_536  # 64 Kio
_SETTINGS: Final = "settings"

SectionValidator = Callable[[dict[str, Any]], object]


class ExchangeReason(str, Enum):
    """Raison du refus d'un fichier, que l'atelier traduit."""

    UNREADABLE = "unreadable"
    NOT_WRITTEN = "not_written"
    TOO_LARGE = "too_large"
    NOT_JSON = "not_json"
    NOT_STRICT = "not_strict"
    DUPLICATE_KEY = "duplicate_key"
    NOT_AN_OBJECT = "not_an_object"
    BAD_FORMAT = "bad_format"
    NEWER_FORMAT = "newer_format"
    INVALID_SETTING = "invalid_setting"
    INVALID_SECTION = "invalid_section"


class ExchangeError(ValueError):
    """Fichier refusé en entier. ``detail`` précise l'élément en cause (clé, section, message
    technique) ; ``cause`` est le refus du catalogue quand une valeur est en cause."""

    def __init__(
        self, reason: ExchangeReason, detail: str = "", cause: SettingError | None = None
    ) -> None:
        super().__init__(f"{reason.value}: {detail}" if detail else reason.value)
        self.reason = reason
        self.detail = detail
        self.cause = cause


@dataclass(frozen=True)
class Change:
    """Un réglage qu'un import modifierait : ``old`` et ``new`` sont des valeurs lisibles."""

    key: str
    old: Value
    new: Value


@dataclass(frozen=True)
class ImportResult:
    """Contenu validé d'un fichier : valeurs des réglages (cases « Dernier utilisé » comprises,
    sous ``<clé>RememberLast``), sections validées et éléments ignorés (clés inconnues)."""

    values: Mapping[str, Value] = field(default_factory=dict)
    sections: Mapping[str, object] = field(default_factory=dict)
    ignored: tuple[str, ...] = ()


def export_payload(
    catalog: Catalog, settings: Settings, sections: Mapping[str, object] | None = None
) -> dict[str, object]:
    """Document à écrire : valeurs en vigueur de tout le catalogue, cases « Dernier utilisé »
    des réglages qui le permettent, puis les ``sections`` données (déjà sérialisables)."""
    values: dict[str, Value] = {}
    for setting in catalog:
        values[setting.key] = settings.value(setting.key)
        if setting.remember_last:
            values[setting.key + REMEMBER_SUFFIX] = settings.remembers_last(setting.key)
    return {"format": FORMAT_VERSION, _SETTINGS: values, **(sections or {})}


def write_export(path: Path, payload: Mapping[str, object]) -> None:
    """Écrit ``payload`` en JSON indenté (UTF-8) de façon atomique ; :class:`ExchangeError`
    (``NOT_WRITTEN``) si l'écriture échoue, ``ValueError`` si le document n'est pas
    sérialisable."""
    text = json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    try:
        write_text_atomic(path, text, prefix=".atelier-")
    except OSError as error:
        raise ExchangeError(ExchangeReason.NOT_WRITTEN, str(error)) from None


def _refuse_constant(name: str) -> Any:
    raise ExchangeError(ExchangeReason.NOT_STRICT, name)


def _no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ExchangeError(ExchangeReason.DUPLICATE_KEY, key)
        result[key] = value
    return result


def _load(path: Path) -> dict[str, Any]:
    """Objet JSON racine du fichier, taille et syntaxe vérifiées, ``format`` compris."""
    try:
        with path.open("rb") as handle:
            data = handle.read(MAX_FILE_BYTES + 1)
    except OSError as error:
        raise ExchangeError(ExchangeReason.UNREADABLE, str(error)) from None
    if len(data) > MAX_FILE_BYTES:
        raise ExchangeError(ExchangeReason.TOO_LARGE, str(MAX_FILE_BYTES))
    try:
        document = json.loads(
            data.decode("utf-8"),
            parse_constant=_refuse_constant,
            object_pairs_hook=_no_duplicates,
        )
    except ExchangeError:
        raise
    except (ValueError, RecursionError) as error:  # JSON, UTF-8 ou entier démesuré
        raise ExchangeError(ExchangeReason.NOT_JSON, type(error).__name__) from None
    if not isinstance(document, dict):
        raise ExchangeError(ExchangeReason.NOT_AN_OBJECT, "")
    version = document.get("format")
    if isinstance(version, bool) or not isinstance(version, int):
        raise ExchangeError(ExchangeReason.BAD_FORMAT, "format")
    if version > FORMAT_VERSION:
        raise ExchangeError(ExchangeReason.NEWER_FORMAT, str(version))
    if version != FORMAT_VERSION:
        raise ExchangeError(ExchangeReason.BAD_FORMAT, str(version))
    return document


def _check_setting(catalog: Catalog, key: str, raw: object) -> Value | None:
    """Valeur validée de ``key`` ; ``None`` si la clé est inconnue ; refus du fichier sinon."""
    base = key.removesuffix(REMEMBER_SUFFIX)
    try:
        if key != base and base in catalog and catalog.get(base).remember_last:
            if not isinstance(raw, bool):
                raise SettingError(key, Reason.WRONG_TYPE)
            return raw
        if key in catalog:
            return catalog.get(key).check(raw)
    except SettingError as error:
        raise ExchangeError(ExchangeReason.INVALID_SETTING, key, error) from None
    return None


def _validated_settings(catalog: Catalog, raw: object) -> tuple[dict[str, Value], tuple[str, ...]]:
    if not isinstance(raw, dict):
        raise ExchangeError(ExchangeReason.NOT_AN_OBJECT, _SETTINGS)
    values: dict[str, Value] = {}
    ignored: list[str] = []
    for key, item in raw.items():
        value = _check_setting(catalog, key, item)
        if value is None:
            ignored.append(key)
        else:
            values[key] = value
    return values, tuple(ignored)


def _validated_section(name: str, raw: object, validator: SectionValidator) -> object:
    if not isinstance(raw, dict):
        raise ExchangeError(ExchangeReason.NOT_AN_OBJECT, name)
    try:
        return validator(raw)
    except ValueError as error:
        raise ExchangeError(ExchangeReason.INVALID_SECTION, f"{name}: {error}") from None


def read_import(
    path: Path, catalog: Catalog, sections: Mapping[str, SectionValidator] | None = None
) -> ImportResult:
    """Lit et valide ``path`` ; :class:`ExchangeError` si le fichier est refusé. ``sections``
    associe le nom de chaque section attendue à son validateur (dict JSON → valeur validée, ou
    ``ValueError``). Une section absente est permise ; une section inconnue est ignorée."""
    document = _load(path)
    values, ignored = _validated_settings(catalog, document.get(_SETTINGS, {}))
    validated: dict[str, object] = {}
    for name, validator in (sections or {}).items():
        if name in document:
            validated[name] = _validated_section(name, document[name], validator)
    known = {"format", _SETTINGS, *(sections or {})}
    extra = tuple(key for key in document if key not in known)
    return ImportResult(values, validated, (*ignored, *extra))


def _current(settings: Settings, key: str) -> Value:
    if key.endswith(REMEMBER_SUFFIX):
        return settings.remembers_last(key.removesuffix(REMEMBER_SUFFIX))
    return settings.value(key)


def preview(catalog: Catalog, settings: Settings, result: ImportResult) -> list[Change]:
    """Changements que :func:`apply` ferait (ancienne et nouvelle valeur), seulement ceux qui
    diffèrent, dans l'ordre du catalogue."""
    changes: list[Change] = []
    for setting in catalog:
        for key in (setting.key, setting.key + REMEMBER_SUFFIX):
            if key not in result.values:
                continue
            old, new = _current(settings, key), result.values[key]
            if new != old:
                changes.append(Change(key, old, new))
    return changes


def apply(settings: Settings, result: ImportResult) -> None:
    """Écrit les valeurs de ``result`` dans ``settings`` (déjà validées). Les sections sont
    appliquées par l'appelant, qui décide quand."""
    for key, value in result.values.items():
        if key.endswith(REMEMBER_SUFFIX):
            settings.set_remember_last(key.removesuffix(REMEMBER_SUFFIX), bool(value))
        else:
            settings.set(key, value)
