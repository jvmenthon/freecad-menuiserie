# SPDX-License-Identifier: LGPL-2.1-or-later
"""Cache des plans d'assemblage : clé exacte dans le repère local des deux pièces."""

from __future__ import annotations

import types
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import pytest

from freecad.menuiserie.core.geometry import PlacedBlock, RigidTransform, Vec3
from freecad.menuiserie.core.joints import JointError, JointPlan
from freecad.menuiserie.core.part_model import Dimensions
from tests.unit.aides_freecad import simulated_freecad

IDENTITY = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
TURNED = ((0.0, -1.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0))


@dataclass(frozen=True)
class Params:
    depth: float = 1.0


class FakeStrategy:
    kind = "fake"

    def __init__(self) -> None:
        self.calls = 0

    def plan(self, host: PlacedBlock, guest: PlacedBlock, params: Any) -> JointPlan:
        self.calls += 1
        if params.depth < 0:
            raise JointError("refus", {})
        return JointPlan()


def block(x: float = 0.0, rotation: Any = IDENTITY, length: float = 100.0) -> PlacedBlock:
    return PlacedBlock(Dimensions(length, 50.0, 18.0), RigidTransform(rotation, Vec3(x, 0, 0)))


@pytest.fixture(autouse=True)
def plan_cache(monkeypatch: pytest.MonkeyPatch) -> Iterator[types.ModuleType]:
    """``features.joints.plan_cache`` importé sur un FreeCAD simulé, cache vide."""
    with simulated_freecad(monkeypatch):
        from freecad.menuiserie.features.joints import plan_cache as module

        module.reset_plan_cache()
        yield module


def test_meme_entree_meme_plan_calcule_une_fois(plan_cache: types.ModuleType) -> None:
    strategy = FakeStrategy()
    first = plan_cache.cached_plan(strategy, block(0), block(10), Params())
    second = plan_cache.cached_plan(strategy, block(0), block(10), Params())
    assert first is second
    assert strategy.calls == 1


def test_translation_commune_meme_plan(plan_cache: types.ModuleType) -> None:
    strategy = FakeStrategy()
    plan_cache.cached_plan(strategy, block(0), block(10), Params())
    plan_cache.cached_plan(strategy, block(700), block(710), Params())
    assert strategy.calls == 1


@pytest.mark.parametrize(
    ("host", "guest", "params"),
    [
        (block(0, length=101.0), block(10), Params()),  # cote de l'hôte
        (block(0), block(10, length=101.0), Params()),  # cote de l'invitée
        (block(0), block(11), Params()),  # placement relatif
        (block(0, TURNED), block(10, TURNED), Params()),  # rotation de l'hôte (le bas)
        (block(0), block(10), Params(depth=2.0)),  # paramètres
    ],
)
def test_toute_difference_change_la_cle(
    plan_cache: types.ModuleType, host: PlacedBlock, guest: PlacedBlock, params: Any
) -> None:
    strategy = FakeStrategy()
    plan_cache.cached_plan(strategy, block(0), block(10), Params())
    plan_cache.cached_plan(strategy, host, guest, params)
    assert strategy.calls == 2


def test_echec_non_memorise(plan_cache: types.ModuleType) -> None:
    strategy = FakeStrategy()
    for _ in range(2):
        with pytest.raises(JointError):
            plan_cache.cached_plan(strategy, block(0), block(10), Params(depth=-1.0))
    assert strategy.calls == 2
    assert plan_cache.plan_cache_size() == 0


def test_cache_borne(plan_cache: types.ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(plan_cache, "MAX_ENTRIES", 2)
    strategy = FakeStrategy()
    for depth in (1.0, 2.0, 3.0):
        plan_cache.cached_plan(strategy, block(0), block(10), Params(depth=depth))
    assert plan_cache.plan_cache_size() == 2


def test_parametres_non_hachables_calcules_sans_cache(plan_cache: types.ModuleType) -> None:
    strategy = FakeStrategy()

    class Unhashable:
        depth = 1.0
        __hash__ = None  # type: ignore[assignment]

    for _ in range(2):
        plan_cache.cached_plan(strategy, block(0), block(10), Unhashable())
    assert strategy.calls == 2
