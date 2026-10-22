# SPDX-License-Identifier: LGPL-2.1-or-later
"""Feuille de calcul « Liste de débit » et export CSV (J2c, critères S1 à S7 de ``docs/specs/J2``).

Création et mise à jour, colonnes de l'utilisateur conservées, mise en page, aucune formule,
pas de recalcul automatique, export atomique, annulation, réouverture sans proxy.
"""

from __future__ import annotations

import csv
import io
import os
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from tests.integration.aides import touched_names
from tests.integration.bureau import Bureau
from tests.integration.cadre import Cadre
from tests.integration.debit import (
    COLUMNS,
    SHEET_NAME,
    column,
    line_of,
    part,
    row_of,
    sheets,
    table,
    text,
)

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
api = pytest.importorskip("freecad.menuiserie.api")

Reopen = Callable[[Any], Any]
NUMERIC = "BCDEFGHLMN"  # colonnes de nombres (la colonne N, surface, est vide hors panneaux)
HEADERS = [
    "Repère",
    "Qté",
    "Longueur finie (mm)",
    "Largeur finie (mm)",
    "Épaisseur finie (mm)",
    "Longueur de débit (mm)",
    "Largeur de débit (mm)",
    "Épaisseur de débit (mm)",
    "Matériau",
    "Fil",
    "Ensemble",
    "Volume de débit (m³)",
    "Masse (kg)",
    "Surface (m²)",
    "Remarque",
]
HEADER_ROW = 5
FIRST_LINE_ROW = 6


def cut_sheet(doc: Any, objects: list[Any] | None = None) -> Any:
    """Feuille de la liste de débit, créée ou mise à jour."""
    return api.make_cut_list(doc, objects)


def contents(sheet: Any) -> dict[str, str]:
    """Contenu brut des cellules A à O non vides (lignes 1 à 80)."""
    found = {}
    for row in range(1, 81):
        for letter in COLUMNS:
            content = str(sheet.getContents(f"{letter}{row}"))
            if content:
                found[f"{letter}{row}"] = content
    return found


# --- S1 : création et mise à jour -----------------------------------------------------------


def test_creation_de_la_feuille_marquee_et_sans_proxy(document: Any) -> None:
    part(document, "M1")
    sheet = cut_sheet(document)
    assert (sheet.TypeId, sheet.Name, sheet.Label) == (
        "Spreadsheet::Sheet",
        SHEET_NAME,
        "Liste de débit",
    )
    assert sheet.MenuiserieCutList is True
    assert sheet.getTypeIdOfProperty("MenuiserieCutList") == "App::PropertyBool"
    assert sheet.getEditorMode("MenuiserieCutList") == ["Hidden"]
    assert "Proxy" not in sheet.PropertiesList
    assert sheet.ExpressionEngine == []
    assert sheet.OutList == []  # aucune dépendance : le recalcul du meuble n'est pas touché
    assert sheets(document) == [sheet]


def test_deuxieme_appel_met_a_jour_la_meme_feuille(document: Any) -> None:
    part(document, "M1")
    first = cut_sheet(document)
    part(document, "M2")
    second = cut_sheet(document)
    assert second == first
    assert len(sheets(document)) == 1
    assert "M2" in column(second)


def test_feuille_renommee_retrouvee_par_sa_marque(document: Any) -> None:
    part(document, "M1")
    ordinary = document.addObject("Spreadsheet::Sheet", "Autre")
    ordinary.set("A1", "'à moi")
    sheet = cut_sheet(document)
    sheet.Label = "Mon débit"
    part(document, "M2")
    assert cut_sheet(document) == sheet
    assert len(sheets(document)) == 2
    assert text(ordinary, "A1") == "à moi"  # une feuille ordinaire n'est jamais touchée
    assert text(sheet, "A1") == "Liste de débit"


def test_une_seule_transaction(document: Any) -> None:
    document.UndoMode = 1
    part(document, "M1")
    before = document.UndoCount
    cut_sheet(document)
    assert document.UndoCount == before + 1
    assert "Liste de débit" in document.UndoNames
    cut_sheet(document)
    assert document.UndoCount == before + 2


# --- S2 : colonnes de l'utilisateur conservées ----------------------------------------------


