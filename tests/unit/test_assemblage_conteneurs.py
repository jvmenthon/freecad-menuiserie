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
            assert frame_containers(first, second) == [child_a, root, child_b]
