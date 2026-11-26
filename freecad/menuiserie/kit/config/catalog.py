# SPDX-License-Identifier: LGPL-2.1-or-later
"""Catalogue de réglages : description, valeur par défaut et validation bornée (ADR 0069).

Python pur. Un réglage refusé lève :class:`SettingError` avec une raison codée (:class:`Reason`) ;
l'atelier qui utilise ce module en fait un message traduit.
"""

from __future__ import annotations

import math
import os
import re
import unicodedata
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from enum import Enum
from pathlib import PurePath
from typing import Final, TypeAlias

__all__ = [
    "MAX_TEXT_LENGTH",
    "REMEMBER_SUFFIX",
    "Catalog",
    "Kind",
    "Reason",
    "Setting",
    "SettingError",
    "Value",
    "coerce",
]

Value: TypeAlias = bool | int | float | str

MAX_TEXT_LENGTH: Final = 1024  # caractères d'un texte ou d'un chemin
REMEMBER_SUFFIX: Final = "RememberLast"  # clé de la case « Dernier utilisé » : <clé>RememberLast
_KEY_PATTERN: Final = re.compile(r"[A-Za-z][A-Za-z0-9]{0,63}")
# Contrôle, format, demi-substituts, usage privé, non attribués, séparateurs de ligne.
_FORBIDDEN_CATEGORIES: Final = frozenset({"Cc", "Cf", "Cs", "Co", "Cn", "Zl", "Zp"})


class Kind(str, Enum):
    """Nature d'un réglage, qui fixe sa validation et son stockage."""

    BOOL = "bool"
    INT = "int"
    FLOAT = "float"
    TEXT = "text"
    CHOICE = "choice"
    PATH = "path"


class Reason(str, Enum):
    """Raison d'un refus, que l'atelier traduit."""

    UNKNOWN_KEY = "unknown_key"
    WRONG_TYPE = "wrong_type"
    NOT_FINITE = "not_finite"
    BELOW_MINIMUM = "below_minimum"
    ABOVE_MAXIMUM = "above_maximum"
    NOT_A_CHOICE = "not_a_choice"
    TEXT_TOO_LONG = "text_too_long"
    FORBIDDEN_CHARACTER = "forbidden_character"
    NOT_ABSOLUTE = "not_absolute"


class SettingError(ValueError):
    """Valeur refusée pour le réglage ``key`` ; ``reason`` dit pourquoi, ``limit`` la borne."""

    def __init__(self, key: str, reason: Reason, limit: Value | None = None) -> None:
        super().__init__(f"{key}: {reason.value}" + ("" if limit is None else f" ({limit})"))
        self.key = key
        self.reason = reason
        self.limit = limit


