# SPDX-License-Identifier: LGPL-2.1-or-later
"""Parenté des conteneurs de deux pièces assemblées (issue #209, ADR 0054)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from tests.unit.aides_freecad import simulated_freecad


def part(parent: Any = None, type_id: str = "App::Part") -> Any:
    return SimpleNamespace(TypeId=type_id, getParentGeoFeatureGroup=lambda: parent)


def piece(holder: Any = None) -> Any:
    return SimpleNamespace(getParentGeoFeatureGroup=lambda: holder)


@pytest.mark.parametrize("case", ["same", "nested", "siblings", "roots", "free", "body", "sub"])
def test_parente(monkeypatch: pytest.MonkeyPatch, case: str) -> None:
    with simulated_freecad(monkeypatch):
        from freecad.menuiserie.features.joints.frames import frame_containers, related_containers

        root = part()
        child_a, child_b = part(root), part(root)
        other = part()
        body = part(type_id="PartDesign::Body")
        pairs = {
            "same": (piece(root), piece(root), True),
            "nested": (piece(root), piece(child_a), True),
            "siblings": (piece(child_a), piece(child_b), True),
            "roots": (piece(root), piece(other), True),
            "free": (piece(), piece(root), True),
            "body": (piece(body), piece(root), False),
            "sub": (piece(child_a), piece(child_a), True),
        }
        first, second, expected = pairs[case]
        assert related_containers(first, second) is expected
        if case == "same":
            assert frame_containers(first, second) == []
        if case == "siblings":
            assert len(frame_containers(first, second)) == 3


class Shift:
    """Placement simulé : une translation en x (assez pour ``inverse`` et ``*``)."""

    def __init__(self, x: float) -> None:
        self.x = x

    def inverse(self) -> Shift:
        return Shift(-self.x)

    def __mul__(self, other: Shift) -> Shift:
        return Shift(self.x + other.x)


def test_placement_dans_le_repere_de_l_hote(monkeypatch: pytest.MonkeyPatch) -> None:
    with simulated_freecad(monkeypatch):
        from freecad.menuiserie.features.joints.frames import placement_in_frame_of

        host_part = SimpleNamespace(getGlobalPlacement=lambda: Shift(100.0))
        host = SimpleNamespace(Placement=Shift(5.0), getParentGeoFeatureGroup=lambda: host_part)
        guest = SimpleNamespace(
            Placement=Shift(1.0),
            getParentGeoFeatureGroup=lambda: SimpleNamespace(),
            getGlobalPlacement=lambda: Shift(130.0),
        )
        assert placement_in_frame_of(guest, host).x == 30.0  # global 130, conteneur de l'hôte 100
        same = SimpleNamespace(Placement=Shift(7.0), getParentGeoFeatureGroup=lambda: host_part)
        assert placement_in_frame_of(same, host).x == 7.0  # même conteneur : Placement local
