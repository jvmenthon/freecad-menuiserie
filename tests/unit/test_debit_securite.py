# SPDX-License-Identifier: LGPL-2.1-or-later
"""Liste de débit face à un document ou un chemin hostile (relecture de sécurité de fin de J2).

Collecte exponentielle, quantités débordantes, ``Sheet`` étrangère, export CSV (encodage, mode
des nouveaux fichiers), message de ``write_pdf`` et fsync du PDF.
"""

from __future__ import annotations

import os
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from freecad.menuiserie.core.cutlist import build_cut_list
from tests.unit.aides_debit import entry
from tests.unit.aides_debit_document import Doc, Obj, World, group, link, simulated_world
from tests.unit.aides_debit_feuille import FakeSheet, SheetDoc

ROOT = Path(__file__).resolve().parents[2]
PDF_MODULE = ROOT / "freecad" / "menuiserie" / "gui" / "cutlist_pdf.py"
COMMANDS_MODULE = ROOT / "freecad" / "menuiserie" / "gui" / "commands" / "cutlist.py"


@pytest.fixture
def world(monkeypatch: pytest.MonkeyPatch) -> Iterator[World]:
    with simulated_world(monkeypatch) as simulated:
        yield simulated


def part(world: World, name: str, mark: str = "M1") -> Obj:
    return world.part(name, mark, ExpressionEngine=[])


def kinds(collected: object) -> list[str]:
    return [notice.kind.value for notice in collected.notices]  # type: ignore[attr-defined]


# --- 1 : collecte exponentielle et quantités débordantes -----------------------------------


def nested_diamonds(world: World, depth: int) -> Doc:
    """G1…Gn : chaque groupe contient deux liens vers le suivant (2^n chemins), Gn une pièce."""
    board = part(world, "WoodPart")
    groups = [group(f"G{i}") for i in range(1, depth + 1)]
    groups[-1].props["Group"] = [board]
    for rank, current in enumerate(groups[:-1]):
        following = groups[rank + 1]
        current.props["Group"] = [link(f"L{rank}a", following), link(f"L{rank}b", following)]
    objects = [
        board,
        *groups,
        *(item for g in groups for item in g.props["Group"] if item is not board),
    ]
    return Doc(*objects)


def test_diamants_imbriques_finissent_vite_avec_un_avertissement(world: World) -> None:
    module = world.features.cutlist_collect
    doc = nested_diamonds(world, 30)
    start = time.monotonic()
    collected = module.collect(doc)
    assert time.monotonic() - start < 5
    assert "Truncated" in kinds(collected)
    assert kinds(collected).count("Truncated") == 1
    assert all(e.quantity <= module.MAX_QUANTITY for e in collected.entries)


def test_budget_de_visites_sans_avertissement_pour_un_document_ordinaire(world: World) -> None:
    board = part(world, "WoodPart")
    collected = world.features.cutlist_collect.collect(Doc(board, link("L", board)))
    assert kinds(collected) == []
    assert collected.entries[0].quantity == 2


def test_tableau_de_liens_geant_plafonne_sans_debordement(world: World) -> None:
    module = world.features.cutlist_collect
    board = part(world, "WoodPart")
    huge = link("L", board, count=10**30)
    collected = module.collect(Doc(board, huge))
    assert [e.quantity for e in collected.entries] == [module.MAX_QUANTITY]
    assert "QuantityCapped" in kinds(collected)
    module.collect_cut_list(Doc(board, huge))  # totaux sans OverflowError


def test_liens_composes_plafonnes(world: World) -> None:
    module = world.features.cutlist_collect
    board = part(world, "WoodPart")
    inner = link("Inner", board, count=10**9)
    outer = link("Outer", inner, count=10**9)
    cut_list, _ = module.collect_cut_list(Doc(board, inner, outer))
    assert cut_list.lines[0].quantity == module.MAX_QUANTITY
    assert any(w.kind.value == "QuantityCapped" for w in cut_list.warnings)


# --- 2 et 4 : Sheet étrangère, document plus récent ----------------------------------------


def live(world: World, doc: SheetDoc) -> Obj:
    world.features.cutlist_object.ensure_cut_list(doc)
    found = world.features.cutlist_object.find_cut_list(doc)
    assert found is not None
    return found


