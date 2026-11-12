# SPDX-License-Identifier: LGPL-2.1-or-later
"""Choix du format du CSV de la liste de débit dans la boîte d'enregistrement (issue #223)."""

from __future__ import annotations

from collections.abc import Iterator
from types import ModuleType

import pytest

from freecad.menuiserie.core.cutlist import FRENCH_CSV, INTERNATIONAL_CSV
from tests.unit.aides_freecad import simulated_freecad

FRENCH = "french"
INTERNATIONAL = "international"


@pytest.fixture
def module(monkeypatch: pytest.MonkeyPatch) -> Iterator[ModuleType]:
    with simulated_freecad(monkeypatch):
        from freecad.menuiserie.features import csv_format

        yield csv_format


@pytest.mark.parametrize("language", ["Français", "French", "fr", "fr-FR", " français "])
def test_francais_par_defaut_quand_freecad_est_en_francais(
    module: ModuleType, language: str
) -> None:
    assert module.initial_format("", language) == FRENCH


@pytest.mark.parametrize("language", ["English", "Deutsch", "", "en"])
def test_international_par_defaut_sinon(module: ModuleType, language: str) -> None:
    assert module.initial_format("", language) == INTERNATIONAL


@pytest.mark.parametrize("remembered", [FRENCH, INTERNATIONAL])
def test_le_dernier_choix_prime_sur_la_langue(module: ModuleType, remembered: str) -> None:
    assert module.initial_format(remembered, "Français") == remembered
    assert module.initial_format(remembered, "English") == remembered


def test_choix_memorise_inconnu_ignore(module: ModuleType) -> None:
    assert module.initial_format("autre", "Français") == FRENCH


def test_dialectes(module: ModuleType) -> None:
    assert module.dialect_of(FRENCH) is FRENCH_CSV
    assert module.dialect_of(INTERNATIONAL) is INTERNATIONAL_CSV
    assert module.dialect_of("inconnu") is INTERNATIONAL_CSV


def test_filtres_distincts_pour_le_csv(module: ModuleType) -> None:
    assert set(module.FILTERS) == {FRENCH, INTERNATIONAL}
    assert len(set(module.FILTERS.values())) == 2
    assert all("*.csv" in text for text in module.FILTERS.values())
