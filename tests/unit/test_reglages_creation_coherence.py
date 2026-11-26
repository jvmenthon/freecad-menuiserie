# SPDX-License-Identifier: LGPL-2.1-or-later
"""Cohérence entre les réglages de l'atelier et le noyau (``core``) : un réglage que la page
accepte ne doit jamais faire échouer une création (ADR 0031, 0069), et « Dernier utilisé » ne
retient que ce que le catalogue accepte."""

from __future__ import annotations

import dataclasses
import importlib
import pkgutil
import types
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from freecad.menuiserie.core.edges import EdgeFamily
from freecad.menuiserie.core.part_model import Allowances, Dimensions
from tests.unit.aides import ROOT
from tests.unit.aides_reglages import settings_module

PACKAGE = ROOT / "freecad" / "menuiserie"


@pytest.fixture
def config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[Any]:
    with settings_module(monkeypatch, tmp_path) as module:
        yield module


def quantity(value: float) -> Any:
    return types.SimpleNamespace(Value=value)


def _joint_classes() -> dict[Any, Any]:
    package = importlib.import_module("freecad.menuiserie.features.joints")
    for info in pkgutil.iter_modules(package.__path__):
        importlib.import_module(f"{package.__name__}.{info.name}")
    base = importlib.import_module("freecad.menuiserie.features.joints.base").JointFeature
    found: dict[Any, Any] = {}
    todo = list(base.__subclasses__())
    while todo:
        cls = todo.pop()
        todo.extend(cls.__subclasses__())
        if "KIND" in vars(cls):
            found[cls.KIND] = cls
    return found


def _all_parameters(joint_settings: Any) -> dict[Any, dict[str, str]]:
    """Paramètres réglés (``_PARAMETERS``) et copiés à la création (``_COPIED``) par type."""
    merged: dict[Any, dict[str, str]] = {}
    for table in (joint_settings._PARAMETERS, joint_settings._COPIED):
        for kind, names in table.items():
            merged.setdefault(kind, {}).update(names)
    return merged


def test_parametres_de_la_table_existent_dans_le_noyau_et_l_assemblage(config: Any) -> None:
    """Chaque (type, paramètre) de la table est un champ de ``PARAMS`` et une propriété de
    l'assemblage, de même défaut que le réglage (``None`` : automatique, accepté)."""
    joint_settings = importlib.import_module("freecad.menuiserie.features.joint_settings")
    classes = _joint_classes()
    for kind, names in _all_parameters(joint_settings).items():
        cls = classes[kind]
        fields = {item.name: item for item in dataclasses.fields(cls.PARAMS)}
        properties = {spec.name for spec in cls.PROPERTIES}
        for name, key in names.items():
            assert name in fields, (kind, name)
            assert joint_settings.property_name(name) in properties, (kind, name)
            core_default = fields[name].default
            setting = config.CATALOG.get(key)
            automatic = name in ("angle", "max_spacing")  # 0 : angle ou entraxe habituel
            if not automatic and core_default not in (dataclasses.MISSING, None):
                assert setting.default == core_default, (kind, name, setting.default, core_default)


def test_bornes_des_reglages_d_assemblage_acceptees_par_le_noyau(config: Any) -> None:
    """Valeurs extrêmes permises par la page : le noyau ne doit pas les refuser à la création."""
    joint_settings = importlib.import_module("freecad.menuiserie.features.joint_settings")
    classes = _joint_classes()
    for kind, names in _all_parameters(joint_settings).items():
        for name, key in names.items():
            setting = config.CATALOG.get(key)
            for value in (setting.minimum, setting.maximum):
                if value is None:
                    continue
                try:
                    classes[kind].PARAMS(**{name: value})
                except (ValueError, TypeError) as error:
                    pytest.fail(f"{kind.name}.{name}={value} permis par la page, refusé : {error}")


def test_bornes_des_cotes_et_surcotes_acceptees_par_le_noyau(config: Any) -> None:
    for key in (config.LENGTH, config.WIDTH, config.THICKNESS):
        setting = config.CATALOG.get(key)
        for value in (setting.minimum, setting.maximum):
            args = {config.LENGTH: 0, config.WIDTH: 1, config.THICKNESS: 2}[key]
            cotes = [100.0, 100.0, 20.0]
            cotes[args] = value
            Dimensions(*cotes)
    for key in (*config.SOLID_ALLOWANCES, *config.PANEL_ALLOWANCES):
        setting = config.CATALOG.get(key)
        for value in (setting.minimum, setting.maximum):
            Allowances(value, value, value)


def test_bornes_des_cotes_de_profil_acceptees_par_le_noyau(config: Any) -> None:
    """Arête cassée (quart de rond) et cote proposée à la finition : la cote minimale permise
    par la page est au moins celle qu'accepte le noyau, et la maximale ne le fait pas échouer."""
    cut = importlib.import_module("freecad.menuiserie.core.edges._cut")
    for key in (config.BROKEN_EDGE_SIZE, config.EDGE_PROFILE_SIZE):
        setting = config.CATALOG.get(key)
        assert setting.minimum is not None and setting.minimum >= cut.MIN_SIZE_MM, key
        for value in (setting.minimum, setting.maximum):
            assert cut.resolved_sizes(EdgeFamily.ROUND, value, 0.0, "x") == (value, value)


def test_record_used_refuse_une_valeur_hors_bornes(config: Any) -> None:
    values = config.settings()
    values.set_remember_last(config.BROKEN_EDGE_SIZE, True)
    assert values.record_used(config.BROKEN_EDGE_SIZE, 2.0)
    for bad in (0.0, -1.0, 1.0e9, float("nan"), "x", None):
        assert not values.record_used(config.BROKEN_EDGE_SIZE, bad), bad
    assert values.value(config.BROKEN_EDGE_SIZE) == 2.0


def test_arete_cassee_taille_decochee_ignoree(config: Any) -> None:
    new_part = importlib.import_module("freecad.menuiserie.features.new_part_settings")
    config.settings().set(config.BROKEN_EDGE_SIZE, 3.0)
    assert new_part.broken_edge_size() is None  # case décochée : pas d'arête
    assert EdgeFamily.ROUND.value == "Round"