@pytest.mark.parametrize("kind", ["autre_type", "sans_marque", "autre_document"])
def test_feuille_etrangere_jamais_reecrite(
    world: World, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    doc = SheetDoc(part(world, "WoodPart"))
    obj = live(world, doc)
    messages: list[str] = []
    monkeypatch.setattr(world.features.cutlist_object, "report_warning", messages.append)
    if kind == "autre_type":
        fake: Obj = Obj("Box", "Part::Box")
        fake.Document = doc
    else:
        fake = FakeSheet("Autre")
        fake.Document = doc if kind == "sans_marque" else SheetDoc()
        fake.props["MenuiserieCutList"] = kind == "autre_document"
    obj.props["Sheet"] = fake
    obj.Proxy.execute(obj)
    assert not getattr(fake, "cells", None)
    assert "recomputed" not in vars(fake) or fake.recomputed == 0
    assert len(messages) == 1
    assert "feuille" in messages[0]
    assert not obj.Proxy.mustExecute(obj)


def test_feuille_propre_toujours_reecrite(world: World) -> None:
    doc = SheetDoc(part(world, "WoodPart"))
    obj = live(world, doc)
    sheet = obj.Sheet
    sheet.cells.clear()
    obj.Proxy.execute(obj)
    assert sheet.cells


def test_must_execute_faux_pour_un_document_plus_recent(world: World) -> None:
    board = part(world, "WoodPart")
    doc = SheetDoc(board)
    obj = live(world, doc)
    extra = part(world, "WoodPart001", "M2")
    extra.Document = doc
    doc.Objects.append(extra)
    assert obj.Proxy.mustExecute(obj)
    obj.props["Version"] = world.features.cutlist_object.MODEL_VERSION + 1
    assert not obj.Proxy.mustExecute(obj)


# --- 3 et 5 : export CSV --------------------------------------------------------------------


def test_export_csv_survit_a_une_substitution_isolee(world: World, tmp_path: Path) -> None:
    cut_list = build_cut_list([entry("M\ud800")], [])
    target = world.features.cutlist_export.export_csv(cut_list, tmp_path / "debit.csv")
    assert "M?" in target.read_bytes().decode("utf-8-sig")
    assert os.listdir(tmp_path) == ["debit.csv"]


@pytest.mark.skipif(os.name != "posix", reason="umask POSIX")
@pytest.mark.parametrize(("mask", "mode"), [(0o022, 0o644), (0o077, 0o600), (0o002, 0o664)])
def test_nouveau_fichier_respecte_le_umask(
    world: World, tmp_path: Path, mask: int, mode: int
) -> None:
    previous = os.umask(mask)
    try:
        target = world.features.cutlist_export.export_csv(
            build_cut_list([entry()], []), tmp_path / "debit.csv"
        )
    finally:
        os.umask(previous)
    assert target.stat().st_mode & 0o777 == mode


@pytest.mark.skipif(os.name != "posix", reason="umask POSIX")
def test_umask_sans_proc_lu_par_os_umask_et_retabli(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    export = world.features.cutlist_export
    previous = os.umask(0o027)
    try:
        monkeypatch.setattr(Path, "read_text", lambda *_a, **_k: (_ for _ in ()).throw(OSError()))
        assert export._current_umask() == 0o027
        assert os.umask(previous) == 0o027  # rétabli par la lecture
    finally:
        os.umask(previous)


# --- 6 : chemins échappés, fsync -----------------------------------------------------------


def test_chemins_cites_par_les_messages_sont_echappes() -> None:
    for module in (PDF_MODULE, COMMANDS_MODULE):
        source = module.read_text(encoding="utf-8")
        assert "escaped_text(str(" in source
        assert '{"path": str(' not in source


def test_pdf_synchronise_avant_le_remplacement() -> None:
    assert "os.fsync(" in PDF_MODULE.read_text(encoding="utf-8")


def test_validated_path_documente_le_remplacement_d_un_lien(world: World) -> None:
    doc = world.features.cutlist_export.validated_path.__doc__ or ""
    assert "lien symbolique" in doc
