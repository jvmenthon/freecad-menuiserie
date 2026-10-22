# SPDX-License-Identifier: LGPL-2.1-or-later
"""Export CSV de la liste de débit (J2b, C7 et C8)."""

from __future__ import annotations

import csv
import io

import pytest

from freecad.menuiserie.core.cutlist import (
    FRENCH_CSV,
    INTERNATIONAL_CSV,
    CsvDialect,
    CutList,
    Hardware,
    HardwareKind,
    additions_remark,
    build_cut_list,
    format_number,
    neutralize_formula,
    table_sections,
    to_csv,
)
from freecad.menuiserie.core.part_model import Allowances, GrainDirection
from tests.unit.aides_debit import entry, plywood

TENON = Allowances(60.0, 0.0, 0.0)


def sample() -> CutList:
    entries = [
        entry("M10", (1200, 95.5, 22), quantity=2, furniture="Caisson"),
        entry("M2", (800, 100, 22.5), additions=TENON, grain=GrainDirection.NONE),
        plywood(),
    ]
    return build_cut_list(entries, [Hardware(HardwareKind.DOWEL, 8.0, 35.0, 6)])


def rows(text: str, delimiter: str = ",") -> list[list[str]]:
    return list(csv.reader(io.StringIO(text, newline=""), delimiter=delimiter))


# --- C7 : structure et dialecte -----------------------------------------------------------


def test_dialecte_international_par_defaut() -> None:  # C7'
    text = to_csv(sample())
    assert text == to_csv(sample(), INTERNATIONAL_CSV)
    assert text.endswith("\r\n")
    assert "\n" not in text.replace("\r\n", "")
    assert text.encode(INTERNATIONAL_CSV.encoding).startswith(b"\xef\xbb\xbf")
    assert (INTERNATIONAL_CSV.delimiter, INTERNATIONAL_CSV.decimal_separator) == (",", ".")
    assert (INTERNATIONAL_CSV.encoding, INTERNATIONAL_CSV.line_terminator) == ("utf-8-sig", "\r\n")


def test_structure_en_trois_blocs() -> None:
    table = rows(to_csv(sample()))
    blank = [i for i, row in enumerate(table) if not row]
    assert len(blank) == 2
    lines = table[: blank[0]]
    totals = table[blank[0] + 1 : blank[1]]
    hardware = table[blank[1] + 1 :]
    assert lines[0][:2] == ["Repère", "Qté"]
    assert len(lines) == 4
    assert totals[0] == ["Totaux par matériau et épaisseur"]
    assert totals[-1][0] == "Total général"
    assert hardware == [
        ["Fournitures"],
        ["Fourniture", "Diamètre (mm)", "Longueur (mm)", "Qté"],
        ["Tourillon", "8", "35", "6"],
    ]


def test_lignes_de_donnees_internationales() -> None:
    table = rows(to_csv(sample()))
    assert table[1] == [
        *["M2", "1", "800", "100", "22.5", "880", "105", "22.5", "Chene", "Sans fil", ""],
        *["0.0021", "1.48", "", "Ajouts compris (L / l / e) : +60 / +0 / +0 mm"],
    ]
    assert table[2][10] == "Caisson"
    assert table[2][5:8] == ["1220", "100.5", "22"]
    assert table[3][:2] == ["P1", "1"]  # contreplaqué : surface renseignée
    assert table[3][13] == "0.240"


def test_dialecte_francais_disponible() -> None:
    text = to_csv(sample(), FRENCH_CSV)
    table = rows(text, ";")
    assert (FRENCH_CSV.delimiter, FRENCH_CSV.decimal_separator) == (";", ",")
    assert table[1][4] == "22,5"
    assert table[1][11] == "0,0021"
    assert ";" in text.splitlines()[0]


def test_dialecte_parametrable() -> None:
    tabs = CsvDialect("\t", ".", "utf-16", "\n")
    text = to_csv(sample(), tabs)
    assert "\r" not in text
    assert text.splitlines()[0].count("\t") == 14


