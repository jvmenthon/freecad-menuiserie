# SPDX-License-Identifier: LGPL-2.1-or-later
"""Cache borné en entrées et en octets vivants (audit de sécurité J1d, point 3 : mémoire des
textures)."""

from __future__ import annotations

import gc

import pytest

from freecad.menuiserie.core.budget_cache import BudgetedCache, Decoded

Cache = BudgetedCache[str, str]


def decoded(name: str, nbytes: int = 10) -> Decoded[str]:
    return Decoded(name, nbytes)


def test_valeur_retenue_et_retrouvee() -> None:
    cache: Cache = BudgetedCache(max_entries=2, max_bytes=100)
    value = decoded("a")
    cache.remember("a", value)
    assert "a" in cache
    assert cache.get("a") is value
    assert cache.bytes_alive == 10


def test_refus_memorise_sans_octets() -> None:
    cache: Cache = BudgetedCache(max_entries=2, max_bytes=100)
    cache.remember("a", None)
    assert "a" in cache
    assert cache.get("a") is None
    assert cache.bytes_alive == 0


def test_cle_inconnue() -> None:
    cache: Cache = BudgetedCache(max_entries=2, max_bytes=100)
    assert "a" not in cache
    with pytest.raises(KeyError):
        cache.get("a")


def test_plus_anciennes_entrees_oubliees() -> None:
    cache: Cache = BudgetedCache(max_entries=2, max_bytes=100)
    cache.remember("a", None)
    cache.remember("b", None)
    cache.get("a")  # « a » devient la plus récente
    cache.remember("c", None)
    assert ("a" in cache, "b" in cache, "c" in cache) == (True, False, True)


def test_valeur_oubliee_mais_gardee_reste_comptee_et_partagee() -> None:
    """Une valeur affichée par une pièce, oubliée par le cache, compte toujours dans le budget et
    est retrouvée par sa clé : pas de seconde copie."""
    cache: Cache = BudgetedCache(max_entries=1, max_bytes=100)
    shown, other = decoded("a", 60), decoded("b", 30)
    cache.remember("a", shown)
    cache.remember("b", other)
    assert cache.bytes_alive == 90
    assert "a" in cache
    assert cache.get("a") is shown
    assert not cache.reserve(20)  # « b », oubliée à son tour, reste gardée par ``other``


def test_valeur_liberee_sort_du_budget() -> None:
    cache: Cache = BudgetedCache(max_entries=1, max_bytes=100)
    cache.remember("a", decoded("a", 60))
    cache.remember("b", None)  # « a » n'est plus gardée par personne
    gc.collect()
    assert "a" not in cache
    assert cache.bytes_alive == 0


def test_reserve_oublie_les_plus_anciennes_valeurs() -> None:
    cache: Cache = BudgetedCache(max_entries=10, max_bytes=100)
    cache.remember("a", decoded("a", 40))
    cache.remember("refus", None)
    cache.remember("b", decoded("b", 40))
    assert cache.reserve(50)
    assert ("a" in cache, "refus" in cache, "b" in cache) == (False, True, True)
    assert cache.bytes_alive == 40


def test_reserve_refusee_si_les_valeurs_sont_gardees() -> None:
    cache: Cache = BudgetedCache(max_entries=10, max_bytes=100)
    kept = [decoded("a", 40), decoded("b", 40)]
    for value in kept:
        cache.remember(value.value, value)
    assert not cache.reserve(30)
    assert cache.bytes_alive == 80
    assert cache.reserve(20)


def test_valeur_plus_grosse_que_le_budget() -> None:
    cache: Cache = BudgetedCache(max_entries=10, max_bytes=100)
    cache.remember("a", decoded("a", 10))
    assert not cache.reserve(101)
    assert "a" in cache  # rien n'a été oublié pour rien


def test_vider_garde_les_valeurs_affichees() -> None:
    cache: Cache = BudgetedCache(max_entries=10, max_bytes=100)
    shown = decoded("a", 70)
    cache.remember("a", shown)
    cache.clear()
    assert cache.bytes_alive == 70
    assert cache.get("a") is shown
