# SPDX-License-Identifier: LGPL-2.1-or-later
"""Plans cotés : sauvegarde, réouverture et rétablissement (revue testeur de la PR #247,
issue #153, ADR 0053)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from tests.integration.bureau import Bureau, build_desk

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
pytest.importorskip("TechDraw", reason="TechDraw non importable dans freecadcmd")
api = pytest.importorskip("freecad.menuiserie.api")
drawing = pytest.importorskip("freecad.menuiserie.features.drawing")

ANNOTATION = "TechDraw::DrawViewAnnotation"


@pytest.fixture
def bureau(document: Any) -> Bureau:
    return build_desk(document)


def _notes(page: Any) -> list[str]:
    (note,) = [view for view in page.Views if view.TypeId == ANNOTATION]
    return list(note.Text)


def test_plans_de_piece_intacts_apres_reouverture(
    bureau: Bureau, rouvrir: Callable[[Any], Any]
) -> None:
    pages = api.make_part_drawings(bureau.doc, [bureau.furniture])
    before = {page.Name: (_notes(page), sorted(v.Name for v in page.Views)) for page in pages}
    reopened = rouvrir(bureau.doc)
    for name, (notes, views) in before.items():
        page = reopened.getObject(name)
        assert page is not None
        assert getattr(page, drawing.KIND) == drawing.PART_KIND
        assert _notes(page) == notes
        assert sorted(v.Name for v in page.Views) == views
    # Relancée sur le document rouvert, la commande refait les mêmes pages.
    furniture = reopened.getObject(bureau.furniture.Name)
    again = api.make_part_drawings(reopened, [furniture])
    assert sorted(page.Name for page in again) == sorted(before)


def test_vue_eclatee_intacte_apres_reouverture(
    bureau: Bureau, rouvrir: Callable[[Any], Any]
) -> None:
    page = api.make_exploded_drawing(bureau.doc, [bureau.furniture])
    name = page.Name
    reopened = rouvrir(bureau.doc)
    restored = reopened.getObject(name)
    (view,) = restored.Views
    (holder,) = view.Source
    assert not holder.Shape.isNull()
    furniture = reopened.getObject(bureau.furniture.Name)
    assert api.make_exploded_drawing(reopened, [furniture]).Name == name


@pytest.mark.parametrize("command", ["make_part_drawings", "make_exploded_drawing"])
def test_annuler_puis_retablir(bureau: Bureau, command: str) -> None:
    doc = bureau.doc
    doc.UndoMode = 1
    before = len(doc.Objects)
    getattr(api, command)(doc, [bureau.furniture])
    after = len(doc.Objects)
    doc.undo()
    assert len(doc.Objects) == before
    doc.redo()
    assert len(doc.Objects) == after


def test_plan_de_piece_suit_un_changement_de_cote(bureau: Bureau) -> None:
    part = bureau.parts["P"]
    api.make_part_drawings(bureau.doc, [bureau.shown("P")])
    part.Length = 1000
    bureau.doc.recompute()
    (page,) = api.make_part_drawings(bureau.doc, [bureau.shown("P")])
    lengths = [float(dim.getRawValue()) for dim in drawing.overall_dimensions(page)]
    assert lengths[0] == pytest.approx(1000, abs=0.01)
