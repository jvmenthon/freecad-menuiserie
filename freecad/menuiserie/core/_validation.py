# SPDX-License-Identifier: LGPL-2.1-or-later
"""Aides de validation partagées par ``core/materials/`` et ``core/part_model.py``.

Module privé : seuls ``core/`` et ses tests unitaires l'importent.
"""

from __future__ import annotations

import math
import unicodedata
from collections.abc import Iterator, Mapping
from typing import Final

MIN_DIMENSION_MM: Final = 0.1
MAX_DIMENSION_MM: Final = 20_000.0

# Contrôle, format (invisibles, bidi), demi-substituts, usage privé, non attribués, séparateurs
# de ligne et de paragraphe : refusés dans les libellés.
_FORBIDDEN_CATEGORIES: Final = frozenset({"Cc", "Cf", "Cs", "Co", "Cn", "Zl", "Zp"})


class FrozenMapping(Mapping[str, str]):
    """Dictionnaire de textes immuable et hachable (libellés, paramètres d'anomalie)."""

    __slots__ = ("_items",)

    def __init__(self, items: Mapping[str, str]) -> None:
        self._items: dict[str, str] = dict(items)

    def __getitem__(self, key: str) -> str:
        return self._items[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._items)

    def __len__(self) -> int:
        return len(self._items)

    def __hash__(self) -> int:
        return hash(frozenset(self._items.items()))

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self._items!r})"


def nfc(text: str) -> str:
    """Texte en forme normalisée NFC (« é » composé plutôt que « e » + accent combinant)."""
    return unicodedata.normalize("NFC", text)


def to_finite_float(value: object) -> float | None:
    """Nombre JSON fini (entier ou flottant, pas booléen) converti en flottant, sinon ``None``."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        number = float(value)
    except OverflowError:
        return None
    return number if math.isfinite(number) else None


def bounded_float(value: object, minimum: float, maximum: float) -> float | None:
    """Nombre fini (pas booléen) compris entre ``minimum`` et ``maximum``, sinon ``None``."""
    number = to_finite_float(value)
    if number is not None and minimum <= number <= maximum:
        return number
    return None


def decimal_text(number: float) -> str:
    """Nombre écrit à la française pour un message : « 0,1 », « 300 »."""
    return f"{number:g}".replace(".", ",")


def has_forbidden_character(text: str) -> bool:
    """Vrai si ``text`` contient un caractère d'une catégorie Unicode interdite."""
    return any(unicodedata.category(char) in _FORBIDDEN_CATEGORIES for char in text)
