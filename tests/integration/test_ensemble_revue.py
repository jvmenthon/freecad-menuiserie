# SPDX-License-Identifier: LGPL-2.1-or-later
"""Relecture de fin de jalon « Ensemble à la souris » (ADR 0038) : Std Part tourné, suppression,
messages de sortie, Std Parts de l'utilisateur."""

from __future__ import annotations

from typing import Any

import pytest

from tests.integration.bureau import build_parts
from tests.integration.cadre import stale_or_invalid
from tests.integration.test_ensemble_membres import caisson
from tests.integration.test_ensemble_std_part import geometry

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
api = pytest.importorskip("freecad.menuiserie.api")
container = pytest.importorskip("freecad.menuiserie.features.furniture_container")


# --- 1 : ensemble déjà tourné, puis rangé dans un parent ----------------------------------------


def test_ensemble_tourne_puis_range_dans_un_parent(document: Any) -> None:
    desk = build_parts(document)
    sub, parts = caisson(document)
    assert api.rotate_furniture(sub, (0, 0, 30))
    document.recompute()
    before = geometry(document)
    members = [desk.parts["P"], desk.parts["JG"], desk.parts["JD"], sub]
    furniture, _ = api.make_furniture(members, "Bureau")
    sub_std = container.std_part_of(sub)
    assert tuple(sub.Origin) == (0, 0, 0)  # l'Origin est passée dans le Placement du Std Part
    assert geometry(document) == before
    corner = sub_std.Placement.Base
    furniture.Width = 1400
    document.recompute()
    assert stale_or_invalid(document) == []
    assert sub_std.Placement.Base.isEqual(corner, 1e-6)  # ne se décale pas au recalcul
    assert {p.Name for p in parts.values()} <= {o.Name for o in sub_std.Group}
