# SPDX-License-Identifier: LGPL-2.1-or-later
"""Lecture et écriture des réglages d'un catalogue, option « Dernier utilisé » (ADR 0069).

Python pur : le stockage est une interface (:class:`ParamStore`). :class:`FreeCADStore` reçoit la
fonction ``App.ParamGet`` de l'atelier, :class:`MemoryStore` sert aux tests et aux aperçus.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Final, Protocol

from .catalog import REMEMBER_SUFFIX, Catalog, Kind, SettingError, Value, coerce

__all__ = ["REMEMBER_SUFFIX", "FreeCADStore", "MemoryStore", "ParamStore", "Settings"]


@dataclass(frozen=True)
class _Backend:
    """Nature des paramètres FreeCAD d'un type de réglage et méthodes d'écriture et d'effacement."""

    type_name: str
    write: Callable[[Any, str, Value], None]
    remove: Callable[[Any, str], None]


def _set_bool(group: Any, key: str, value: Value) -> None:
    group.SetBool(key, value)


def _set_int(group: Any, key: str, value: Value) -> None:
    group.SetInt(key, value)


def _set_float(group: Any, key: str, value: Value) -> None:
    group.SetFloat(key, value)


def _set_string(group: Any, key: str, value: Value) -> None:
    group.SetString(key, value)


def _rem_bool(group: Any, key: str) -> None:
    group.RemBool(key)


def _rem_int(group: Any, key: str) -> None:
    group.RemInt(key)


def _rem_float(group: Any, key: str) -> None:
    group.RemFloat(key)


def _rem_string(group: Any, key: str) -> None:
    group.RemString(key)


_TEXT_BACKEND: Final = _Backend("String", _set_string, _rem_string)

# Type de réglage → stockage FreeCAD (table explicite, sans appel dynamique).
_STORAGE: Final[dict[Kind, _Backend]] = {
    Kind.BOOL: _Backend("Boolean", _set_bool, _rem_bool),
    Kind.INT: _Backend("Integer", _set_int, _rem_int),
    Kind.FLOAT: _Backend("Float", _set_float, _rem_float),
    Kind.TEXT: _TEXT_BACKEND,
    Kind.CHOICE: _TEXT_BACKEND,
    Kind.PATH: _TEXT_BACKEND,
}


class ParamStore(Protocol):
    """Stockage de valeurs typées par clé."""

    def read(self, key: str, kind: Kind) -> Value | None:
        """Valeur enregistrée, ``None`` si la clé est absente."""

    def write(self, key: str, kind: Kind, value: Value) -> None:
        """Enregistre ``value`` (déjà validée)."""

    def remove(self, key: str, kind: Kind) -> None:
        """Efface la clé (sans effet si elle est absente)."""


class MemoryStore:
    """Stockage en mémoire (tests, aperçu d'un import)."""

    def __init__(self) -> None:
        self.values: dict[tuple[str, str], Value] = {}

    def read(self, key: str, kind: Kind) -> Value | None:
        return self.values.get((_STORAGE[kind].type_name, key))

    def write(self, key: str, kind: Kind, value: Value) -> None:
        self.values[(_STORAGE[kind].type_name, key)] = value

    def remove(self, key: str, kind: Kind) -> None:
        self.values.pop((_STORAGE[kind].type_name, key), None)


class FreeCADStore:
    """Paramètres FreeCAD d'un groupe (``"User parameter:BaseApp/Preferences/Mod/…"``).

    ``param_get`` est ``FreeCAD.ParamGet`` : le module n'importe pas FreeCAD lui-même.
    """

    def __init__(self, param_get: Callable[[str], Any], path: str) -> None:
        self._param_get = param_get
        self._path = path

    def _group(self) -> Any:
        return self._param_get(self._path)

    def read(self, key: str, kind: Kind) -> Value | None:
        storage = _STORAGE[kind].type_name
        for entry in self._group().GetContents() or ():
            if entry[0] == storage and entry[1] == key:
                value: Value = entry[2]
                return value
        return None

    def write(self, key: str, kind: Kind, value: Value) -> None:
        _STORAGE[kind].write(self._group(), key, value)

    def remove(self, key: str, kind: Kind) -> None:
        _STORAGE[kind].remove(self._group(), key)


class Settings:
    """Réglages d'un catalogue lus et écrits dans un stockage, toujours bornés par le catalogue."""

    def __init__(self, catalog: Catalog, store: ParamStore) -> None:
        self.catalog = catalog
        self._store = store

    def value(self, key: str) -> Value:
        """Valeur en vigueur : celle du stockage si elle est valide, sinon la valeur par défaut."""
        setting = self.catalog.get(key)
        return coerce(setting, self._store.read(key, setting.kind))

    def set(self, key: str, value: object) -> Value:
        """Enregistre ``value`` après validation ; :class:`SettingError` si elle est refusée."""
        setting = self.catalog.get(key)
        checked = setting.check(value)
        self._store.write(key, setting.kind, checked)
        return checked

    def is_modified(self, key: str) -> bool:
        """Vrai si la valeur en vigueur diffère de la valeur par défaut."""
        return self.value(key) != self.catalog.get(key).default

    def reset(self, key: str) -> None:
        """Rétablit la valeur par défaut et décoche « Dernier utilisé »."""
        setting = self.catalog.get(key)
        self._store.remove(key, setting.kind)
        self._store.remove(_remember_key(key), Kind.BOOL)

    def reset_all(self) -> None:
        """Rétablit tout le catalogue."""
        for setting in self.catalog:
            self.reset(setting.key)

    def remembers_last(self, key: str) -> bool:
        """Vrai si la case « Dernier utilisé » du réglage est cochée."""
        setting = self.catalog.get(key)
        return setting.remember_last and self._store.read(_remember_key(key), Kind.BOOL) is True

    def set_remember_last(self, key: str, enabled: bool) -> None:
        """Coche ou décoche « Dernier utilisé » ; ``ValueError`` si le réglage ne le permet pas."""
        setting = self.catalog.get(key)
        if not setting.remember_last:
            raise ValueError(f"{key} : « Dernier utilisé » non prévu")
        self._store.write(_remember_key(key), Kind.BOOL, bool(enabled))

    def record_used(self, key: str, value: object) -> bool:
        """Valeur utilisée à une création : retenue si « Dernier utilisé » est coché et qu'elle
        est acceptée. Rend vrai si elle a été retenue ; une valeur refusée est ignorée."""
        if not self.remembers_last(key):
            return False
        try:
            self.set(key, value)
        except SettingError:
            return False
        return True


def _remember_key(key: str) -> str:
    return f"{key}{REMEMBER_SUFFIX}"
