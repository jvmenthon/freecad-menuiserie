# SPDX-License-Identifier: LGPL-2.1-or-later
"""Export et import de ``atelier.json`` par l'atelier : réglages et dimensions (ADR 0069)."""

from __future__ import annotations

import importlib
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from freecad.menuiserie.core.user_dimensions import UserDimensions
from freecad.menuiserie.kit.config.exchange import ExchangeError, ExchangeReason
from tests.unit.aides_reglages import settings_module


@pytest.fixture
def module(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[Any]:
    """``features.settings_exchange`` avec un FreeCAD simulé et un dossier d'atelier dans tmp."""
    with settings_module(monkeypatch, tmp_path) as base:
        base.settings().set(base.WORKSHOP_FOLDER, str(tmp_path / "atelier"))
        yield importlib.import_module("freecad.menuiserie.features.settings_exchange")


def _dimensions() -> Any:
    return importlib.import_module("freecad.menuiserie.features.user_dimensions")


def test_fichier_par_defaut_dans_le_dossier_de_l_atelier(module: Any, tmp_path: Path) -> None:
    assert module.workshop_file() == tmp_path / "atelier" / "atelier.json"


def test_aller_retour_reglages_et_dimensions(module: Any, tmp_path: Path) -> None:
    base = importlib.import_module("freecad.menuiserie.features.settings")
    base.settings().set(base.LENGTH, 1234.0)
    base.settings().set_remember_last(base.BROKEN_EDGE_SIZE, True)
    _dimensions().add_thickness(22.0)
    _dimensions().add_sheet(2800.0, 2070.0)
    path = tmp_path / "export.json"
    module.export_workshop(path)
    for key in (base.LENGTH, base.BROKEN_EDGE_SIZE):
        base.settings().reset(key)
    _dimensions().dimensions_path().unlink()
    result, changes = module.load_workshop(path)
    assert {change.key for change in changes} == {
        base.LENGTH,
        base.BROKEN_EDGE_SIZE + "RememberLast",
    }
    assert _dimensions().read_dimensions() == UserDimensions()  # le chargement n'écrit rien
    assert result.values[base.LENGTH] == 1234.0
    assert result.values[base.BROKEN_EDGE_SIZE + "RememberLast"] is True
    assert result.sections[module.DIMENSIONS] == UserDimensions((22.0,), ((2800.0, 2070.0),))


def test_import_sans_section_dimensions(module: Any, tmp_path: Path) -> None:
    path = tmp_path / "export.json"
    path.write_text('{"format": 1, "settings": {"NewPartLength": 900}}', encoding="utf-8")
    result, _ = module.load_workshop(path)
    assert module.DIMENSIONS not in result.sections


def test_export_avec_dimensions_illisibles_ecrit_une_section_vide(
    module: Any, tmp_path: Path
) -> None:
    """Un ``dimensions.json`` illisible est ignoré (avertissement dans la console) : l'export
    n'échoue pas et sa section « dimensions » est vide."""
    _dimensions().dimensions_path().parent.mkdir(parents=True, exist_ok=True)
    _dimensions().dimensions_path().write_text("{pas du json", encoding="utf-8")
    path = tmp_path / "export.json"
    module.export_workshop(path)
    document = json.loads(path.read_text(encoding="utf-8"))
    assert document[module.DIMENSIONS] == {"thicknesses": [], "sheets": []}


def test_message_de_refus_nettoie_le_detail(module: Any) -> None:
    detail = "x\u202e\n" + "y" * 500
    message = module.error_message(ExchangeError(ExchangeReason.NOT_JSON, detail))
    assert "\u202e" not in message
    assert "\n" not in message
    assert len(message) < 300


@pytest.mark.parametrize(
    "dimensions",
    [{"thicknesses": [0]}, {"thicknesses": "12"}, {"sheets": [[2000, 0]]}, {"sheets": [1]}],
)
def test_section_dimensions_invalide_refusee(
    module: Any, tmp_path: Path, dimensions: dict[str, Any]
) -> None:
    path = tmp_path / "export.json"
    path.write_text(json.dumps({"format": 1, "dimensions": dimensions}), encoding="utf-8")
    with pytest.raises(ExchangeError) as info:
        module.load_workshop(path)
    assert info.value.reason is ExchangeReason.INVALID_SECTION
    assert info.value.detail.startswith("dimensions")


def test_valeur_hors_bornes_refusee_et_rien_ecrit(module: Any, tmp_path: Path) -> None:
    base = importlib.import_module("freecad.menuiserie.features.settings")
    path = tmp_path / "export.json"
    path.write_text('{"format": 1, "settings": {"NewPartLength": 0}}', encoding="utf-8")
    with pytest.raises(ExchangeError) as info:
        module.load_workshop(path)
    assert info.value.reason is ExchangeReason.INVALID_SETTING
    assert module.error_message(info.value).endswith("« NewPartLength ».")
    assert not base.settings().is_modified(base.LENGTH)


def test_messages_pour_chaque_raison(module: Any) -> None:
    for reason in ExchangeReason:
        assert module.error_message(ExchangeError(reason, "x"))
