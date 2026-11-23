# SPDX-License-Identifier: LGPL-2.1-or-later
"""Copies dessinées sur les plans (retour de jv du 23/11 : « les copies n'apparaissent pas »).

Copie par « Répéter » (vraies pièces de bois) et copie par lien (``App::Link`` du Std Part d'un
ensemble, comme le conseille le panneau des ensembles) : le plan de l'ouvrage les dessine à
leur place et les plans de pièce les comptent dans la quantité.
"""

from __future__ import annotations

from typing import Any

import pytest

from tests.integration.bureau import Bureau, build_desk

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
TechDraw = pytest.importorskip("TechDraw", reason="TechDraw non importable dans freecadcmd")
api = pytest.importorskip("freecad.menuiserie.api")
drawing = pytest.importorskip("freecad.menuiserie.features.drawing")
container = pytest.importorskip("freecad.menuiserie.features.furniture_container")
furniture = pytest.importorskip("freecad.menuiserie.features.furniture")

WIDTH, DEPTH, HEIGHT = 1200.0, 600.0, 750.0  # le bureau de test


@pytest.fixture
def bureau(document: Any) -> Bureau:
    return build_desk(document)


def _width(page: Any) -> float:
    return float(drawing.overall_dimensions(page)[0].getRawValue())


def _quantities(pages: list[Any]) -> int:
    kinds = [dict(page.Template.EditableTexts)["document_type"] for page in pages]
    return sum(int(kind.rsplit(",", 1)[1].split()[0]) for kind in kinds)


def _link_copy(bureau: Bureau, shift: float) -> Any:
    std_part = container.std_part_of(bureau.furniture)
    assert std_part is not None
    link = bureau.doc.addObject("App::Link", "CopieBureau")
    link.LinkedObject = std_part
    link.Placement = App.Placement(
        std_part.Placement.Base + App.Vector(shift, 0, 0), std_part.Placement.Rotation
    )
    bureau.doc.recompute()
    return link


def test_copie_par_lien_dessinee_et_comptee(bureau: Bureau) -> None:
    link = _link_copy(bureau, 2000.0)
    scope = drawing.document_scope(bureau.doc)
    assert link in scope
    assert link in drawing.drawing_sources(bureau.doc, scope)
    page = api.make_overall_drawing(bureau.doc, scope)
    assert _width(page) == pytest.approx(2000.0 + WIDTH, abs=0.01)
    pages = api.make_part_drawings(bureau.doc, [])
    assert _quantities(pages) == 8  # 4 pièces, deux fois


def test_lien_seul_selectionne(bureau: Bureau) -> None:
    link = _link_copy(bureau, 2000.0)
    original = drawing.global_box(drawing.drawing_sources(bureau.doc, [bureau.furniture]))
    box = drawing.global_box(drawing.drawing_sources(bureau.doc, [link]))
    assert box.XLength == pytest.approx(WIDTH, abs=0.01)
    assert box.XMin == pytest.approx(original.XMin + 2000.0, abs=0.01)


def test_copie_par_repeter_dessinee_et_comptee(bureau: Bureau) -> None:
    params = api.RepeatParams(count=1, step=1500.0, axis=api.RepeatAxis.X)
    api.make_repeat([bureau.furniture], params)
    bureau.doc.recompute()
    scope = drawing.document_scope(bureau.doc)
    assert len([obj for obj in scope if furniture.is_furniture(obj)]) == 2
    page = api.make_overall_drawing(bureau.doc, scope)
    assert _width(page) == pytest.approx(1500.0 + WIDTH, abs=0.01)
    assert _quantities(api.make_part_drawings(bureau.doc, [])) == 8


def test_arbre_du_choix_des_pieces(bureau: Bureau) -> None:
    """Panneau « Plans de pièce » sans sélection : le bureau et ses 4 pièces, la copie par
    lien comme une ligne à cocher."""
    choice = pytest.importorskip("freecad.menuiserie.features.drawing_choice")
    link = _link_copy(bureau, 2000.0)
    groups, loose = choice.part_choices(bureau.doc)
    assert loose == []
    by_name = {row.obj.Name: row for row in groups}
    assert by_name[bureau.furniture.Name].parts == 4
    assert by_name[link.Name].children == ()


def test_tableau_de_liens_compte_chaque_copie(bureau: Bureau) -> None:
    """Revue : un tableau de liens compte autant de fois qu'il a d'éléments."""
    link = _link_copy(bureau, 2000.0)
    link.ElementCount = 3
    bureau.doc.recompute()
    assert _quantities(api.make_part_drawings(bureau.doc, [])) == 4 * (1 + 3)


def test_vue_eclatee_d_une_copie_par_lien(bureau: Bureau) -> None:
    """Revue : une copie par lien seule s'éclate pièce par pièce."""
    link = _link_copy(bureau, 2000.0)
    assembled = drawing.global_box(drawing.drawing_sources(bureau.doc, [link]))
    api.make_exploded_drawing(bureau.doc, [link])
    holder = next(obj for obj in bureau.doc.Objects if obj.Name.startswith("MenuiserieEclate"))
    assert holder.Shape.BoundBox.XLength > assembled.XLength + 1.0


def test_cartouche_d_une_copie_et_titre_vide(bureau: Bureau) -> None:
    """Revue : le matériau d'une copie par lien est écrit ; un titre vidé reprend le nom."""
    link = _link_copy(bureau, 2000.0)
    options = api.DrawingOptions(title="Mon titre")
    page = api.make_overall_drawing(bureau.doc, [link], options)
    texts = dict(page.Template.EditableTexts)
    assert texts["material"].strip() != ""
    assert texts["drawing_title"] == "Mon titre"
    page = api.make_overall_drawing(bureau.doc, [link], api.DrawingOptions(title=""))
    assert dict(page.Template.EditableTexts)["drawing_title"] == str(link.Label)
