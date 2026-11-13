# SPDX-License-Identifier: LGPL-2.1-or-later
"""Plans de pièce : une page TechDraw par pièce distincte (issue #153, ADR 0053, lot P-c)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from tests.integration.bureau import Bureau, build_desk
from tests.integration.cadre import stale_or_invalid

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
pytest.importorskip("TechDraw", reason="TechDraw non importable dans freecadcmd")
api = pytest.importorskip("freecad.menuiserie.api")
drawing = pytest.importorskip("freecad.menuiserie.features.drawing")

ANNOTATION = "TechDraw::DrawViewAnnotation"


@pytest.fixture
def bureau(document: Any) -> Bureau:
    return build_desk(document)


def dimensions(page: Any) -> list[float]:
    """Longueur, largeur et épaisseur cotées, en millimètres réels."""
    return [float(dim.getRawValue()) for dim in drawing.overall_dimensions(page)]


def notes(page: Any) -> list[str]:
    (note,) = [view for view in page.Views if view.TypeId == ANNOTATION]
    return list(note.Text)


def quantity(page: Any) -> int:
    kind = dict(page.Template.EditableTexts)["document_type"]
    return int(kind.rsplit(",", 1)[1].split()[0])


def page_of(pages: list[Any], part: Any) -> Any:
    shown = api.machined_part_of(part) or part
    for page in pages:
        front = next(v for v in page.Views if v.Name.startswith("MenuiseriePlanFront"))
        if list(front.Source) == [shown]:
            return page
    raise AssertionError(f"pas de page pour {part.Label}")


def test_une_page_par_piece_distincte(bureau: Bureau) -> None:
    pages = api.make_part_drawings(bureau.doc, [bureau.furniture])
    # Plateau, voile, joues : les joues, symétriques, peuvent avoir leurs perçages sur des
    # faces différentes et donc deux pages.
    assert 3 <= len(pages) <= 4
    assert sum(quantity(page) for page in pages) == 4
    assert all(page.TypeId == "TechDraw::DrawPage" for page in pages)
    assert all(getattr(page, drawing.KIND) == drawing.PART_KIND for page in pages)
    for page in pages:
        assert all(view.isValid() and "Invalid" not in view.State for view in page.Views)
    assert stale_or_invalid(bureau.doc) == []


def test_cotes_dans_le_repere_de_la_piece(bureau: Bureau) -> None:
    pages = api.make_part_drawings(bureau.doc, [bureau.furniture])
    assert dimensions(page_of(pages, bureau.parts["P"])) == pytest.approx([1200, 600, 30], abs=0.01)
    # Joue tournée de -90° : la face montre quand même sa longueur et sa largeur.
    assert dimensions(page_of(pages, bureau.parts["JG"])) == pytest.approx([720, 560, 22], abs=0.01)


def test_tableau_des_usinages(bureau: Bureau) -> None:
    pages = api.make_part_drawings(bureau.doc, [bureau.furniture])
    voile = notes(page_of(pages, bureau.parts["V"]))
    holes = [line for line in voile if "Ø" in line]
    assert holes, voile
    assert all("bout" in line for line in holes), voile  # tourillons en bout de voile
    joue = notes(page_of(pages, bureau.parts["JG"]))
    assert any("Ø" in line for line in joue), joue
    assert len(notes(page_of(pages, bureau.parts["P"]))) == 1  # plateau sans usinage


def test_relance_refait_les_memes_pages(bureau: Bureau) -> None:
    pages = api.make_part_drawings(bureau.doc, [bureau.furniture])
    again = api.make_part_drawings(bureau.doc, [bureau.furniture])
    assert sorted(page.Name for page in again) == sorted(page.Name for page in pages)
    overall = api.make_overall_drawing(bureau.doc, [bureau.parts["P"]])
    assert overall not in pages  # le plan de l'ouvrage d'une pièce seule reste une autre page


def test_selection_d_une_piece(bureau: Bureau) -> None:
    (page,) = api.make_part_drawings(bureau.doc, [bureau.shown("V")])
    assert quantity(page) == 1
    assert "Voile" in dict(page.Template.EditableTexts)["drawing_title"]


def test_annulation_en_une_fois(bureau: Bureau) -> None:
    doc = bureau.doc
    doc.UndoMode = 1
    before = len(doc.Objects)
    api.make_part_drawings(doc, [bureau.furniture])
    assert len(doc.Objects) > before
    doc.undo()
    assert len(doc.Objects) == before


def test_rien_a_dessiner(document: Any) -> None:
    with pytest.raises(ValueError, match="aucune pièce"):
        api.make_part_drawings(document, [])


def test_perspective_a_sa_propre_echelle(bureau: Bureau) -> None:
    pages = api.make_part_drawings(bureau.doc, [bureau.furniture])
    for page in pages:
        isos = [v for v in page.Views if v.Name.startswith("MenuiseriePlanIso")]
        assert len(isos) == 1, page.Label
        assert isos[0].ScaleType == "Custom"
        assert 0 < isos[0].Scale <= page.Scale
        assert all(
            view.HardHidden
            for view in page.Views
            if view.TypeId == "TechDraw::DrawViewPart" and view not in isos
        )


# --- Sauvegarde, réouverture, annuler et rétablir (revue testeur de la PR #247) ---


def test_plans_de_piece_intacts_apres_reouverture(
    bureau: Bureau, rouvrir: Callable[[Any], Any]
) -> None:
    pages = api.make_part_drawings(bureau.doc, [bureau.furniture])
    furniture_name = bureau.furniture.Name
    before = {page.Name: (notes(page), sorted(v.Name for v in page.Views)) for page in pages}
    reopened = rouvrir(bureau.doc)
    for name, (expected, views) in before.items():
        page = reopened.getObject(name)
        assert page is not None
        assert getattr(page, drawing.KIND) == drawing.PART_KIND
        assert notes(page) == expected
        assert sorted(v.Name for v in page.Views) == views
    # Relancée sur le document rouvert, la commande refait les mêmes pages.
    furniture = reopened.getObject(furniture_name)
    again = api.make_part_drawings(reopened, [furniture])
    assert sorted(page.Name for page in again) == sorted(before)


def test_vue_eclatee_intacte_apres_reouverture(
    bureau: Bureau, rouvrir: Callable[[Any], Any]
) -> None:
    page = api.make_exploded_drawing(bureau.doc, [bureau.furniture])
    name, furniture_name = page.Name, bureau.furniture.Name
    reopened = rouvrir(bureau.doc)
    restored = reopened.getObject(name)
    (view,) = restored.Views
    (holder,) = view.Source
    assert not holder.Shape.isNull()
    furniture = reopened.getObject(furniture_name)
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
    api.make_part_drawings(bureau.doc, [bureau.shown("P")])
    bureau.furniture.Width = 1000  # la longueur du plateau suit la largeur du bureau
    bureau.doc.recompute()
    (page,) = api.make_part_drawings(bureau.doc, [bureau.shown("P")])
    lengths = [float(dim.getRawValue()) for dim in drawing.overall_dimensions(page)]
    assert lengths[0] == pytest.approx(1000, abs=0.01)
