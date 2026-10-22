# SPDX-License-Identifier: LGPL-2.1-or-later
"""Miniatures de la liste de débit sur de vrais documents (demande de jv du 2026-10-22,
critères A1 et A2) : la forme usinée (tenon, queue d'aronde) n'est pas la boîte simple ; repli sur
la boîte de débit pour une pièce invalide ; HTML autonome ; 200 pièces en moins de 2 secondes.
Sans interface : tout est calculé par ``features/`` et ``core/`` (Qt n'intervient qu'à l'affichage).
"""

from __future__ import annotations

import re
import time
from typing import Any

import pytest

from tests.integration.cadre import Cadre
from tests.integration.debit import part
from tests.integration.types_assemblages import DOVETAIL, build

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
api = pytest.importorskip("freecad.menuiserie.api")
core = pytest.importorskip("freecad.menuiserie.core.cutlist")
thumbnail = pytest.importorskip("freecad.menuiserie.features.cutlist_thumbnail")

OAK = (184, 135, 90)  # couleur du chêne dans la bibliothèque intégrée
BUDGET_S = 2.0
PIECES = 200


def box_of(line: Any, color: tuple[int, int, int] = OAK) -> str:
    rough = line.rough
    svg: str = core.thumbnail_svg(core.box_faces(rough.length, rough.width, rough.thickness), color)
    return svg


def line_of(cut_list: Any, mark: str) -> Any:
    return next(line for line in cut_list.lines if mark in line.marks)


def paths(svg: str) -> int:
    return svg.count("<path ")


def test_une_piece_avec_tenon_n_est_pas_la_boite_simple(cadre: Cadre) -> None:
    api.make_mortise_tenon(cadre.parts["M1"], cadre.parts["T1"], tenon_length=30)
    cut_list = api.cut_list_of(cadre.doc)
    thumbnails = thumbnail.thumbnails_of(cadre.doc, cut_list)
    line = line_of(cut_list, "T1")
    assert line.additions.length == pytest.approx(30)
    svg = thumbnails[line.source]
    assert svg != box_of(line)
    assert paths(svg) > paths(box_of(line))  # tenon : faces et arêtes en plus
    assert svg.startswith("<svg ")


def test_queue_d_aronde_visible(document: Any) -> None:
    montage = build(document, DOVETAIL)
    cut_list = api.cut_list_of(document)
    thumbnails = thumbnail.thumbnails_of(document, cut_list)
    assert len(thumbnails) == len(cut_list.lines)
    for line in cut_list.lines:
        assert paths(thumbnails[line.source]) > paths(box_of(line))  # queues et embrèvements
    assert montage.host is not None


def test_piece_non_usinee_boite_de_debit(document: Any) -> None:
    part(document, "M1")
    cut_list = api.cut_list_of(document)
    (line,) = cut_list.lines
    assert thumbnail.thumbnails_of(document, cut_list) == {line.source: box_of(line)}


def test_piece_usinee_invalide_repli_sur_la_boite(cadre: Cadre) -> None:
    api.make_mortise_tenon(cadre.parts["M1"], cadre.parts["T1"], tenon_length=30)
    machined = cadre.machined("T1")
    machined.touch()  # à recalculer : sa forme n'est pas fiable
    cut_list = api.cut_list_of(cadre.doc)
    line = line_of(cut_list, "T1")
    assert thumbnail.thumbnails_of(cadre.doc, cut_list)[line.source] == box_of(line)


def test_piece_supprimee_apres_le_calcul_repli(cadre: Cadre) -> None:
    cut_list = api.cut_list_of(cadre.doc)
    line = line_of(cut_list, "M1")
    cadre.doc.removeObject(cadre.parts["M1"].Name)
    assert thumbnail.thumbnail_of(cadre.doc, line) == box_of(line)


def test_une_miniature_par_groupe(document: Any) -> None:
    api.make_wood_part(800.0, 100.0, 22.0, "chene", mark="A", doc=document)
    api.make_wood_part(800.0, 100.0, 22.0, "chene", mark="B", doc=document)
    api.make_wood_part(500.0, 100.0, 22.0, "chene", mark="C", doc=document)
    document.recompute()
    cut_list = api.cut_list_of(document)
    assert [line.quantity for line in cut_list.lines] == [2, 1]
    assert len(thumbnail.thumbnails_of(document, cut_list)) == 2


def test_couleur_du_materiau(document: Any) -> None:
    api.make_wood_part(800.0, 100.0, 22.0, "noyer", mark="N", doc=document)
    document.recompute()
    cut_list = api.cut_list_of(document)
    (svg,) = thumbnail.thumbnails_of(document, cut_list).values()
    assert svg == box_of(cut_list.lines[0], (107, 74, 51))  # noyer #6B4A33
    assert svg != box_of(cut_list.lines[0], OAK)


def test_html_une_image_par_ligne_et_aucune_url_externe(cadre: Cadre) -> None:
    cadre.assemble()
    html = api.cut_list_html(cadre.doc)
    lines = api.cut_list_of(cadre.doc).lines
    assert html.count("<img ") == len(lines) == 2
    assert html.count('src="data:image/svg+xml;base64,') == 2
    assert not re.search(r"(?i)(https?:|file:|ftp:|@import|url\()", html)
    assert "<script" not in html
    assert "<th>Miniature</th><th>Repère</th>" in html


def test_apercu_lecture_seule(cadre: Cadre) -> None:
    cadre.assemble()
    cadre.doc.recompute()
    before = (len(cadre.doc.Objects), cadre.doc.UndoCount, [o.Name for o in cadre.doc.Objects])
    first = api.cut_list_html(cadre.doc)
    after = (len(cadre.doc.Objects), cadre.doc.UndoCount, [o.Name for o in cadre.doc.Objects])
    assert after == before
    assert not [obj.Name for obj in cadre.doc.Objects if "Touched" in obj.State]
    assert re.sub(r"Date : [\d: -]+", "", api.cut_list_html(cadre.doc)) == re.sub(
        r"Date : [\d: -]+", "", first
    )


def test_objet_d_un_autre_document_refuse(document: Any) -> None:
    other = App.newDocument("Autre")
    try:
        board = api.make_wood_part(800.0, 100.0, 22.0, "chene", doc=other)
        with pytest.raises(ValueError, match="autre document"):
            api.cut_list_html(document, [board])
    finally:
        App.closeDocument(other.Name)


def test_deux_cents_pieces_en_moins_de_deux_secondes(document: Any) -> None:
    """Pièces usinées de formes distinctes (une brute par ligne) : miniatures en < 2 s."""
    from freecad.menuiserie.features.machined_part import ensure_machined_part

    for index in range(PIECES):
        blank = api.make_wood_part(
            500.0 + index, 100.0 + index % 7, 22.0, "chene", mark=f"P{index}", doc=document
        )
        ensure_machined_part(blank)
    document.recompute()
    cut_list = api.cut_list_of(document)
    assert len(cut_list.lines) == PIECES
    started = time.perf_counter()
    thumbnails = thumbnail.thumbnails_of(document, cut_list)
    elapsed = time.perf_counter() - started
    assert len(thumbnails) == PIECES
    assert all(paths(svg) >= 6 for svg in thumbnails.values())
    assert elapsed < BUDGET_S, f"{PIECES} miniatures en {elapsed:.2f} s"
