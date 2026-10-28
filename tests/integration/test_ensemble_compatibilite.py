# SPDX-License-Identifier: LGPL-2.1-or-later
"""Ensemble, Std Part, ``App::Link``, TechDraw, STEP et document sans l'atelier (J4b', N9,
N10, N14 ; ADR 0007, ADR 0008)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tests.integration.bureau import LAYOUT, Bureau, build_desk
from tests.integration.cadre import stale_or_invalid
from tests.integration.test_assemblages_compatibilite import (
    FREECAD_LIB,
    ROOT,
    assert_opens_without_workbench,
    run_python,
)

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
Part = pytest.importorskip("Part")
api = pytest.importorskip("freecad.menuiserie.api")

TURNED = App.Placement(App.Vector(150, -80, 25), App.Rotation(App.Vector(0, 0, 1), 30))


@pytest.fixture
def meuble(document: Any) -> tuple[Any, Bureau]:
    """Bureau rangé dans un Std Part tourné de 30° autour de Z et déplacé."""
    part = document.addObject("App::Part", "Meuble")
    part.Placement = TURNED
    bureau = build_desk(document, part)
    return part, bureau


# --- N9 : Std Part ------------------------------------------------------------------------------


def test_bureau_dans_un_std_part(meuble: tuple[Any, Bureau]) -> None:
    part, bureau = meuble
    assert bureau.furniture.getParentGeoFeatureGroup() == part
    assert tuple(bureau.furniture.Origin) == pytest.approx((0, 0, 0))
    bureau.furniture.Depth = 800
    bureau.doc.recompute()
    assert bureau.sizes("P") == (1200, 800, 30)
    assert bureau.sizes("JG") == (720, 760, 22)
    assert bureau.bounds("V")[1] == (641, 659)  # forme dans le repère du conteneur
    engines = {mark: bureau.expressions(mark) for mark in LAYOUT}
    part.Placement = App.Placement(App.Vector(-500, 20, 0), App.Rotation(App.Vector(1, 0, 0), 10))
    bureau.doc.recompute()
    assert {mark: bureau.expressions(mark) for mark in LAYOUT} == engines
    assert bureau.bounds("V")[1] == (641, 659)
    assert stale_or_invalid(bureau.doc) == []


# --- N10 : App::Link et duplication -------------------------------------------------------------


def test_lien_vers_le_std_part_suit_l_original(meuble: tuple[Any, Bureau]) -> None:
    part, bureau = meuble
    link = bureau.doc.addObject("App::Link", "Lien")
    link.LinkedObject = part
    link.Placement = App.Placement(App.Vector(3000, 0, 0), App.Rotation())
    bureau.doc.recompute()
    api.resize_furniture(bureau.furniture, depth=800, width=1400)
    original = Part.getShape(part).Volume
    assert Part.getShape(link).Volume == pytest.approx(original, rel=1e-6)
    assert stale_or_invalid(bureau.doc) == []


def test_duplication_independante(meuble: tuple[Any, Bureau]) -> None:
    part, bureau = meuble
    doc = bureau.doc
    count = len(doc.Objects)
    [copy] = doc.copyObject([part], True)  # comme « Dupliquer la sélection »
    doc.recompute()
    created = doc.Objects[count:]
    [furniture] = [obj for obj in created if obj.Name.startswith("Furniture")]
    members = [obj for obj in created if "FurnitureBindings" in obj.PropertiesList]
    assert len(members) == 4
    assert all(obj.Furniture == furniture for obj in members)
    assert all(obj.getParentGeoFeatureGroup() == copy for obj in [furniture, *members])
    # Les pièces se citent par leur Name : la copie vise ses propres pièces sans rien relier.
    furniture.Depth = 800
    doc.recompute()
    assert bureau.sizes("JG")[1] == 560
    assert sorted(obj.Width.Value for obj in members) == pytest.approx([400, 760, 760, 800])
    # Liaison qui viserait encore l'original (ancienne copie) : « Relier » la rétablit.
    copied_joue = next(obj for obj in members if obj.Label.startswith("Joue gauche"))
    copied_joue.setExpression("Width", "<<Bureau>>.Depth - 40 mm")
    assert api.rebind_furniture(furniture) == ()
    engine = {path.lstrip("."): text for path, text in copied_joue.ExpressionEngine}
    assert engine["Width"] == f"<<{furniture.Label}>>.Depth - 40 mm"
    assert stale_or_invalid(doc) == []


# --- N14 : TechDraw, STEP, sans l'atelier, inventaire -------------------------------------------


def test_vue_techdraw_du_std_part(meuble: tuple[Any, Bureau]) -> None:
    pytest.importorskip("TechDraw", reason="TechDraw non importable dans freecadcmd (critère G)")
    part, bureau = meuble
    doc = bureau.doc
    page = doc.addObject("TechDraw::DrawPage", "Page")
    page.Template = doc.addObject("TechDraw::DrawSVGTemplate", "Modele")
    view = doc.addObject("TechDraw::DrawViewPart", "Vue")
    page.addView(view)
    view.Source = [part]
    doc.recompute()
    assert view.isValid()
    bureau.furniture.Depth = 800
    doc.recompute()
    assert view.isValid()
    assert "Invalid" not in view.State


def test_export_et_import_step(meuble: tuple[Any, Bureau], tmp_path: Path) -> None:
    import_module = pytest.importorskip("Import")
    part, _ = meuble
    path = tmp_path / "bureau.step"
    import_module.export([part], str(path))
    shape = Part.read(str(path))
    assert shape.isValid()
    # Tout le contenu du Std Part est exporté, brutes masquées comprises.
    solids = [obj.Shape for obj in part.Group if hasattr(obj, "Shape") and not obj.Shape.isNull()]
    assert shape.Volume == pytest.approx(sum(item.Volume for item in solids), rel=1e-6)


def test_document_ouvert_sans_l_atelier(meuble: tuple[Any, Bureau], tmp_path: Path) -> None:
    _, bureau = meuble
    bureau.furniture.Height = 800
    bureau.doc.recompute()
    expected = {
        obj.Name: obj.Shape.Volume
        for obj in bureau.doc.Objects
        if hasattr(obj, "Shape") and not obj.Shape.isNull() and obj.Shape.Volume > 0
    }
    assert len(expected) == 10  # Std Part, 4 brutes, 3 pièces usinées, 2 jeux de tourillons
    assert_opens_without_workbench(bureau.doc, expected, tmp_path)


def test_module_du_proxy_importable_seul(tmp_path: Path) -> None:
    module = "freecad.menuiserie.features.furniture"
    code = f"import FreeCAD, importlib; importlib.import_module({module!r}); print('OK')"
    output = run_python(["-c", code], tmp_path, [FREECAD_LIB, ROOT])
    assert output.strip().endswith("OK")
