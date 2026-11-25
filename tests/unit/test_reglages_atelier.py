# SPDX-License-Identifier: LGPL-2.1-or-later
"""Catalogue des réglages de l'atelier Menuiserie et dossier de l'atelier (ADR 0031, 0069)."""

from __future__ import annotations

import importlib
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from freecad.menuiserie.core.edges import BROKEN_EDGE_MM, EdgeFamily
from freecad.menuiserie.core.part_model import (
    DEFAULT_DIMENSIONS,
    DEFAULT_PANEL_ALLOWANCES,
    DEFAULT_SOLID_ALLOWANCES,
)
from freecad.menuiserie.kit.config.catalog import Kind
from tests.unit.aides_freecad import simulated_freecad
from tests.unit.aides_reglages import FakeParamGroup


@pytest.fixture
def module(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[Any]:
    """``features.settings`` importé avec un FreeCAD simulé : paramètres en mémoire, dossier de
    données utilisateur dans ``tmp_path``."""
    group = FakeParamGroup()
    with simulated_freecad(monkeypatch):
        settings: Any = importlib.import_module("freecad.menuiserie.features.settings")

        settings.App.ParamGet = lambda _path: group
        settings.App.getUserAppDataDir = lambda: str(tmp_path / "FreeCAD")
        settings.group = group  # pour les tests
        yield settings


def test_valeurs_par_defaut_celles_du_code(module: Any) -> None:
    values = module.settings()
    assert [values.value(k) for k in (module.LENGTH, module.WIDTH, module.THICKNESS)] == [
        DEFAULT_DIMENSIONS.length,
        DEFAULT_DIMENSIONS.width,
        DEFAULT_DIMENSIONS.thickness,
    ]
    solid = [values.value(k) for k in module.SOLID_ALLOWANCES]
    panel = [values.value(k) for k in module.PANEL_ALLOWANCES]
    assert solid == [DEFAULT_SOLID_ALLOWANCES.length, DEFAULT_SOLID_ALLOWANCES.width, 0.0]
    assert panel == [DEFAULT_PANEL_ALLOWANCES.length, 0.0, 0.0]
    assert values.value(module.BROKEN_EDGE) is False
    assert values.value(module.BROKEN_EDGE_SIZE) == BROKEN_EDGE_MM
    assert values.value(module.EDGE_PROFILE) == EdgeFamily.ROUND.value
    expected = {
        module.MORTISE_CLEARANCE: 2.0,
        module.MORTISE_THROUGH: False,
        module.GROOVE_CLEARANCE: 1.0,
        module.TONGUE_LENGTH: 10.0,
        module.GROOVE_THROUGH: True,
        module.RABBET_THROUGH: True,
        module.DOWEL_CLEARANCE: 1.0,
        module.DOWEL_SPACING: 128.0,
        module.DOVETAIL_ANGLE: 10.0,
        module.SLOT_FREE_SIZE: False,
    }
    assert {key: values.value(key) for key in expected} == expected


def test_dernier_utilise_sur_les_chants_et_les_assemblages(module: Any) -> None:
    """Choix de jv (2026-11-25) : chants et réglages principaux des assemblages."""
    remembered = {s.key for s in module.CATALOG if s.remember_last}
    edges = {
        module.BROKEN_EDGE,
        module.BROKEN_EDGE_SIZE,
        module.EDGE_PROFILE,
        module.EDGE_PROFILE_SIZE,
    }
    joints = {s.key for s in module.CATALOG if s.group == module.JOINTS}
    assert len(joints) == 10
    assert remembered == edges | joints


def test_groupes_et_textes(module: Any) -> None:
    assert module.CATALOG.groups() == (
        module.NEW_PARTS,
        module.EDGES,
        module.JOINTS,
        module.STORAGE,
    )
    for setting in module.CATALOG:
        assert setting.label
        assert setting.tooltip.endswith(".")
        assert setting.kind is not Kind.FLOAT or setting.unit


def test_dossier_de_l_atelier_par_defaut_puis_ancien_chemin_puis_reglage(
    module: Any, tmp_path: Path
) -> None:
    assert module.workshop_folder() == tmp_path / "FreeCAD" / "Menuiserie"
    legacy = tmp_path / "ancien" / "materiaux.json"
    module.group.SetString(module.USER_LIBRARY_PARAM, str(legacy))
    assert module.workshop_folder() == legacy.parent
    module.settings().set(module.WORKSHOP_FOLDER, str(tmp_path / "nuage"))
    assert module.workshop_folder() == tmp_path / "nuage"


def test_reglage_abime_ignore(module: Any) -> None:
    module.group.SetFloat(module.MORTISE_CLEARANCE, -3.0)
    module.group.SetString(module.EDGE_PROFILE, "Inconnu")
    values = module.settings()
    assert values.value(module.MORTISE_CLEARANCE) == 2.0
    assert values.value(module.EDGE_PROFILE) == EdgeFamily.ROUND.value


def test_fichiers_personnels_dans_le_dossier_de_l_atelier(module: Any, tmp_path: Path) -> None:
    """Dimensions et quincaillerie suivent le dossier de l'atelier ; sans réglage, rien ne bouge."""
    import freecad.menuiserie.features.hardware as hardware
    import freecad.menuiserie.features.library as library
    import freecad.menuiserie.features.user_dimensions as user_dimensions

    default = tmp_path / "FreeCAD" / "Menuiserie"
    assert library.user_library_path() == default / "materiaux.json"
    assert user_dimensions.dimensions_path() == default / "dimensions.json"
    assert hardware.user_catalog_path() == default / "quincaillerie.json"
    module.settings().set(module.WORKSHOP_FOLDER, str(tmp_path / "nuage"))
    assert user_dimensions.dimensions_path() == tmp_path / "nuage" / "dimensions.json"
    assert hardware.user_catalog_path() == tmp_path / "nuage" / "quincaillerie.json"
    assert library.user_library_path() == tmp_path / "nuage" / "materiaux.json"
    legacy = tmp_path / "ancien" / "perso.json"
    module.group.SetString(module.USER_LIBRARY_PARAM, str(legacy))
    assert library.user_library_path() == legacy  # l'ancien chemin reste prioritaire (ADR 0069)
    assert user_dimensions.dimensions_path() == tmp_path / "nuage" / "dimensions.json"
