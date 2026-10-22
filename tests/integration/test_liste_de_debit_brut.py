# SPDX-License-Identifier: LGPL-2.1-or-later
"""Épaisseurs standards de brut dans la liste de débit (J2, § 10.4, critère B3, ADR 0015).

Une pièce de chêne de 18 mm est débitée dans du brut de 27 mm, une pièce de pin de 18 mm dans du
brut de 22 mm, un contreplaqué de 18 mm reste à 18 mm : dans la feuille, le CSV, le PDF (via son
HTML) et les totaux.
"""

from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Any

import pytest

from tests.integration.debit import kinds, row_of, text

pytestmark = pytest.mark.integration

pytest.importorskip("FreeCAD")
api = pytest.importorskip("freecad.menuiserie.api")

THICKNESS_COLUMN = "H"  # « Épaisseur de débit (mm) » de la feuille
CSV_THICKNESS_INDEX = 7
SIZE = (800.0, 100.0, 18.0)


def make(doc: Any, mark: str, material: str, size: tuple[float, float, float] = SIZE) -> None:
    api.make_wood_part(*size, material, mark=mark, doc=doc)
    doc.recompute()


@pytest.fixture
def trio(document: Any) -> Any:
    make(document, "C1", "chene")
    make(document, "P1", "pin-sylvestre", (700.0, 100.0, 18.0))
    make(document, "X1", "cp-bouleau", (600.0, 400.0, 18.0))
    return document


def rough_thicknesses(cut_list: Any) -> dict[str, float]:
    return {line.display_mark: line.rough.thickness for line in cut_list.lines}


def test_epaisseurs_de_debit_dans_la_liste(trio: Any) -> None:
    cut_list = api.cut_list_of(trio)
    assert rough_thicknesses(cut_list) == {"C1": 27.0, "P1": 22.0, "X1": 18.0}
    assert kinds(cut_list) == []


def test_epaisseurs_de_debit_dans_les_totaux(trio: Any) -> None:
    cut_list = api.cut_list_of(trio)
    thickness_of = {total.material_id: total.thickness for total in cut_list.totals}
    assert thickness_of == {"chene": 27.0, "pin-sylvestre": 22.0, "cp-bouleau": 18.0}
    oak = next(total for total in cut_list.totals if total.material_id == "chene")
    line = next(line for line in cut_list.lines if line.material_id == "chene")
    assert oak.volume_m3 == pytest.approx(line.rough.length * line.rough.width * 27.0 / 1e9)


def test_epaisseurs_de_debit_dans_la_feuille(trio: Any) -> None:
    sheet = api.make_cut_list(trio)
    for mark, expected in {"C1": 27.0, "P1": 22.0, "X1": 18.0}.items():
        row = row_of(sheet, mark)
        assert float(text(sheet, f"{THICKNESS_COLUMN}{row}")) == pytest.approx(expected)


def test_epaisseurs_de_debit_dans_le_csv(trio: Any, tmp_path: Path) -> None:
    path = tmp_path / "debit.csv"
    api.export_cut_list_csv(trio, path)
    rows = list(csv.reader(io.StringIO(path.read_text(encoding="utf-8-sig"), newline="")))
    by_mark = {row[0]: float(row[CSV_THICKNESS_INDEX]) for row in rows[1:4]}
    assert by_mark == {"C1": 27.0, "P1": 22.0, "X1": 18.0}


def test_epaisseurs_de_debit_dans_le_pdf(trio: Any) -> None:
    html = api.cut_list_html(trio)
    assert ">27<" in html
    assert ">22<" in html
    assert ">18<" in html


def test_avertissement_au_dela_du_plus_gros_brut(document: Any) -> None:
    make(document, "G1", "chene", (800.0, 100.0, 98.0))
    cut_list = api.cut_list_of(document)
    (line,) = cut_list.lines
    assert line.rough.thickness == pytest.approx(101.0)
    assert kinds(cut_list) == ["RoughThicknessOverStandard"]
    assert "au-delà des épaisseurs de brut du Chêne" in cut_list.warnings[0].message
