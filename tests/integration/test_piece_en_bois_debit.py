# SPDX-License-Identifier: LGPL-2.1-or-later
"""Liste de débit et pièce en bois (PD-c, critères C1 à C5 de ``docs/specs/piece-en-bois.md``).

Collecte dans le document, la sélection, un conteneur et par lien ; liste vivante qui suit le corps
(ADR 0013) ; regroupement de deux pièces identiques, jamais avec une pièce de bois de mêmes cotes ;
remarque « forme » ; numérotation des repères.
"""

from __future__ import annotations

from typing import Any

import pytest

from freecad.menuiserie.core import cutlist as core
from freecad.menuiserie.core.cutlist import to_csv
from tests.integration.debit import link, text
from tests.integration.test_piece_en_bois import box, leg

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
api = pytest.importorskip("freecad.menuiserie.api")
cutlist_object = pytest.importorskip("freecad.menuiserie.features.cutlist_object")
cutlist_thumbnail = pytest.importorskip("freecad.menuiserie.features.cutlist_thumbnail")

REMARK_COLUMN = "O"
FINISHED_LENGTH = "C"
SIZE = (200.0, 100.0, 50.0)


def shaped_box(doc: Any, mark: str = "", name: str = "Boite") -> Any:
    """Pièce en bois d'une boîte de ``SIZE``, recalculée."""
    part = api.make_shaped_part(box(doc, SIZE, name), mark=mark)
    doc.recompute()
    return part


def twin(doc: Any, part: Any, mark: str = "") -> Any:
    """Pièce de bois de mêmes cotes, matériau, fil et surcotes que la pièce en bois ``part``."""
    wood = api.make_wood_part(
        part.Length.Value,
        part.Width.Value,
        part.Thickness.Value,
        part.MaterialId,
        mark=mark,
        doc=doc,
    )
    wood.GrainDirection = part.GrainDirection
    for name in ("LengthAllowance", "WidthAllowance", "ThicknessAllowance"):
        setattr(wood, name, getattr(part, name))
    doc.recompute()
    return wood


def sheet_row(sheet: Any, mark: str) -> int:
    """Numéro de la ligne de la feuille dont la colonne A cite le repère ``mark``."""
    for row in range(1, 80):
        if mark in text(sheet, f"A{row}").split(", "):
            return row
    raise AssertionError(f"repère {mark} absent de la feuille")


# --- C1 : collecte -------------------------------------------------------------------------


def test_collecte_du_document(document: Any) -> None:
    shaped_box(document, "P1")
    [line] = api.cut_list_of(document).lines
    assert (line.marks, line.quantity) == (("P1",), 1)
    assert line.shape is not None


def test_collecte_de_la_selection(document: Any) -> None:
    first, _second = shaped_box(document, "P1"), shaped_box(document, "P2", "Autre")
    [line] = api.cut_list_of(document, [first]).lines
    assert line.marks == ("P1",)


def test_collecte_dans_un_conteneur(document: Any) -> None:
    part = shaped_box(document, "P1")
    container = document.addObject("App::Part", "Ensemble")
    container.addObject(part)
    document.recompute()
    [line] = api.cut_list_of(document, [container]).lines
    assert (line.marks, line.quantity) == (("P1",), 1)


def test_collecte_par_lien(document: Any) -> None:
    part = shaped_box(document, "P1")
    link(document, part)
    [line] = api.cut_list_of(document).lines
    assert line.quantity == 2
    [counted] = api.cut_list_of(document, [document.getObject("Lien")]).lines
    assert counted.quantity == 1


# --- C2 : cotes finies = encombrement, volume à acheter ------------------------------------


def test_cotes_finies_et_volume_a_acheter(document: Any) -> None:
    part = shaped_box(document, "P1")
    [line] = api.cut_list_of(document).lines
    finished = (line.finished.length, line.finished.width, line.finished.thickness)
    assert finished == pytest.approx((part.Length.Value, part.Width.Value, part.Thickness.Value))
    rough = line.rough
    assert rough.length == pytest.approx(finished[0] + part.LengthAllowance.Value)
    assert line.volume_m3(rough=True) == pytest.approx(
        rough.length * rough.width * rough.thickness / 1e9
    )
    assert line.volume_m3(rough=True) > line.volume_m3()


