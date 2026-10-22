# SPDX-License-Identifier: LGPL-2.1-or-later
"""Feuille de calcul et export CSV de la liste de débit sur des objets simulés (J2c : S1 à S6).

La vraie ``Spreadsheet::Sheet``, l'annulation et la réouverture sont vérifiées par
``tests/integration/test_liste_de_debit*.py``.
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from freecad.menuiserie.core.cutlist import CutList, Hardware, HardwareKind, build_cut_list
from tests.unit.aides_debit import entry, plywood
from tests.unit.aides_debit_document import Obj, World, simulated_world

NOW = datetime(2026, 10, 22, 14, 30)
ADDRESS = re.compile(r"([A-Z]+)([0-9]+)$")


class FakeSheet(Obj):
    """Feuille simulée : contenus, styles, alignements et largeurs enregistrés."""

    def __init__(self, name: str = "MenuiserieCutList") -> None:
        super().__init__(name, "Spreadsheet::Sheet")
        self.cells: dict[str, str] = {}
        self.styles: dict[str, str] = {}
        self.alignments: dict[str, str] = {}
        self.widths: dict[str, int] = {}
        self.modes: dict[str, int] = {}
        self.recomputed = 0

    def addProperty(self, kind: str, name: str, group: str, doc: str) -> None:
        assert kind == "App::PropertyBool"
        assert (group, bool(doc)) == ("Menuiserie", True)
        self.props[name] = False

    def __setattr__(self, name: str, value: Any) -> None:
        if name in ("MenuiserieCutList", "Label") and "props" in self.__dict__:
            self.props[name] = value
        else:
            super().__setattr__(name, value)

    def setEditorMode(self, name: str, mode: int) -> None:
        self.modes[name] = mode

    def set(self, address: str, content: str) -> None:
        self.cells[address] = content

    def clear(self, address: str) -> None:
        self.cells.pop(address, None)
        self.styles.pop(address, None)
        self.alignments.pop(address, None)

    def getUsedCells(self) -> list[str]:
        return sorted(self.cells)

    def setStyle(self, address: str, style: str) -> None:
        self.styles[address] = style

    def setAlignment(self, address: str, alignment: str) -> None:
        self.alignments[address] = alignment

    def setColumnWidth(self, column: str, width: int) -> None:
        self.widths[column] = width

    def recompute(self) -> None:
        self.recomputed += 1

    def purgeTouched(self) -> None:
        """Marque « Touched » effacée (sans effet sur le double)."""


class SheetDoc:
    """Document simulé qui crée la feuille et note les transactions."""

    def __init__(self, *objects: Obj, fail: bool = False) -> None:
        self.Objects = list(objects)
        self.log: list[str] = []
        self.fail = fail

    def addObject(self, type_id: str, name: str) -> FakeSheet:
        assert type_id == "Spreadsheet::Sheet"
        self.log.append(f"add {name}")
        sheet = FakeSheet(name)
        self.Objects.append(sheet)
        return sheet

    def openTransaction(self, name: str) -> None:
        self.log.append(f"open {name}")

    def commitTransaction(self) -> None:
        self.log.append("commit")

    def abortTransaction(self) -> None:
        self.log.append("abort")


@pytest.fixture
def world(monkeypatch: pytest.MonkeyPatch) -> Iterator[World]:
    with simulated_world(monkeypatch) as simulated:
        yield simulated


def sample() -> CutList:
    dowels = [Hardware(HardwareKind.DOWEL, 8.0, 35.0, 8)]
    return build_cut_list([entry("M1", quantity=2), plywood("P1")], dowels)


def write(world: World, doc: SheetDoc, cut_list: CutList | None = None, **options: Any) -> Any:
    return world.features.cutlist_sheet.write_cut_list(
        doc, cut_list or sample(), now=NOW, **options
    )


def column(sheet: FakeSheet, letter: str) -> dict[int, str]:
    found = {}
    for address, content in sheet.cells.items():
        match = ADDRESS.match(address)
        assert match is not None
        if match.group(1) == letter:
            found[int(match.group(2))] = content
    return found


# --- S1 : création, marque, transaction ----------------------------------------------------


def test_creation_de_la_feuille_marquee_en_une_transaction(world: World) -> None:
    doc = SheetDoc()
    sheet = write(world, doc)
    assert doc.log == ["open Liste de débit", "add MenuiserieCutList", "commit"]
    assert sheet.Label == "Liste de débit"
    assert sheet.props["MenuiserieCutList"] is True
    assert sheet.modes == {"MenuiserieCutList": 2}  # masquée
    assert sheet.recomputed == 1


def test_feuille_renommee_retrouvee_par_sa_marque(world: World) -> None:
    ordinary = Obj("Sheet", "Spreadsheet::Sheet")
    renamed = FakeSheet("Sheet001")
    renamed.props.update(Label="Mon débit", MenuiserieCutList=True)
    doc = SheetDoc(ordinary, renamed)
    assert world.features.cutlist_sheet.find_sheet(doc) is renamed
    assert write(world, doc) is renamed
    assert not any(line.startswith("add") for line in doc.log)
    assert world.features.cutlist_sheet.find_sheet(SheetDoc(ordinary)) is None


def test_marque_fausse_ou_autre_type_ignores(world: World) -> None:
    fake = Obj("Autre", "App::FeaturePython", MenuiserieCutList=True)
    off = FakeSheet("Sheet")
    off.props["MenuiserieCutList"] = False
    assert world.features.cutlist_sheet.find_sheet(SheetDoc(fake, off)) is None


# --- S2 : mise à jour -----------------------------------------------------------------------


def test_mise_a_jour_vide_a_a_o_et_garde_p_et_au_dela(world: World) -> None:
    doc = SheetDoc()
    sheet = write(world, doc)
    sheet.cells.update({"P1": "'note", "Q7": "=A1+1", "AA3": "x", "Z10": "y"})
    sheet.set("O300", "'ancien")  # ligne d'une liste précédente plus longue
    write(world, doc, build_cut_list([entry("M9")]))
    assert {"P1", "Q7", "AA3", "Z10"} <= set(sheet.cells)
    assert sheet.cells["P1"] == "'note"
    assert "O300" not in sheet.cells
    assert column(sheet, "A")[6] == "'M9"
    assert all(row < 12 for row in column(sheet, "A") if row != 300)


def test_mise_a_jour_sans_methode_pour_lister_balaie_les_colonnes_de_l_atelier(
    world: World,
) -> None:
    doc = SheetDoc()
    sheet = write(world, doc)
    vars(sheet)["getUsedCells"] = None  # pas de méthode pour lister les cellules
    sheet.cells["P1"] = "'garde"
    sheet.cells["B900"] = "'vieux"
    write(world, doc)
    assert sheet.cells["P1"] == "'garde"
    assert "B900" not in sheet.cells


# --- S3 : mise en page ----------------------------------------------------------------------


def test_entete_date_portee_et_tableau(world: World) -> None:
    sheet = write(world, SheetDoc())
    a = column(sheet, "A")
    assert a[1] == "'Liste de débit"
    assert a[2].startswith("'Calculée le 2026-10-22 14:30")
    assert "pas mise à jour automatiquement" in a[2]
    assert a[3] == "'Tout le document"
    assert a[5] == "'Repère"
    assert [a[6], a[7]] == ["'M1", "'P1"]
    assert sheet.cells["B6"] == "2"
    assert sheet.cells["C6"] == "800"
    [line, _panel] = sample().lines
    assert sheet.cells["L6"] == f"{line.volume_m3(rough=True):.4f}".rstrip("0")
    assert sheet.cells["I6"] == "'Chene"
    assert "N6" not in sheet.cells  # surface : panneaux seulement
    assert sheet.styles["A1"] == sheet.styles["A5"] == "bold"
    assert sheet.alignments["B6"] == sheet.alignments["C5"] == "right"
    assert "A6" not in sheet.alignments


def test_portee_selection(world: World) -> None:
    assert column(write(world, SheetDoc(), selection_count=3), "A")[3] == "'Sélection : 3 objets"
    assert column(write(world, SheetDoc(), selection_count=1), "A")[3] == "'Sélection : 1 objet"


def test_totaux_fournitures_et_avertissements_sous_le_tableau(world: World) -> None:
    sheet = write(world, SheetDoc(), messages=("Repère M1 utilisé pour des pièces différentes.",))
    a = column(sheet, "A")
    titles = {content: row for row, content in a.items() if content.startswith("'")}
    lines_end = titles["'P1"]
    assert lines_end < titles["'Totaux par matériau"] < titles["'Total général"]
    assert titles["'Total général"] < titles["'Fournitures"] < titles["'Tourillon"]
    assert titles["'Tourillon"] < titles["'Avertissements"]
    last = max(a)
    assert a[last] == "'Repère M1 utilisé pour des pièces différentes."


def test_largeurs_de_colonnes_reglees(world: World) -> None:
    sheet = write(world, SheetDoc())
    assert list(sheet.widths) == list("ABCDEFGHIJKLMNO")
    assert all(width > 0 for width in sheet.widths.values())


def test_remarque_des_ajouts(world: World) -> None:
    from freecad.menuiserie.core.part_model import Allowances

    cut_list = build_cut_list(
        [entry("T1", additions=Allowances(60, 0, 0), allowances=Allowances())]
    )
    sheet = write(world, SheetDoc(), cut_list)
    assert sheet.cells["O6"] == "'Ajouts compris (L / l / e) : +60 / +0 / +0 mm"
    assert sheet.cells["F6"] == "860"


# --- jamais de formule ----------------------------------------------------------------------


@pytest.mark.parametrize("hostile", ["=1+1", "+cmd", "-2", "@SUM(A1)", "5 mm", "12", "'x", "\tA"])
def test_textes_toujours_litteraux(world: World, hostile: str) -> None:
    cut_list = build_cut_list([entry(hostile, material=hostile)])
    sheet = write(world, SheetDoc(), cut_list, messages=(hostile,))
    for address, content in sheet.cells.items():
        letter = ADDRESS.match(address).group(1)  # type: ignore[union-attr]
        assert not content.startswith(("=", "+", "-", "@")), address
        if letter in "AIJKO" or content.startswith("'"):
            assert content == "" or content.startswith("'"), address
    assert sheet.cells["A6"] == "'" + hostile.replace("\t", " ")


def test_caracteres_de_controle_remplaces(world: World) -> None:
    sheet = write(world, SheetDoc(), build_cut_list([entry("a\nb\r")]))
    assert sheet.cells["A6"] == "'a b "


# --- S6 : échec -> transaction annulée ------------------------------------------------------


def test_echec_annule_la_transaction(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_args: Any) -> None:
        raise RuntimeError("échec")

    monkeypatch.setattr(world.features.cutlist_sheet, "_fill", boom)
    doc = SheetDoc()
    with pytest.raises(RuntimeError):
        write(world, doc)
    assert doc.log[-1] == "abort"
    assert "commit" not in doc.log


# --- S5 : export CSV ------------------------------------------------------------------------


def export(world: World, path: Path, cut_list: CutList | None = None) -> Path:
    return Path(world.features.cutlist_export.export_csv(cut_list or sample(), path))


def test_export_international_bom_crlf_et_aucun_temporaire(world: World, tmp_path: Path) -> None:
    target = export(world, tmp_path / "debit.csv")
    raw = target.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")
    assert b"\r\n" in raw
    assert b"\n" not in raw.replace(b"\r\n", b"")
    text = raw.decode("utf-8-sig")
    assert text.splitlines()[0].split(",")[:2] == ["Repère", "Qté"]
    assert "M1,2,800,100,22" in text
    assert "Tourillon,8,35,8" in text
    assert os.listdir(tmp_path) == ["debit.csv"]


def test_export_remplace_un_fichier_existant_en_gardant_son_mode(
    world: World, tmp_path: Path
) -> None:
    target = tmp_path / "debit.csv"
    target.write_text("ancien", encoding="utf-8")
    target.chmod(0o640)
    export(world, target)
    assert "ancien" not in target.read_text(encoding="utf-8-sig")
    assert target.stat().st_mode & 0o777 == 0o640
    assert os.listdir(tmp_path) == ["debit.csv"]


def test_export_nouveau_fichier_en_mode_ordinaire(world: World, tmp_path: Path) -> None:
    target = export(world, tmp_path / "debit.CSV")
    assert target.stat().st_mode & 0o777 == 0o644


@pytest.mark.parametrize("name", ["debit.txt", "debit", "debit.csv.bak", ".csv"])
def test_export_refuse_une_autre_extension(world: World, tmp_path: Path, name: str) -> None:
    with pytest.raises(ValueError, match=r"extension \.csv"):
        export(world, tmp_path / name)
    assert os.listdir(tmp_path) == []


def test_export_refuse_un_dossier_et_un_dossier_absent(world: World, tmp_path: Path) -> None:
    (tmp_path / "dossier.csv").mkdir()
    with pytest.raises(ValueError, match="est un dossier"):
        export(world, tmp_path / "dossier.csv")
    with pytest.raises(ValueError, match="n'existe pas"):
        export(world, tmp_path / "absent" / "debit.csv")
    assert not (tmp_path / "absent").exists()


@pytest.mark.skipif(os.name == "nt" or os.geteuid() == 0, reason="droits POSIX, hors root")
def test_export_refuse_un_fichier_ou_un_dossier_protege(world: World, tmp_path: Path) -> None:
    protected = tmp_path / "protege.csv"
    protected.write_text("garde", encoding="utf-8")
    protected.chmod(0o444)
    with pytest.raises(ValueError, match="pas accessible en écriture"):
        export(world, protected)
    assert protected.read_text(encoding="utf-8") == "garde"
    folder = tmp_path / "lecture"
    folder.mkdir()
    folder.chmod(0o555)
    try:
        with pytest.raises(ValueError, match="pas accessible en écriture"):
            export(world, folder / "debit.csv")
    finally:
        folder.chmod(0o755)


def test_echec_d_ecriture_laisse_le_fichier_intact_et_sans_temporaire(
    world: World, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "debit.csv"
    target.write_text("garde", encoding="utf-8")

    def refuse(*_args: Any) -> None:
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(os, "replace", refuse)
    with pytest.raises(ValueError, match=r"l'écriture .* a échoué"):
        export(world, target)
    assert target.read_text(encoding="utf-8") == "garde"
    assert os.listdir(tmp_path) == ["debit.csv"]


def test_export_neutralise_les_formules(world: World, tmp_path: Path) -> None:
    target = export(world, tmp_path / "debit.csv", build_cut_list([entry("=1+1")]))
    assert "'=1+1," in target.read_text(encoding="utf-8-sig")
