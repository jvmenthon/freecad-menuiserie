# SPDX-License-Identifier: LGPL-2.1-or-later
"""Diagnostic temporaire : état « Touched » d'une pièce en bois dans un ensemble."""

from __future__ import annotations

from typing import Any

import pytest

from tests.integration.test_piece_en_bois import box

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
api = pytest.importorskip("freecad.menuiserie.api")


@pytest.mark.parametrize("angle", [0.0, 30.0])
def test_diagnostic_etat(document: Any, angle: float) -> None:
    top = api.make_wood_part(1200, 600, 30, "chene", mark="Plateau", doc=document)
    top.Placement = App.Placement(App.Vector(0, 0, 720), App.Rotation())
    source = box(document, (45.0, 95.0, 720.0), "SourcePied")
    turn = App.Rotation(App.Vector(0, 0, 1), angle)
    source.Placement = App.Placement(App.Vector(100, 400, 0), turn)
    document.recompute()
    leg = api.make_shaped_part(source, mark="Pied")
    stages = [("cree", list(leg.State))]
    document.recompute()
    stages.append(("cree+recalcul", list(leg.State)))
    furniture, _notices = api.make_furniture([top, leg], label="Table")
    stages.append(("ensemble", list(leg.State)))
    document.recompute()
    stages.append(("ensemble+recalcul", list(leg.State)))
    api.resize_furniture(furniture, depth=800)
    stages.append(("redim", list(leg.State)))
    document.recompute()
    stages.append(("redim+recalcul", list(leg.State)))
    document.recompute()
    stages.append(("second recalcul", list(leg.State)))
    leg.touch()
    document.recompute()
    stages.append(("touch+recalcul", list(leg.State)))
    assert False, (angle, stages, leg.ExpressionEngine, leg.FurnitureBindings)
