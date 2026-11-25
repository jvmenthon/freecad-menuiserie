# SPDX-License-Identifier: LGPL-2.1-or-later
"""Vue éclatée de l'ouvrage dans une page TechDraw (issue #153, demande du 2026-11-13)."""

from __future__ import annotations

from typing import Any

import pytest

from tests.integration.bureau import Bureau, build_desk
from tests.integration.cadre import stale_or_invalid

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
pytest.importorskip("TechDraw", reason="TechDraw non importable dans freecadcmd")
api = pytest.importorskip("freecad.menuiserie.api")
drawing = pytest.importorskip("freecad.menuiserie.features.drawing")
exploded = pytest.importorskip("freecad.menuiserie.features.drawing_exploded")


@pytest.fixture
def bureau(document: Any) -> Bureau:
    return build_desk(document)


def holder(page: Any) -> Any:
    (view,) = page.Views
    (shape,) = view.Source
    return shape


def test_page_de_vue_eclatee(bureau: Bureau) -> None:
    page = api.make_exploded_drawing(bureau.doc, [bureau.furniture])
    assert page.TypeId == "TechDraw::DrawPage"
    assert getattr(page, drawing.KIND) == exploded.EXPLODED_KIND
    shape = holder(page)
    assert shape.TypeId == "Part::Feature" and shape.Visibility is False
    assert len(shape.Shape.Solids) >= 4  # plateau, joues, voile
    # Les pièces s'écartent : l'éclaté est plus grand que le bureau.
    original = drawing.global_box(drawing.drawing_sources(bureau.doc, [bureau.furniture]))
    assert shape.Shape.BoundBox.XLength > original.XLength
    assert shape.Shape.BoundBox.ZLength > original.ZLength
    assert all(view.isValid() and "Invalid" not in view.State for view in page.Views)
    assert stale_or_invalid(bureau.doc) == []


def test_relance_refait_la_meme_page(bureau: Bureau) -> None:
    page = api.make_exploded_drawing(bureau.doc, [bureau.furniture])
    shape = holder(page)
    count = len(bureau.doc.Objects)
    again = api.make_exploded_drawing(bureau.doc, [bureau.furniture])
    assert again == page and holder(again) == shape
    assert len(bureau.doc.Objects) == count


def test_annulation_en_une_fois(bureau: Bureau) -> None:
    doc = bureau.doc
    doc.UndoMode = 1
    before = {obj.Name for obj in doc.Objects}
    api.make_exploded_drawing(doc, [bureau.furniture])
    doc.undo()
    assert {obj.Name for obj in doc.Objects} == before