@dataclass(frozen=True)
class Setting:
    """Un réglage : clé de stockage, nature, valeur par défaut, bornes et textes de la page.

    ``label``, ``tooltip``, ``unit`` et ``group`` sont des textes à traduire par l'atelier.
    ``advanced`` range le réglage dans « Afficher les réglages avancés » ; ``remember_last``
    autorise la case « Dernier utilisé ».
    """

    key: str
    kind: Kind
    default: Value
    label: str
    tooltip: str
    group: str
    unit: str = ""
    minimum: float | None = None
    maximum: float | None = None
    choices: tuple[str, ...] = ()
    advanced: bool = False
    remember_last: bool = False

    def __post_init__(self) -> None:
        if not _KEY_PATTERN.fullmatch(self.key):
            raise ValueError(f"clé de réglage invalide : {self.key!r}")
        if self.kind is Kind.CHOICE and not self.choices:
            raise ValueError(f"{self.key} : un choix sans valeurs possibles")
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValueError(f"{self.key} : minimum au-dessus du maximum")
        self.check(self.default)  # une valeur par défaut refusée est une erreur de catalogue

    def check(self, value: object) -> Value:
        """Valeur acceptée (un entier devient un réel pour ``FLOAT``), sinon
        :class:`SettingError`."""
        if self.kind is Kind.BOOL:
            if not isinstance(value, bool):
                raise SettingError(self.key, Reason.WRONG_TYPE)
            return value
        if self.kind in (Kind.INT, Kind.FLOAT):
            return self._check_number(value)
        return self._check_text(value)

    def _check_number(self, value: object) -> Value:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise SettingError(self.key, Reason.WRONG_TYPE)
        if self.kind is Kind.INT and not isinstance(value, int):
            raise SettingError(self.key, Reason.WRONG_TYPE)
        try:
            number: int | float = value if self.kind is Kind.INT else float(value)
        except OverflowError as error:  # entier hors de portée d'un réel
            reason = Reason.ABOVE_MAXIMUM if value > 0 else Reason.BELOW_MINIMUM
            limit = self.maximum if value > 0 else self.minimum
            raise SettingError(
                self.key, reason if limit is not None else Reason.NOT_FINITE, limit
            ) from error
        if not math.isfinite(number):
            raise SettingError(self.key, Reason.NOT_FINITE)
        if self.minimum is not None and number < self.minimum:
            raise SettingError(self.key, Reason.BELOW_MINIMUM, self.minimum)
        if self.maximum is not None and number > self.maximum:
            raise SettingError(self.key, Reason.ABOVE_MAXIMUM, self.maximum)
        return number

    def _check_text(self, value: object) -> Value:
        if not isinstance(value, str):
            raise SettingError(self.key, Reason.WRONG_TYPE)
        if self.kind is Kind.CHOICE:
            if value not in self.choices:
                raise SettingError(self.key, Reason.NOT_A_CHOICE)
            return value
        if len(value) > MAX_TEXT_LENGTH:
            raise SettingError(self.key, Reason.TEXT_TOO_LONG, MAX_TEXT_LENGTH)
        if any(unicodedata.category(char) in _FORBIDDEN_CATEGORIES for char in value):
            raise SettingError(self.key, Reason.FORBIDDEN_CHARACTER)
        if self.kind is Kind.PATH and value and not _is_absolute(value):
            raise SettingError(self.key, Reason.NOT_ABSOLUTE)
        return value


def _is_absolute(text: str) -> bool:
    """Vrai si le chemin est absolu ; « ~ » seul ou suivi d'un séparateur est le dossier de
    l'utilisateur (``~nom`` n'est pas développé : il interrogerait la base des comptes)."""
    if text == "~" or text.startswith(("~/", "~\\")):
        text = os.path.expanduser(text)
    return PurePath(text).is_absolute()


def coerce(setting: Setting, raw: object) -> Value:
    """Valeur lue dans un stockage : ``raw`` si elle est acceptée, sinon la valeur par défaut
    (valeur absente, abîmée ou hors des bornes d'une version plus récente du catalogue)."""
    if raw is None:
        return setting.default
    try:
        return setting.check(raw)
    except SettingError:
        return setting.default


class Catalog:
    """Ensemble ordonné de réglages, à clés uniques."""

    def __init__(self, settings: Iterable[Setting]) -> None:
        self._settings: dict[str, Setting] = {}
        for setting in settings:
            if setting.key in self._settings:
                raise ValueError(f"clé de réglage en double : {setting.key}")
            if setting.key.endswith(REMEMBER_SUFFIX):
                raise ValueError(f"clé réservée à « Dernier utilisé » : {setting.key}")
            self._settings[setting.key] = setting

    def __iter__(self) -> Iterator[Setting]:
        return iter(self._settings.values())

    def __len__(self) -> int:
        return len(self._settings)

    def __contains__(self, key: object) -> bool:
        return key in self._settings

    def get(self, key: str) -> Setting:
        """Réglage de clé ``key`` ; :class:`SettingError` (``UNKNOWN_KEY``) s'il n'existe pas."""
        try:
            return self._settings[key]
        except KeyError:
            raise SettingError(key, Reason.UNKNOWN_KEY) from None

    def groups(self) -> tuple[str, ...]:
        """Groupes dans l'ordre de leur premier réglage."""
        return tuple(dict.fromkeys(setting.group for setting in self))
