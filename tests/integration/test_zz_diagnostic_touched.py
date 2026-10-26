# SPDX-License-Identifier: LGPL-2.1-or-later
"""Diagnostic temporaire : état « Touched » d'une pièce en bois dans un ensemble."""

from __future__ import annotations

from typing import Any

import pytest

from tests.integration.test_piece_en_bois import box

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
api = pytest.importorskip("freecad.menuiserie.api")
TURN_30 = App.Rotation(App.Vector(0, 0, 1), 30)


def test_diagnostic_pas_a_pas(document: Any) -> None:
    top = api.make_wood_part(1200, 600, 30, "chene", mark="Plateau", doc=document)
    top.Placement = App.Placement(App.Vector(0, 0, 720), App.Rotation())
    source = box(document, (45.0, 95.0, 720.0), "SourcePied")
    source.Placement = App.Placement(App.Vector(100, 400, 0), TURN_30)
    document.recompute()
    leg = api.make_shaped_part(source, mark="Pied")
    log = [f"cree={leg.State}"]
    furniture, _notices = api.make_furniture([top, leg], label="Table")
    log.append(f"ens={leg.State}")
    sizes = (leg.Length.Value, leg.Width.Value, leg.Thickness.Value)
    log.append(f"cotes={leg.State} {sizes}")
    api.resize_furniture(furniture, depth=800)
    log.append(f"redim={leg.State}")
    document.recompute()
    log.append(f"recalc={leg.State} {(leg.Length.Value, leg.Width.Value, leg.Thickness.Value)}")
    _ = leg.ExpressionEngine
    log.append(f"expr={leg.State}")
    document.recompute()
    log.append(f"recalc2={leg.State}")
    pytest.fail("DIAG " + " ; ".join(log))
