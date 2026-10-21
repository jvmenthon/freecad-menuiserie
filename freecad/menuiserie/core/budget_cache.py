# SPDX-License-Identifier: LGPL-2.1-or-later
"""Cache de valeurs décodées borné en nombre d'entrées **et** en octets vivants (ADR 0004).

Python pur, sans FreeCAD ni Qt ; utilisé par ``gui/textures.py`` pour les images de texture.

Les valeurs décodées sont enveloppées dans :class:`Decoded`, qui porte leur taille en octets.
Le cache retient au plus ``max_entries`` entrées (succès ou refus ``None``), les plus anciennes
oubliées ; mais une valeur oubliée par le cache peut rester en mémoire tant qu'un utilisateur
(une pièce affichée) la garde. Le budget compte donc toutes les valeurs **encore vivantes**,
suivies par références faibles : ``reserve`` oublie les plus anciennes entrées du cache tant
que la nouvelle valeur ne tient pas, puis répond si elle tient. Une valeur vivante oubliée est
retrouvée par sa clé (pas de seconde copie).
"""

from __future__ import annotations

import weakref
from collections import OrderedDict
from collections.abc import Hashable
from dataclasses import dataclass
from typing import Generic, TypeVar

__all__ = ["BudgetedCache", "Decoded"]

K = TypeVar("K", bound=Hashable)
V = TypeVar("V")


@dataclass(frozen=True, eq=False)
class Decoded(Generic[V]):
    """Valeur décodée et taille qu'elle occupe en mémoire (octets) ; comparée par identité."""

    value: V
    nbytes: int


class BudgetedCache(Generic[K, V]):
    """Entrées récentes (succès ou refus) et valeurs vivantes, bornées en nombre et en octets."""

    def __init__(self, max_entries: int, max_bytes: int) -> None:
        self.max_bytes = max_bytes
        self._max_entries = max_entries
        self._entries: OrderedDict[K, Decoded[V] | None] = OrderedDict()
        self._alive: weakref.WeakValueDictionary[K, Decoded[V]] = weakref.WeakValueDictionary()

    def __contains__(self, key: K) -> bool:
        """Vrai si ``key`` est retenue par le cache ou si sa valeur est encore vivante."""
        return key in self._entries or key in self._alive

    def get(self, key: K) -> Decoded[V] | None:
        """Entrée de ``key`` (``None`` : refus mémorisé), marquée la plus récente ; une valeur
        vivante oubliée par le cache y est remise. ``KeyError`` si ``key`` est inconnue."""
        if key in self._entries:
            self._entries.move_to_end(key)
            return self._entries[key]
        alive = self._alive[key]
        self.remember(key, alive)
        return alive

    def remember(self, key: K, value: Decoded[V] | None) -> None:
        """Retient ``value`` (ou le refus ``None``) ; les plus anciennes entrées sont oubliées
        au-delà de ``max_entries``."""
        self._entries[key] = value
        self._entries.move_to_end(key)
        if value is not None:
            self._alive[key] = value
        while len(self._entries) > self._max_entries:
            self._entries.popitem(last=False)

    @property
    def bytes_alive(self) -> int:
        """Octets des valeurs encore vivantes (retenues par le cache ou par un utilisateur)."""
        return sum(value.nbytes for value in self._alive.values())

    def reserve(self, nbytes: int) -> bool:
        """Vrai si ``nbytes`` octets de plus tiennent dans le budget, après avoir oublié au
        besoin les plus anciennes valeurs du cache (libérées si personne ne les garde)."""
        if nbytes > self.max_bytes:
            return False
        while self.bytes_alive + nbytes > self.max_bytes and self._forget_oldest_value():
            pass
        return self.bytes_alive + nbytes <= self.max_bytes

    def _forget_oldest_value(self) -> bool:
        """Oublie la plus ancienne entrée qui porte une valeur ; faux s'il n'y en a plus."""
        oldest = next((key for key, value in self._entries.items() if value is not None), None)
        if oldest is None:
            return False
        del self._entries[oldest]
        return True
