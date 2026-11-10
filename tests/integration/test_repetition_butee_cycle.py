# SPDX-License-Identifier: LGPL-2.1-or-later
"""Butée sur la pièce assemblée à l'original (retour de jv, 2026-11-10) : pas de cycle
(« The graph must be a DAG ») ni d'objet resté à recalculer."""

from __future__ import annotations

from typing import Any

import pytest

from tests.integration.cadre import placement, stale_or_invalid
from tests.integration.test_repetition_assemblages import part
from tests.integration.test_repetition_butee import face_at

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
api = pytest.importorskip("freecad.menuiserie.api")


def test_butee_sur_la_piece_assemblee(document: Any) -> None:
    long = part(document, "B", (500, 60, 22), placement(0, 0))
    bar = part(document, "A", (280, 40, 22), placement(140, 60, 90))
    api.make_dowels(long, bar)
    document.recompute()
    params = api.RepeatParams(
        spacing=api.SpacingMode.COUNT_ON_SPAN, grid=(api.AxisRepeat(api.RepeatAxis.X, 3, span=1.0),)
    )
    rep = api.make_repeat(
        [bar], params, stops={api.RepeatAxis.X: api.Stop(long, face_at(long, "X", 500.0))}
    )
    document.recompute()
    long.Length = 600
    document.recompute()
    assert stale_or_invalid(document) == []
    assert [o.Name for o in document.Objects if "Touched" in o.State] == []
    assert rep.Span.Value > 0
    cycles = [o.Name for o in document.Objects if o in o.OutListRecursive]
    assert cycles == []
