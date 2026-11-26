# SPDX-License-Identifier: LGPL-2.1-or-later
"""Entraxe maximal des tourillons, faux tenons et lamellos à la place du nombre (ADR 0070)."""

from __future__ import annotations

import ast
import importlib
from collections.abc import Iterator
from dataclasses import fields
from pathlib import Path
from typing import Any

import pytest

from freecad.menuiserie.core.geometry import PlacedBlock
from freecad.menuiserie.core.joints import JointKind
from freecad.menuiserie.core.joints.dowels import (
    MAX_DOWEL_COUNT,
    MAX_SPACING_MM,
    DowelParams,
    DowelStrategy,
    DowelValues,
    auto_count,
)
from freecad.menuiserie.core.joints.slots import SlotParams, SlotValues
from freecad.menuiserie.core.joints.slots._params import AUTO_SPACING_MM
from freecad.menuiserie.core.joints.slots._strategy import LooseTenonStrategy
from tests.unit.aides_assemblages import block
from tests.unit.aides_reglages import settings_module
from tests.unit.test_panneau_assemblage import FEATURES, property_specs

DOWELS = DowelStrategy()
TENON = LooseTenonStrategy()


def boards(length: float = 300.0) -> tuple[PlacedBlock, PlacedBlock]:
    size = (length, 100.0, 22.0)
    return block(size), block(size, (0.0, 100.0, 0.0))


@pytest.fixture
def config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[Any]:
    with settings_module(monkeypatch, tmp_path) as module:
        yield module


# --- noyau -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("max_spacing", "count"),
    [(0.0, 4), (MAX_SPACING_MM, 4), (200.0, 3), (100.0, 4), (50.0, 7), (10.0, 28), (1000.0, 2)],
)
def test_nombre_de_tourillons_selon_l_entraxe(max_spacing: float, count: int) -> None:
    """Contact de 300 mm, bord de 16 mm, tourillons de 8 mm : 0 donne l'entraxe historique."""
    assert auto_count(300, 16, 8, max_spacing) == count


def test_entraxe_nul_est_l_entraxe_historique() -> None:
    assert auto_count(300, 16, 8) == auto_count(300, 16, 8, MAX_SPACING_MM)
    assert (
        TENON.resolve(*boards(600.0), SlotParams()).count
        == TENON.resolve(*boards(600.0), SlotParams(max_spacing=AUTO_SPACING_MM)).count
    )


@pytest.mark.parametrize(
    ("max_spacing", "count"), [(0.0, 3), (AUTO_SPACING_MM, 3), (100.0, 3), (60.0, 5), (1000.0, 2)]
)
def test_nombre_de_mortaises_selon_l_entraxe(max_spacing: float, count: int) -> None:
    values = TENON.resolve(*boards(), SlotParams(max_spacing=max_spacing))
    assert values.count == count


def test_nombre_borne_et_ecart_respecte() -> None:
    assert auto_count(20_000, 20, 10, 10) == MAX_DOWEL_COUNT
    values = DOWELS.resolve(*boards(), DowelParams(max_spacing=100.0))
    assert isinstance(values, DowelValues)
    assert values.count == len(values.positions) == 4
    assert values.spacing <= 100.0
    assert values.spacing == pytest.approx(values.positions[1] - values.positions[0])


def test_un_seul_tourillon_n_a_pas_d_entraxe() -> None:
    values = DOWELS.resolve(*boards(length=30.0), DowelParams(max_spacing=50.0))
    assert (values.count, values.spacing) == (1, 0.0)


def test_entraxe_des_mortaises() -> None:
    values = TENON.resolve(*boards(), SlotParams(max_spacing=60.0))
    assert isinstance(values, SlotValues)
    assert values.count == 5
    assert 0 < values.spacing <= 60.0
    assert TENON.resolve(*boards(), SlotParams()).count == 3


def test_petit_entraxe_de_tourillons_jamais_refuse() -> None:
    """Un entraxe de 10 mm ne fait jamais refuser : le nombre est réduit pour garder la place."""
    values = DOWELS.resolve(*boards(), DowelParams(max_spacing=10.0))
    assert values.spacing > values.diameter


def test_entraxe_trop_petit_pour_les_mortaises_reduit_le_nombre() -> None:
    """Comme les tourillons : le nombre est réduit pour que les mortaises restent séparées."""
    params = SlotParams(custom_size=True, thickness=6, along=20, total_depth=40, max_spacing=10)
    values = TENON.resolve(*boards(), params)
    gaps = [b - a for a, b in zip(values.positions, values.positions[1:], strict=False)]
    assert all(gap > values.along for gap in gaps)


