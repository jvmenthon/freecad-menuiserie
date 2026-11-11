# SPDX-License-Identifier: LGPL-2.1-or-later
"""Dernière forme affectée à un assemblage : réaffectée seulement si elle a changé."""

from __future__ import annotations

import types
from collections.abc import Iterator
from typing import Any

import pytest

from tests.unit.aides_freecad import simulated_freecad


class FakeShape:
    """Forme OCC simulée : ``partner`` désigne le solide sous-jacent partagé."""

    def __init__(self, solid: object | None) -> None:
        self.solid = solid

    def isNull(self) -> bool:
        return self.solid is None

    def isPartner(self, other: FakeShape) -> bool:
        return self.solid is other.solid


@pytest.fixture
def assigned(monkeypatch: pytest.MonkeyPatch) -> Iterator[types.ModuleType]:
    with simulated_freecad(monkeypatch):
        from freecad.menuiserie.features import assigned_shape

        yield assigned_shape


def holder(shape: FakeShape) -> Any:
    return types.SimpleNamespace(Shape=shape)


def test_jamais_affectee_donc_a_affecter(assigned: types.ModuleType) -> None:
    memo = assigned.AssignedShape()
    assert not memo.is_current(holder(FakeShape(object())), ())


def test_meme_cle_meme_solide_pas_de_reaffectation(assigned: types.ModuleType) -> None:
    solid = object()
    memo = assigned.AssignedShape()
    memo.remember(("a",), FakeShape(solid))
    assert memo.is_current(holder(FakeShape(solid)), ("a",))


def test_cle_differente_a_reaffecter(assigned: types.ModuleType) -> None:
    solid = object()
    memo = assigned.AssignedShape()
    memo.remember(("a",), FakeShape(solid))
    assert not memo.is_current(holder(FakeShape(solid)), ("b",))


def test_forme_changee_depuis_a_reaffecter(assigned: types.ModuleType) -> None:
    """Annulation ou script : l'objet porte un autre solide que celui affecté en dernier."""
    memo = assigned.AssignedShape()
    memo.remember(("a",), FakeShape(object()))
    assert not memo.is_current(holder(FakeShape(object())), ("a",))


def test_formes_vides_identiques(assigned: types.ModuleType) -> None:
    memo = assigned.AssignedShape()
    memo.remember((), FakeShape(None))
    assert memo.is_current(holder(FakeShape(None)), ())
    assert not memo.is_current(holder(FakeShape(object())), ())


def test_cle_inconnue_toujours_a_affecter(assigned: types.ModuleType) -> None:
    solid = object()
    memo = assigned.AssignedShape()
    memo.remember(None, FakeShape(solid))
    assert not memo.is_current(holder(FakeShape(solid)), None)