def test_cellules_a_droite_conservees_et_anciennes_lignes_effacees(document: Any) -> None:
    marks = ["M1", "M2", "M3", "M4"]
    parts = [part(document, mark) for mark in marks]
    sheet = cut_sheet(document)
    sheet.set("P1", "'ma note")
    sheet.set("Q6", "=B6*2")
    sheet.set("AB3", "12")
    sheet.setStyle("P1", "italic")
    for obj in parts[1:]:
        document.removeObject(obj.Name)
    document.recompute()
    cut_sheet(document)
    formula = sheet.getContents("Q6").replace(" ", "")  # FreeCAD normalise l'expression
    assert (text(sheet, "P1"), formula, sheet.getContents("AB3")) == (
        "ma note",
        "=B6*2",
        "12",
    )
    assert "italic" in sheet.getStyle("P1")
    assert column(sheet)[HEADER_ROW] == "M1"
    leftover = [a for a, c in contents(sheet).items() if c in ("'M2", "'M3", "'M4")]
    assert leftover == []


# --- S3 : mise en page ----------------------------------------------------------------------


def test_tete_date_portee_et_en_tetes(document: Any) -> None:
    board = part(document, "M1")
    sheet = cut_sheet(document)
    assert text(sheet, "A1") == "Liste de débit"
    assert re.fullmatch(r"Calculée le \d{4}-\d{2}-\d{2} \d{2}:\d{2} ;.*", text(sheet, "A2"))
    assert "pas mise à jour automatiquement" in text(sheet, "A2")
    assert text(sheet, "A3") == "Tout le document"
    assert table(sheet)[HEADER_ROW - 1] == HEADERS
    assert text(cut_sheet(document, [board]), "A3") == "Sélection : 1 objet"
    second = part(document, "M2")
    assert text(cut_sheet(document, [board, second]), "A3") == "Sélection : 2 objets"


def test_lignes_alignement_gras_et_largeurs(bureau: Bureau) -> None:
    doc = bureau.doc
    cut_list = api.cut_list_of(doc)
    sheet = cut_sheet(doc)
    rows = table(sheet)
    for index, line in enumerate(cut_list.lines):
        cells = rows[FIRST_LINE_ROW - 1 + index]
        assert cells[0] == line.mark
        assert int(cells[1]) == line.quantity
        sizes = (*line.finished.__dict__.values(), *line.rough.__dict__.values())
        assert [float(cell) for cell in cells[2:8]] == pytest.approx(sizes)
        assert cells[8] == line.material_name
        assert cells[10] == "Bureau"
        assert float(cells[11]) == pytest.approx(line.volume_m3(rough=True), abs=5e-5)
        assert float(cells[12]) == pytest.approx(line.mass_kg(rough=True), abs=5e-3)
        assert cells[13] == ""  # surface : panneaux seulement
    assert "bold" in sheet.getStyle("A1")
    assert all("bold" in sheet.getStyle(f"{letter}{HEADER_ROW}") for letter in COLUMNS)
    for letter in NUMERIC:
        assert "right" in sheet.getAlignment(f"{letter}{FIRST_LINE_ROW}"), letter
    assert "right" not in (sheet.getAlignment(f"A{FIRST_LINE_ROW}") or "")
    assert all(sheet.getColumnWidth(letter) > 0 for letter in COLUMNS)
    assert sheet.getColumnWidth("O") > sheet.getColumnWidth("B")


def test_totaux_fournitures_et_avertissements_sous_le_tableau(bureau: Bureau) -> None:
    sheet = cut_sheet(bureau.doc)
    a = column(sheet)
    first_blank = len(api.cut_list_of(bureau.doc).lines) + FIRST_LINE_ROW
    assert a[first_blank - 1] == ""
    totals, grand, hardware = (
        a.index(x) + 1 for x in ("Totaux par matériau", "Total général", "Fournitures")
    )
    assert first_blank < totals < grand < hardware
    assert row_of(sheet, "Tourillon") > hardware
    assert float(text(sheet, f"D{grand}")) == pytest.approx(
        api.cut_list_of(bureau.doc).total_mass_kg, abs=5e-3
    )


def test_remarque_des_tenons_et_avertissements_dans_la_feuille(cadre: Cadre) -> None:
    for host in ("M1", "M2"):
        api.make_mortise_tenon(cadre.parts[host], cadre.parts["T1"], tenon_length=30)
    cadre.parts["T2"].Mark = ""
    sheet = cut_sheet(cadre.doc)
    cut_list = api.cut_list_of(cadre.doc)
    row = row_of(sheet, "T1")
    assert text(sheet, f"O{row}") == "Ajouts compris (L / l / e) : +60 / +0 / +0 mm"
    line = line_of(cut_list, "T1")
    assert float(text(sheet, f"F{row}")) == pytest.approx(line.rough.length)
    assert float(text(sheet, f"C{row}")) == 280
    assert row_of(sheet, "—") > HEADER_ROW  # pièce sans repère
    assert row_of(sheet, "Avertissements") > row_of(sheet, "Total général")
    assert any("sans repère" in cell for cell in column(sheet))