@pytest.mark.parametrize("params_type", [DowelParams, SlotParams])
@pytest.mark.parametrize("value", [0, 10, 128, 1000])
def test_entraxe_accepte(params_type: type, value: float) -> None:
    assert params_type(max_spacing=value).max_spacing == value


@pytest.mark.parametrize("params_type", [DowelParams, SlotParams])
@pytest.mark.parametrize("value", [-1, 5, 9.99, 1000.01, float("nan"), True, "x"])
def test_entraxe_refuse(params_type: type, value: object) -> None:
    with pytest.raises(ValueError, match="invalide : max_spacing"):
        params_type(max_spacing=value)


@pytest.mark.parametrize("params_type", [DowelParams, SlotParams])
def test_le_nombre_n_est_plus_un_parametre(params_type: type) -> None:
    assert "count" not in {item.name for item in fields(params_type)}
    with pytest.raises(TypeError):
        params_type(count=3)


# --- assemblages et formulaires ----------------------------------------------------------


@pytest.mark.parametrize("module", ["dowels.py", "slots.py"])
def test_propriete_entraxe_sans_nombre(module: str) -> None:
    names = {ast.literal_eval(spec["name"]) for spec in property_specs(FEATURES / module)}
    assert "Count" not in names
    assert "MaxSpacing" in names
    for spec in property_specs(FEATURES / module):
        if ast.literal_eval(spec["name"]) == "MaxSpacing":
            assert getattr(spec["type_id"], "id", "") == "LENGTH"  # longueur en mm
            label, tooltip = spec["label"], spec["tooltip"]
            assert isinstance(label, ast.Call) and isinstance(tooltip, ast.Call)
            assert ast.literal_eval(label.args[1]) == "Entraxe maximal"
            assert "resolved" not in spec  # pas de case « Auto » : 0 reste l'entraxe habituel
            assert "mm" in ast.literal_eval(tooltip.args[1])  # l'infobulle donne l'unité


def test_ancien_nombre_supprime_a_la_reouverture() -> None:
    for module in ("dowels.py", "slots.py"):
        text = (FEATURES / module).read_text(encoding="utf-8")
        assert 'OBSOLETE_PROPERTIES: ClassVar[tuple[str, ...]] = ("Count",)' in text
        assert "VERSION: ClassVar[int] = 2" in text


# --- réglages ----------------------------------------------------------------------------


def test_reglage_entraxe_des_lamellos_au_catalogue(config: Any) -> None:
    setting = config.CATALOG.get(config.SLOT_SPACING)
    assert (setting.key, setting.default) == ("SlotMaxSpacing", AUTO_SPACING_MM)
    assert (setting.minimum, setting.maximum) == (10.0, 1000.0)
    assert setting.group == config.JOINTS and setting.remember_last
    assert config.CATALOG.get(config.DOWEL_SPACING).default == MAX_SPACING_MM


def test_entraxe_ecrit_a_la_creation_depuis_le_reglage(config: Any) -> None:
    joint = importlib.import_module("freecad.menuiserie.features.joint_settings")
    values = config.settings()
    assert joint.apply_joint_settings(JointKind.DOWELS, {})["max_spacing"] == 128.0
    values.set(config.DOWEL_SPACING, 90.0)
    values.set(config.SLOT_SPACING, 120.0)
    assert joint.apply_joint_settings(JointKind.DOWELS, {})["max_spacing"] == 90.0
    assert joint.apply_joint_settings(JointKind.LOOSE_TENON, {})["max_spacing"] == 120.0
    assert joint.apply_joint_settings(JointKind.BISCUIT, {})["max_spacing"] == 120.0
    given = {"max_spacing": 60.0}  # l'appelant l'emporte
    assert joint.apply_joint_settings(JointKind.DOWELS, given) == given


def test_nombre_inchange_quand_le_reglage_change_apres_coup(config: Any) -> None:
    """Le recalcul ne lit que la propriété : le nombre d'un assemblage créé ne bouge pas."""
    joint = importlib.import_module("freecad.menuiserie.features.joint_settings")
    values = config.settings()
    values.set(config.DOWEL_SPACING, 100.0)
    created = DowelParams(**joint.apply_joint_settings(JointKind.DOWELS, {}))
    before = DOWELS.resolve(*boards(), created).count
    values.set(config.DOWEL_SPACING, 1000.0)
    assert DOWELS.resolve(*boards(), created).count == before == 4
    later = DowelParams(**joint.apply_joint_settings(JointKind.DOWELS, {}))
    assert DOWELS.resolve(*boards(), later).count == 2  # seuls les nouveaux assemblages changent