# --- C1 : liste vivante --------------------------------------------------------------------


def test_la_liste_vivante_suit_l_allongement_du_pad(document: Any) -> None:
    body = leg(document)
    part = api.make_shaped_part(body, mark="P1")
    document.recompute()
    sheet = api.make_cut_list(document)
    row = sheet_row(sheet, "P1")
    assert float(text(sheet, f"{FINISHED_LENGTH}{row}")) == pytest.approx(720.0, abs=0.1)
    body.Group[1].Length = 1000.0
    document.recompute()
    assert float(text(sheet, f"{FINISHED_LENGTH}{sheet_row(sheet, 'P1')}")) == pytest.approx(
        1000.0, abs=0.1
    )
    assert part.Length.Value == pytest.approx(1000.0, abs=0.1)
    live = cutlist_object.find_cut_list(document)
    assert part in live.Sources


def test_la_liste_vivante_voit_une_nouvelle_piece_en_bois(document: Any) -> None:
    shaped_box(document, "P1")
    sheet = api.make_cut_list(document)
    shaped_box(document, "P2", "Autre")
    document.recompute()
    assert sheet_row(sheet, "P2") > 0


# --- C3 : remarque et miniature ------------------------------------------------------------


def test_remarque_forme_dans_la_feuille(document: Any) -> None:
    shaped_box(document, "P1")
    wood = api.make_wood_part(500.0, 80.0, 22.0, "chene", mark="M1", doc=document)
    document.recompute()
    sheet = api.make_cut_list(document)
    assert "forme" in text(sheet, f"{REMARK_COLUMN}{sheet_row(sheet, 'P1')}")
    assert text(sheet, f"{REMARK_COLUMN}{sheet_row(sheet, wood.Mark)}") == ""


def test_remarque_forme_dans_le_csv_et_le_html(document: Any) -> None:
    shaped_box(document, "P1")
    assert "forme" in to_csv(api.cut_list_of(document))
    assert "forme (cotes = encombrement)" in api.cut_list_html(document)


def test_miniature_de_l_encombrement(document: Any) -> None:
    shaped_box(document, "P1")
    cut_list = api.cut_list_of(document)
    thumbnails = cutlist_thumbnail.thumbnails_of(document, cut_list)
    [svg] = thumbnails.values()
    assert svg.lstrip().startswith("<svg")


def test_miniature_de_la_forme_reelle(document: Any) -> None:
    """Un cylindre n'a pas la miniature de sa boîte L x l x e : elle montre sa forme (facettes)."""
    cylinder = document.addObject("Part::Cylinder", "Rond")
    cylinder.Radius, cylinder.Height = 40.0, 300.0
    api.make_shaped_part(cylinder, mark="R1")
    document.recompute()
    cut_list = api.cut_list_of(document)
    [svg] = cutlist_thumbnail.thumbnails_of(document, cut_list).values()
    size = cut_list.lines[0].finished
    boxed = core.thumbnail_svg(core.box_faces(size.length, size.width, size.thickness))
    assert svg.count("<path ") > boxed.count("<path ")


# --- C4 : regroupement ---------------------------------------------------------------------


def test_deux_pieces_identiques_regroupees(document: Any) -> None:
    shaped_box(document, "P1")
    shaped_box(document, "P2", "Autre")
    [line] = api.cut_list_of(document).lines
    assert (line.quantity, line.marks) == (2, ("P1", "P2"))


def test_pas_de_regroupement_avec_une_piece_de_bois(document: Any) -> None:
    part = shaped_box(document, "P1")
    twin(document, part, "P2")
    lines = api.cut_list_of(document).lines
    assert sorted(line.quantity for line in lines) == [1, 1]
    assert {line.shape is None for line in lines} == {True, False}


# --- C5 : numérotation ---------------------------------------------------------------------


def test_numerotation_des_pieces_en_bois(document: Any) -> None:
    first, second = shaped_box(document), shaped_box(document, name="Autre")
    wood = twin(document, first)
    written = api.number_marks(document)
    assert first.Mark == second.Mark != ""
    assert wood.Mark not in ("", first.Mark)
    assert set(written) == {first.Name, second.Name, wood.Name}