def test_panneaux_avec_surface(document: Any) -> None:
    api.make_wood_part(600, 400, 18, "cp-bouleau", mark="P1", doc=document)
    document.recompute()
    sheet = cut_sheet(document)
    row = row_of(sheet, "P1")
    assert float(text(sheet, f"N{row}")) == pytest.approx(0.24, abs=2e-3)


# --- S4 et sécurité : aucune formule, pas de recalcul automatique ---------------------------


def test_aucune_formule_meme_avec_des_reperes_hostiles(document: Any) -> None:
    hostile = ["=1+1", "+SUM(A1)", "-2", "@A1", '=HYPERLINK("http://x")', "5 mm", "12"]
    for index, mark in enumerate(hostile):
        part(document, mark).Placement = App.Placement(
            App.Vector(0, 300 * index, 0), App.Rotation()
        )
    sheet = cut_sheet(document)
    cells = contents(sheet)
    assert not [a for a, c in cells.items() if c.startswith("=")]
    assert sheet.ExpressionEngine == []
    marks = set(column(sheet)[HEADER_ROW:])
    assert set(hostile) <= marks
    row = row_of(sheet, "=1+1")
    assert str(sheet.getContents(f"A{row}")) == "'=1+1"
    assert sheet.get(f"A{row}") == "=1+1"
    assert sheet.get(f"A{row_of(sheet, '12')}") == "12"  # un texte, pas le nombre 12


def test_libelle_d_ensemble_hostile_litteral(document: Any) -> None:
    board = part(document, "M1")
    furniture, _ = api.make_furniture([board], "=1+1")
    sheet = cut_sheet(document)
    assert furniture.Label == "=1+1"
    assert sheet.getContents(f"K{row_of(sheet, 'M1')}") == "'=1+1"
    assert not [a for a, c in contents(sheet).items() if c.startswith("=")]


def test_feuille_pas_recalculee_automatiquement(document: Any) -> None:
    board = part(document, "M1")
    sheet = cut_sheet(document)
    before = contents(sheet)
    board.Length = 1000
    part(document, "M2")
    document.recompute()
    assert contents(sheet) == before
    assert "Touched" not in sheet.State
    assert float(text(sheet, f"C{row_of(sheet, 'M1')}")) == 800  # l'ancienne valeur, datée
    cut_sheet(document)
    assert float(text(sheet, f"C{row_of(sheet, 'M1')}")) == 1000


# --- S5 : export CSV ------------------------------------------------------------------------


def read_csv(path: Path) -> list[list[str]]:
    raw = path.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")
    assert b"\r\n" in raw
    text_ = raw.decode("utf-8-sig")
    return list(csv.reader(io.StringIO(text_, newline=""), delimiter=";"))


def test_export_csv_du_bureau(bureau: Bureau, tmp_path: Path) -> None:
    path = tmp_path / "bureau.csv"
    written = api.export_cut_list_csv(bureau.doc, path)
    assert Path(written) == path
    rows = read_csv(path)
    cut_list = api.cut_list_of(bureau.doc)
    assert rows[0] == HEADERS
    assert [row[0] for row in rows[1 : 1 + len(cut_list.lines)]] == [
        line.mark for line in cut_list.lines
    ]
    plateau = rows[1 + [line.mark for line in cut_list.lines].index("Plateau")]
    assert plateau[2:5] == ["1200", "600", "30"]
    assert ["Totaux par matériau"] in rows
    assert any(row and row[0] == "Tourillon" for row in rows)
    assert sorted(set(os.listdir(tmp_path)) - {"bibliotheque"}) == ["bureau.csv"]


def test_export_selection_et_remplacement(cadre: Cadre, tmp_path: Path) -> None:
    path = tmp_path / "debit.csv"
    path.write_text("ancien contenu", encoding="utf-8")
    api.export_cut_list_csv(cadre.doc, path, [cadre.parts["M1"]])
    rows = read_csv(path)
    assert [row[0] for row in rows[1:2]] == ["M1"]
    assert "ancien contenu" not in path.read_text(encoding="utf-8-sig")
    assert len([row for row in rows if row and row[0] in ("M1", "M2", "T1", "T2")]) == 1


def test_export_neutralise_les_formules(document: Any, tmp_path: Path) -> None:
    part(document, "=1+1")
    path = tmp_path / "debit.csv"
    api.export_cut_list_csv(document, path)
    assert read_csv(path)[1][0] == "'=1+1"


