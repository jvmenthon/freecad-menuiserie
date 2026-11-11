# SPDX-License-Identifier: LGPL-2.1-or-later
"""Butée sur la pièce usinée assemblée à l'original (retour de jv, 2026-11-10, fichier
« repet-dag ») : la pièce usinée dépend des assemblages recopiés, donc des copies ; la butée vise
la brute, sans cycle (« The graph must be a DAG ») ni objet resté à recalculer."""

from __future__ import annotations

from typing import Any

import pytest

from tests.integration.cadre import placement, stale_or_invalid
from tests.integration.test_repetition_assemblages import part
from tests.integration.test_repetition_butee import face_at

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
api = pytest.importorskip("freecad.menuiserie.api")
X = pytest.importorskip("freecad.menuiserie.core.repeat").RepeatAxis.X


def sans_cycle(doc: Any) -> bool:
    try:
        return all(o not in o.OutListRecursive for o in doc.Objects)
    except IndexError:  # « cyclic dependency detected »
        return False


def touches(doc: Any) -> list[str]:
    return [o.Name for o in doc.Objects if "Touched" in o.State]


def scene(doc: Any) -> tuple[Any, Any]:
    long = part(doc, "B", (500, 60, 22), placement(0, 0))
    bar = part(doc, "A", (280, 40, 22), placement(140, 60, 90))
    api.make_loose_tenons(long, bar)
    doc.recompute()
    return long, bar


def params(count: int = 3) -> Any:
    return api.RepeatParams(
        spacing=api.SpacingMode.COUNT_ON_SPAN, grid=(api.AxisRepeat(X, count, span=1.0),)
    )


def test_butee_sur_la_piece_usinee_assemblee(document: Any) -> None:
    long, bar = scene(document)
    usinee = api.machined_part_of(long)
    rep = api.make_repeat([bar], params(), stops={X: api.Stop(usinee, face_at(usinee, "X", 500.0))})
    assert rep.Stop[0] == long  # la brute, pas la pièce usinée
    assert rep.Stop[1] == [face_at(long, "X", 500.0)]
    document.recompute()
    assert sans_cycle(document) and touches(document) == []
    long.Length = 600
    document.recompute()
    assert rep.Span.Value == 500.0  # A commence à X = 100
    assert sans_cycle(document) and touches(document) == []
    assert stale_or_invalid(document) == []


def test_document_avec_butee_sur_une_piece_usinee_corrige(document: Any) -> None:
    long, bar = scene(document)
    usinee = api.machined_part_of(long)
    rep = api.make_repeat([bar], params(), stops={X: api.Stop(long, face_at(long, "X", 500.0))})
    rep.Stop = (usinee, [face_at(usinee, "X", 500.0)])  # comme un document d'avant le correctif
    rep.Proxy.onDocumentRestored(rep)
    assert rep.Stop[0] == long and rep.Stop[1] == [face_at(long, "X", 500.0)]
    document.recompute()
    assert sans_cycle(document) and touches(document) == []
