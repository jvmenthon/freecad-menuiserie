# SPDX-License-Identifier: LGPL-2.1-or-later
"""Diagnostic temporaire : état « Touched » d'une pièce en bois dans un ensemble."""

from __future__ import annotations

from typing import Any

import pytest

from tests.integration.test_piece_en_bois import box

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
api = pytest.importorskip("freecad.menuiserie.api")


@pytest.mark.parametrize(("angle", "between"), [(0.0, False), (30.0, False), (30.0, True)])
def test_diagnostic_etat(document: Any, angle: float, between: bool) -> None:
    top = api.make_wood_part(1200, 600, 30, "chene", mark="Plateau", doc=document)
    top.Placement = App.Placement(App.Vector(0, 0, 720), App.Rotation())
    source = box(document, (45.0, 95.0, 720.0), "SourcePied")
    source.Placement = App.Placement(
        App.Vector(100, 400, 0), App.Rotation(App.Vector(0, 0, 1), angle)
    )
    document.recompute()
    leg = api.make_shaped_part(source, mark="Pied")
    stages = []

    def note(name: str) -> None:
        stages.append(f"{name}={'/'.join(leg.State)}")

    note("cree")
    furniture, _notices = api.make_furniture([top, leg], label="Table")
    note("ensemble")
    if between:
        document.recompute()
        note("ensemble+recalcul")
    api.resize_furniture(furniture, depth=800)
    note("redim")
    document.recompute()
    note("redim+recalcul")
    document.recompute()
    note("second")
    pytest.fail(f"DIAG {angle} {between} {' ; '.join(stages)} {dict(leg.FurnitureBindings)}")