def test_export_refuse_sans_modifier_le_document(document: Any, tmp_path: Path) -> None:
    document.UndoMode = 1
    part(document, "M1")
    undo_count = document.UndoCount
    (tmp_path / "dossier.csv").mkdir()
    refused = [
        (tmp_path / "debit.txt", "extension"),
        (tmp_path / "debit", "extension"),
        (tmp_path / "dossier.csv", "dossier"),
        (tmp_path / "absent" / "debit.csv", "n'existe pas"),
    ]
    for path, reason in refused:
        with pytest.raises(ValueError, match=reason):
            api.export_cut_list_csv(document, path)
    # « bibliotheque » : dossier de l'utilisateur créé par les fixtures, pas par l'export.
    assert sorted(set(os.listdir(tmp_path)) - {"bibliotheque"}) == ["dossier.csv"]
    assert not (tmp_path / "absent").exists()
    assert (document.UndoCount, sheets(document), touched_names(document)) == (undo_count, [], [])


def test_export_ne_modifie_pas_le_document(bureau: Bureau, tmp_path: Path) -> None:
    doc = bureau.doc
    doc.UndoMode = 1
    undo_count = doc.UndoCount
    api.export_cut_list_csv(doc, tmp_path / "debit.csv")
    assert (doc.UndoCount, sheets(doc), touched_names(doc)) == (undo_count, [], [])


# --- S6 : annuler ---------------------------------------------------------------------------


def test_annuler_la_creation_retire_la_feuille(document: Any) -> None:
    document.UndoMode = 1
    part(document, "M1")
    cut_sheet(document)
    assert document.getObject(SHEET_NAME) is not None
    document.undo()
    assert document.getObject(SHEET_NAME) is None
    assert sheets(document) == []
    document.redo()
    sheet = document.getObject(SHEET_NAME)
    assert sheet is not None
    assert text(sheet, "A1") == "Liste de débit"
    assert "M1" in column(sheet)


def test_annuler_une_mise_a_jour_restaure_la_feuille(document: Any) -> None:
    document.UndoMode = 1
    board = part(document, "M1")
    sheet = cut_sheet(document)
    before = contents(sheet)
    part(document, "M2")
    cut_sheet(document, [board])
    assert text(sheet, "A3") == "Sélection : 1 objet"
    document.undo()
    assert contents(sheet) == before
    assert text(sheet, "A3") == "Tout le document"
    document.redo()
    assert text(sheet, "A3") == "Sélection : 1 objet"


def test_echec_sans_feuille_a_moitie_ecrite(document: Any, tmp_path: Path) -> None:
    document.UndoMode = 1
    part(document, "M1")
    other = App.newDocument("AutreFeuille")
    try:
        stranger = part(other, "E")
        with pytest.raises(ValueError, match="autre document"):
            api.make_cut_list(document, [stranger])
    finally:
        App.closeDocument(other.Name)
    assert sheets(document) == []


# --- S7 : réouverture -----------------------------------------------------------------------


def test_reouverture_la_feuille_reste_ordinaire(
    bureau: Bureau, rouvrir: Reopen, vue_rapport: Any
) -> None:
    sheet = cut_sheet(bureau.doc)
    sheet.set("P2", "'garde")
    before = contents(sheet)
    name = sheet.Name
    vue_rapport.messages.clear()
    doc = rouvrir(bureau.doc)
    restored = doc.getObject(name)
    assert restored.TypeId == "Spreadsheet::Sheet"
    assert "Proxy" not in restored.PropertiesList
    assert restored.MenuiserieCutList is True
    assert restored.getEditorMode("MenuiserieCutList") == ["Hidden"]
    assert contents(restored) == before
    assert text(restored, "P2") == "garde"
    assert not [w for w in vue_rapport.de_niveau("Warning") if "iste de débit" in w]
    updated = api.make_cut_list(doc)  # retrouvée par sa marque après la réouverture
    assert updated == restored
    assert len(sheets(doc)) == 1
    assert text(updated, "P2") == "garde"
    assert text(updated, "A3") == "Tout le document"


def test_avertissements_dans_la_vue_rapport_et_la_feuille(document: Any, vue_rapport: Any) -> None:
    part(document, "M1")
    part(document, "M1", (900, 200, 22))  # même repère, autres cotes
    sheet = cut_sheet(document)
    messages = [w for w in vue_rapport.de_niveau("Warning") if "Repère M1" in w]
    assert len(messages) == 1
    assert any("Repère M1 utilisé pour des pièces différentes" in cell for cell in column(sheet))
