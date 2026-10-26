# SPDX-License-Identifier: LGPL-2.1-or-later
"""Liste de débit et pièce en bois (PD-c, C2 à C5) : empreinte de forme, regroupement, remarque,
CSV et HTML, numérotation."""

from __future__ import annotations

import csv
import io

import pytest

from freecad.menuiserie.core.cutlist import (
    NO_ADDITIONS,
    CutEntry,
    CutList,
    InvalidCutEntryError,
    assign_marks,
    build_cut_list,
    group_key,
    line_remark,
    to_csv,
    to_html,
)
from freecad.menuiserie.core.part_model import Allowances
from freecad.menuiserie.core.shaped import ShapeSignature
from tests.unit.aides_debit import entry, record

SIZE = (800.0, 100.0, 22.0)
SHAPE = ShapeSignature(1.5e6, 4.0e5, 12)
TENON = Allowances(60.0, 0.0, 0.0)


def shaped(
    mark: str = "M1",
    shape: ShapeSignature = SHAPE,
    quantity: int = 1,
    additions: Allowances = NO_ADDITIONS,
) -> CutEntry:
    """Entrée d'une pièce en bois de cotes finies ``SIZE`` (l'encombrement)."""
    return CutEntry(record(mark, SIZE), quantity, additions, shape=shape)


def remark_of(cut_list: CutList) -> str:
    return line_remark(cut_list.lines[0], str)


# --- C4 : regroupement -------------------------------------------------------------------


def test_champ_facultatif_en_fin() -> None:
    assert entry().shape is None
    (line,) = build_cut_list([entry()]).lines
    assert line.shape is None


def test_deux_pieces_en_bois_identiques_regroupees() -> None:
    (line,) = build_cut_list([shaped("M1"), shaped("M2")]).lines
    assert (line.quantity, line.marks, line.shape) == (2, ("M1", "M2"), SHAPE)


def test_jamais_regroupee_avec_une_piece_de_bois() -> None:
    result = build_cut_list([shaped("M1"), entry("M2", SIZE)])
    assert sorted(line.quantity for line in result.lines) == [1, 1]
    assert {line.shape is None for line in result.lines} == {True, False}


def test_empreintes_differentes_non_regroupees() -> None:
    other = ShapeSignature(1.4e6, 4.0e5, 12)
    assert len(build_cut_list([shaped("M1"), shaped("M2", other)]).lines) == 2
    more_faces = ShapeSignature(1.5e6, 4.0e5, 14)
    assert len(build_cut_list([shaped("M1"), shaped("M2", more_faces)]).lines) == 2


def test_empreintes_egales_aux_arrondis_pres() -> None:
    near = ShapeSignature(1.50001e6, 4.00001e5, 12)
    assert len(build_cut_list([shaped("M1"), shaped("M2", near)]).lines) == 1


def test_empreinte_invalide_refusee() -> None:
    with pytest.raises(InvalidCutEntryError):
        CutEntry(record(), shape="forme")  # type: ignore[arg-type]


# --- C2 : cotes et volume à acheter --------------------------------------------------------


def test_cotes_de_debit_et_volume_sur_l_encombrement() -> None:
    (line,) = build_cut_list([shaped(quantity=2, additions=TENON)]).lines
    assert line.finished.length == 800.0
    assert line.additions == TENON
    assert line.rough.length == pytest.approx(800.0 + 60.0 + line.allowances.length)
    expected = line.rough.length * line.rough.width * line.rough.thickness * 2 / 1e9
    assert line.volume_m3(rough=True) == pytest.approx(expected)
    assert line.mass_kg(rough=True) == pytest.approx(expected * 710.0)


# --- C3 : remarque -------------------------------------------------------------------------


def test_remarque_forme() -> None:
    assert "forme" in remark_of(build_cut_list([shaped()]))
    assert remark_of(build_cut_list([entry()])) == ""


def test_remarque_forme_et_ajouts() -> None:
    text = remark_of(build_cut_list([shaped(additions=TENON)]))
    assert text.startswith("forme") and "Ajouts compris" in text and " ; " in text


def test_csv_porte_la_mention() -> None:
    cut_list = build_cut_list([shaped(), entry("M2", (500, 80, 22))])
    table = list(csv.reader(io.StringIO(to_csv(cut_list))))
    remarks = {row[0]: row[14] for row in table[1:3]}
    assert "forme" in remarks["M1"]
    assert remarks["M2"] == ""


def test_html_porte_la_mention() -> None:
    assert "forme (cotes = encombrement)" in to_html(build_cut_list([shaped()]))


# --- C5 : numérotation ---------------------------------------------------------------------


def test_numerotation_distingue_forme_et_bois() -> None:
    entries = [shaped(""), shaped(""), entry("", SIZE)]
    marks = assign_marks(entries)
    assert set(marks.values()) == {"M1", "M2"}
    assert marks[group_key(entries[0])] == marks[group_key(entries[1])]
    assert marks[group_key(entries[0])] != marks[group_key(entries[2])]
