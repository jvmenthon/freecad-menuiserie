# SPDX-License-Identifier: LGPL-2.1-or-later
"""Revue testeur PR #281 : cas limites de l'échange et des réglages de taquets (ADR 0069)."""

from __future__ import annotations

import importlib
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from freecad.menuiserie.core.joints import MIN_WALL_MM
from freecad.menuiserie.core.joints.shelf_pins import AUTO_DIAMETER_MM
from freecad.menuiserie.kit.config.exchange import ExchangeError
from freecad.menuiserie.kit.config.import_model import MAX_NAMES_SHOWN, ignored_text
from tests.unit.aides_reglages import settings_module


@pytest.fixture
def base(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[Any]:
    with settings_module(monkeypatch, tmp_path) as module:
        module.settings().set(module.WORKSHOP_FOLDER, str(tmp_path / "atelier"))
        yield module


def test_pas_minimal_compatible_avec_le_diametre_automatique(base: Any) -> None:
    """Un pas accepté par la page doit pouvoir servir : le perçage refuse un pas inférieur à
    diamètre automatique + MIN_WALL_MM (PITCH_TOO_SMALL) et chaque création échouerait."""
    pitch = base.CATALOG.get(base.SHELF_PIN_PITCH)
    assert pitch.minimum is not None
    assert pitch.minimum >= AUTO_DIAMETER_MM + MIN_WALL_MM


def test_import_pas_et_diametre_incompatibles_refuse(base: Any, tmp_path: Path) -> None:
    """Pas 10 + diamètre 30 : chacun est dans ses bornes mais la paire est inutilisable."""
    exchange = importlib.import_module("freecad.menuiserie.features.settings_exchange")
    path = tmp_path / "x.json"
    path.write_text(
        json.dumps(
            {
                "format": 1,
                "settings": {base.SHELF_PIN_PITCH: 10.0, base.SHELF_PIN_DIAMETER: 30.0},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ExchangeError):
        exchange.load_workshop(path)


def test_bandeau_ignores_tronque_les_noms_longs() -> None:
    """Un fichier peut porter une clé de 60 000 caractères : le bandeau ne doit pas l'afficher
    en entier."""
    text = ignored_text(["x" * 60_000] * (MAX_NAMES_SHOWN - 1))
    assert len(text) < 2_000