def test_en_tetes_traduits() -> None:
    text = to_csv(sample(), translate=lambda s: f"<{s}>")
    assert text.startswith("<Repère>,<Qté>,")
    assert "<Total général>" in text
    assert "<Tourillon>" in text
    assert "<Sans fil>" in text


def test_liste_vide_et_sans_fournitures() -> None:
    assert len(rows(to_csv(build_cut_list([])))) == 1
    table = rows(to_csv(build_cut_list([entry()])))
    assert [] in table
    assert table[-1][0] == "Total général"


# --- C7 : injection de formule -------------------------------------------------------------


@pytest.mark.parametrize("start", ["=", "+", "-", "@", "\t", "\r"])
def test_neutralisation_des_formules(start: str) -> None:
    assert neutralize_formula(f"{start}SOMME(A1)") == f"'{start}SOMME(A1)"


@pytest.mark.parametrize("text", ["M1", "", "a=b", "'=", " =1"])
def test_texte_sans_formule_inchange(text: str) -> None:
    assert neutralize_formula(text) == text


def test_repere_ensemble_et_materiau_neutralises_dans_le_csv() -> None:
    evil = build_cut_list([entry('=HYPERLINK("http://x")', furniture="@cmd", material="-chene")])
    table = rows(to_csv(evil))
    assert table[1][0] == '\'=HYPERLINK("http://x")'
    assert table[1][8] == "'-chene"
    assert table[1][10] == "'@cmd"
    assert table[-1][0] == "Total général"
    assert "'-chene" in [row[0] for row in table if row]


def test_cellule_avec_separateur_ou_saut_de_ligne_protegee() -> None:
    table = rows(to_csv(build_cut_list([entry("A;B\nC")])))
    assert table[1][0] == "A;B\nC"


# --- C8 : nombres affichés -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "text"),
    [(800.0, "800"), (22.5, "22,5"), (22.54, "22,5"), (0.04, "0"), (100.06, "100,1"), (7.0, "7")],
)
def test_format_des_cotes(value: float, text: str) -> None:
    assert format_number(value, 1, FRENCH_CSV) == text
    assert format_number(value, 1) == text.replace(",", ".")  # défaut : international


def test_decimales_fixes_volume_surface_masse() -> None:
    line = rows(to_csv(build_cut_list([plywood("P1", (2500, 1220, 18))])))[1]
    assert line[11:14] == ["0.0549", "32.94", "3.050"]  # m³ à 4, kg à 2, m² à 3


# --- remarque ------------------------------------------------------------------------------


def test_remarque_des_ajouts() -> None:
    (with_tenon,) = build_cut_list([entry(additions=Allowances(60.0, 0.0, 2.25))]).lines
    (without,) = build_cut_list([entry()]).lines
    assert additions_remark(with_tenon, str) == "Ajouts compris (L / l / e) : +60 / +0 / +2.2 mm"
    assert additions_remark(with_tenon, str, FRENCH_CSV).endswith("+2,2 mm")
    assert additions_remark(without, str) == ""


# --- blocs communs au CSV et à la feuille (J2c) ---------------------------------------------


def test_blocs_du_tableau_lignes_totaux_fournitures() -> None:
    lines, totals, hardware = table_sections(sample(), str, INTERNATIONAL_CSV)
    assert (lines.title, totals.title, hardware.title) == (
        "",
        "Totaux par matériau et épaisseur",
        "Fournitures",
    )
    assert len(lines.rows) == 3
    assert lines.rows[0][:2] == ("M2", "1")
    assert "." in lines.rows[0][11]
    assert lines.text_columns == {0, 8, 9, 10, 14}
    assert totals.rows[-1][0] == "Total général"
    assert hardware.rows == (("Tourillon", "8", "35", "6"),)


def test_liste_vide_un_seul_bloc() -> None:
    [only] = table_sections(build_cut_list([]), str)
    assert only.rows == ()
    assert len(only.header) == 15
