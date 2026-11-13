# SPDX-License-Identifier: LGPL-2.1-or-later
"""Plan de l'ouvrage dans une page TechDraw standard (issue #153, ADR 0053, lot P-a)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tests.integration.bureau import Bureau, build_desk
from tests.integration.cadre import stale_or_invalid

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
pytest.importorskip("TechDraw", reason="TechDraw non importable dans freecadcmd")
api = pytest.importorskip("freecad.menuiserie.api")
drawing = pytest.importorskip("freecad.menuiserie.features.drawing")

VIEWS = ("MenuiseriePlanFront", "MenuiseriePlanCutV", "MenuiseriePlanCutH", "MenuiseriePlanIso")


@pytest.fixture
def bureau(document: Any) -> Bureau:
    return build_desk(document)


def values(page: Any) -> list[float]:
    """Valeurs des cotes hors tout (largeur, profondeur, hauteur), en millimètres réels."""
    return [float(dim.getRawValue()) for dim in drawing.overall_dimensions(page)]


def test_page_standard_marquee(bureau: Bureau) -> None:
    page = api.make_overall_drawing(bureau.doc, [bureau.furniture])
    assert page.TypeId == "TechDraw::DrawPage"
    assert page.MenuiserieDrawing is True
    assert drawing.is_workshop_drawing(page)
    assert not hasattr(page, "Proxy")  # page ordinaire, lisible sans l'atelier (ADR 0007)
    assert page.Template.TypeId == "TechDraw::DrawSVGTemplate"
    assert "A3" in page.Template.Template and "Landscape" in page.Template.Template
    assert page.Scale == pytest.approx(0.1)
    views = [bureau.doc.getObject(name) for name in VIEWS]
    assert all(view is not None and view in page.Views for view in views)
    assert all(view.isValid() and "Invalid" not in view.State for view in views)
    assert stale_or_invalid(bureau.doc) == []


def test_vues_des_pieces_usinees(bureau: Bureau) -> None:
    page = api.make_overall_drawing(bureau.doc, [bureau.furniture])
    front = bureau.doc.getObject(VIEWS[0])
    assert len(front.Source) == 4  # plateau, deux joues, voile ; pas de brute sous une usinée
    machined = [obj for obj in front.Source if api.is_machined_part(obj)]
    assert len(machined) >= 2  # au moins les joues, hôtes des tourillons
    assert all(api.blank_of(obj) not in front.Source for obj in machined)
    assert page.Views


def test_coupes_au_milieu_du_meuble(bureau: Bureau) -> None:
    api.make_overall_drawing(bureau.doc, [bureau.furniture])
    front = bureau.doc.getObject(VIEWS[0])
    vertical, horizontal = (bureau.doc.getObject(name) for name in VIEWS[1:3])
    assert vertical.TypeId == horizontal.TypeId == "TechDraw::DrawViewSection"
    assert vertical.BaseView == front and horizontal.BaseView == front
    assert (vertical.SectionSymbol, horizontal.SectionSymbol) == ("A", "B")
    assert vertical.SectionNormal.getAngle(App.Vector(-1, 0, 0)) < 1e-6
    assert horizontal.SectionNormal.getAngle(App.Vector(0, 0, 1)) < 1e-6
    center, expected = vertical.SectionOrigin, drawing.global_box(front.Source).Center
    assert (center.x, center.y, center.z) == pytest.approx((expected.x, expected.y, expected.z))
    assert horizontal.SectionOrigin == center
    # Disposition européenne : coupe verticale à droite de la face, horizontale dessous.
    x, y = float(front.X), float(front.Y)
    assert float(vertical.X) > x and float(vertical.Y) == pytest.approx(y)
    assert float(horizontal.Y) < y and float(horizontal.X) == pytest.approx(x)


def test_cotes_hors_tout(bureau: Bureau) -> None:
    page = api.make_overall_drawing(bureau.doc, [bureau.furniture])
    assert values(page) == pytest.approx([1200, 600, 750], abs=0.01)


def test_cotes_suivent_le_modele(bureau: Bureau) -> None:
    page = api.make_overall_drawing(bureau.doc, [bureau.furniture])
    api.resize_furniture(bureau.furniture, depth=800, width=1400)
    bureau.doc.recompute()
    assert values(page) == pytest.approx([1400, 800, 750], abs=0.01)
    assert stale_or_invalid(bureau.doc) == []


def test_relance_refait_la_meme_page(bureau: Bureau) -> None:
    doc = bureau.doc
    page = api.make_overall_drawing(doc, [bureau.furniture])
    count = len(doc.Objects)
    api.resize_furniture(bureau.furniture, height=2400)
    doc.recompute()
    again = api.make_overall_drawing(doc, [bureau.furniture])
    assert again == page
    assert len(doc.Objects) == count
    assert again.Scale == pytest.approx(0.05)  # 2,40 m de haut ne tient plus au 1 : 10 sur A3
    assert values(again) == pytest.approx([1200, 600, 2400], abs=0.01)


def test_page_modifiee_a_la_main_conservee(bureau: Bureau) -> None:
    doc = bureau.doc
    page = api.make_overall_drawing(doc, [bureau.furniture])
    note = doc.addObject("TechDraw::DrawViewAnnotation", "Note")
    page.addView(note)
    doc.recompute()
    other = api.make_overall_drawing(doc, [bureau.furniture])
    assert other != page
    assert note in page.Views and doc.getObject(VIEWS[0]) in page.Views
    assert drawing.is_workshop_drawing(other)


def test_format_a4_portrait(bureau: Bureau) -> None:
    options = api.DrawingOptions(page_format="A4", orientation=api.Orientation.PORTRAIT)
    page = api.make_overall_drawing(bureau.doc, [bureau.furniture], options)
    assert "A4" in page.Template.Template and "Portrait" in page.Template.Template
    assert page.Scale <= 0.05


def test_annulation_en_une_fois(bureau: Bureau) -> None:
    doc = bureau.doc
    doc.UndoMode = 1
    before = {obj.Name for obj in doc.Objects}
    api.make_overall_drawing(doc, [bureau.furniture])
    doc.undo()
    assert {obj.Name for obj in doc.Objects} == before


def test_refus_sans_modifier_le_document(bureau: Bureau) -> None:
    doc = bureau.doc
    count = len(doc.Objects)
    with pytest.raises(ValueError, match="aucune pièce"):
        api.make_overall_drawing(doc, [])
    with pytest.raises(ValueError, match="Format de page inconnu"):
        api.make_overall_drawing(doc, [bureau.furniture], api.DrawingOptions(page_format="B5"))
    other = App.newDocument("Autre")
    try:
        box = other.addObject("Part::Box", "Boite")
        with pytest.raises(ValueError, match="autre document"):
            api.make_overall_drawing(doc, [box])
    finally:
        App.closeDocument(other.Name)
    assert len(doc.Objects) == count


def test_document_actif_remis(bureau: Bureau) -> None:
    other = App.newDocument("Actif")
    try:
        api.make_overall_drawing(bureau.doc, [bureau.furniture])
        assert App.ActiveDocument == other  # ADR 0007 : rien de global n'est laissé changé
    finally:
        App.closeDocument(other.Name)


def test_solide_d_un_autre_atelier_dans_un_std_part_tourne(document: Any) -> None:
    part = document.addObject("App::Part", "Conteneur")
    box = document.addObject("Part::Box", "Boite")
    box.Length, box.Width, box.Height = 300, 200, 100
    part.addObject(box)
    part.Placement = App.Placement(App.Vector(50, 0, 0), App.Rotation(App.Vector(0, 0, 1), 90))
    document.recompute()
    page = api.make_overall_drawing(document, [box])
    assert values(page) == pytest.approx([200, 300, 100], abs=0.01)  # repère global


def cartouche(page: Any) -> dict[str, str]:
    return dict(page.Template.EditableTexts)


def test_cartouche_rempli(bureau: Bureau) -> None:
    options = api.DrawingOptions(client="Mme Dupont", quote="D-2026-014")
    page = api.make_overall_drawing(bureau.doc, [bureau.furniture], options)
    texts = cartouche(page)
    written = set(texts.values())
    # Le message cite les cases du gabarit : utile si une version de FreeCAD les renomme.
    assert "1 : 10" in written and "D-2026-014" in written, texts
    # Case client, ou client écrit après le titre si le gabarit n'en a pas.
    assert any("Mme Dupont" in value for value in written), texts
    material = str(bureau.parts["P"].Material)
    assert any(material in value for value in written), "\n".join(
        f"{key} = {value!r}" for key, value in sorted(texts.items())
    )


def test_gabarit_francais_de_l_atelier(bureau: Bureau) -> None:
    options = api.DrawingOptions(client="Mme Dupont", quote="D-2026-014")
    page = api.make_overall_drawing(bureau.doc, [bureau.furniture], options)
    assert Path(page.Template.Template).name == "Menuiserie_A3_Landscape.svg"
    texts = cartouche(page)
    assert texts["client"] == "Mme Dupont", texts
    assert texts["quote"] == "D-2026-014", texts
    assert texts["scale"] == "1 : 10", texts
    assert texts["document_type"] == "Plan de l'ouvrage", texts
    assert str(bureau.parts["P"].Material) in texts["material"], texts


def test_cartouche_garde_les_saisies_a_la_relance(bureau: Bureau) -> None:
    doc = bureau.doc
    first = api.DrawingOptions(title="Bureau de Léa", client="Mme Dupont")
    page = api.make_overall_drawing(doc, [bureau.furniture], first)
    again = api.make_overall_drawing(doc, [bureau.furniture])
    assert again == page
    written = set(cartouche(again).values())
    assert any("Bureau de Léa" in value for value in written), cartouche(again)
    assert any("Mme Dupont" in value for value in written), cartouche(again)
    cleared = api.make_overall_drawing(doc, [bureau.furniture], api.DrawingOptions(client=""))
    assert not any("Mme Dupont" in value for value in cartouche(cleared).values())


def test_format_de_la_configuration(bureau: Bureau) -> None:
    parameters = App.ParamGet("User parameter:BaseApp/Preferences/Mod/Menuiserie")
    parameters.SetString("DrawingPageFormat", "a4")
    parameters.SetString("DrawingPageOrientation", "Portrait")
    try:
        page = api.make_overall_drawing(bureau.doc, [bureau.furniture])
        assert "A4" in page.Template.Template and "Portrait" in page.Template.Template
        parameters.SetString("DrawingPageFormat", "Z9")  # valeur abîmée : format par défaut
        parameters.SetString("DrawingPageOrientation", "")
        other = api.make_overall_drawing(bureau.doc, [bureau.parts["P"]])
        assert "A3" in other.Template.Template and "Landscape" in other.Template.Template
    finally:
        parameters.RemString("DrawingPageFormat")
        parameters.RemString("DrawingPageOrientation")


def test_changement_de_format_a_la_relance(bureau: Bureau) -> None:
    doc = bureau.doc
    page = api.make_overall_drawing(doc, [bureau.furniture])
    again = api.make_overall_drawing(doc, [bureau.furniture], api.DrawingOptions(page_format="A4"))
    assert again == page
    assert "A4" in again.Template.Template
    assert again.Scale == pytest.approx(0.05)  # le 1 : 10 ne tient plus sur A4
