# SPDX-License-Identifier: LGPL-2.1-or-later
"""Préparation de l'export PDF de la liste de débit (J2g, critère P2) sur FreeCAD simulé :
chemin ``.pdf`` imposé, nom proposé, écriture atomique commune, HTML du PDF. Le dessin Qt et le
fichier PDF sont vérifiés par ``tests/gui/verifications_debit.py`` (Qt exige l'interface) ;
l'api sans interface est vérifiée par ``tests/integration/test_liste_de_debit_pdf.py``.
"""

from __future__ import annotations

import ast
import os
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

import pytest

from freecad.menuiserie.core.cutlist import build_cut_list
from tests.unit.aides import ROOT
from tests.unit.aides_debit import entry
from tests.unit.aides_debit_document import World, simulated_world

NOW = datetime(2026, 10, 22, 14, 30)
PDF_MODULE = ROOT / "freecad" / "menuiserie" / "gui" / "cutlist_pdf.py"


@pytest.fixture
def world(monkeypatch: pytest.MonkeyPatch) -> Iterator[World]:
    with simulated_world(monkeypatch) as simulated:
        yield simulated


def test_chemin_pdf_accepte_et_extension_imposee(world: World, tmp_path: Path) -> None:
    export = world.features.cutlist_export
    assert (
        export.validated_path(tmp_path / "debit.PDF", export.PDF_SUFFIX) == tmp_path / "debit.PDF"
    )
    for name in ("debit.csv", "debit", "debit.pdf.bak", ".pdf"):
        with pytest.raises(ValueError, match=r"extension \.pdf"):
            export.validated_path(tmp_path / name, export.PDF_SUFFIX)


def test_le_csv_refuse_toujours_un_pdf(world: World, tmp_path: Path) -> None:
    with pytest.raises(ValueError, match=r"extension \.csv"):
        world.features.cutlist_export.validated_path(tmp_path / "debit.pdf")


def test_nom_et_dossier_proposes_en_pdf(world: World, tmp_path: Path) -> None:
    export = world.features.cutlist_export
    assert export.proposed_file_name("Bureau", ".pdf") == "Bureau - liste de débit.pdf"
    proposed = export.proposed_path("bureau", str(tmp_path / "a" / "b.FCStd"), suffix=".pdf")
    assert proposed == tmp_path / "a" / "bureau - liste de débit.pdf"
    assert export.proposed_path("Sans nom", "", home=tmp_path, suffix=".pdf") == (
        tmp_path / "Sans nom - liste de débit.pdf"
    )


@pytest.mark.parametrize(
    ("chosen", "expected"),
    [("dossier/debit", "dossier/debit.pdf"), ("dossier/debit.pdf", "dossier/debit.pdf")],
)
def test_extension_ajoutee_si_absente(world: World, chosen: str, expected: str) -> None:
    assert world.features.cutlist_export.with_suffix(chosen, ".pdf") == expected


def test_ecriture_atomique_commune(world: World, tmp_path: Path) -> None:
    export = world.features.cutlist_export
    target = tmp_path / "debit.pdf"
    target.write_bytes(b"ancien")
    target.chmod(0o640)
    seen: list[Path] = []

    def produce(temporary: Path) -> None:
        seen.append(temporary)
        assert temporary.parent == tmp_path
        assert temporary != target
        temporary.write_bytes(b"%PDF-nouveau")

    export.replace_atomically(target, produce)
    assert target.read_bytes() == b"%PDF-nouveau"
    assert target.stat().st_mode & 0o777 == 0o640
    assert os.listdir(tmp_path) == ["debit.pdf"]
    assert not seen[0].exists()


def test_echec_de_production_laisse_le_fichier_et_aucun_temporaire(
    world: World, tmp_path: Path
) -> None:
    target = tmp_path / "debit.pdf"
    target.write_bytes(b"garde")

    def refuse(temporary: Path) -> None:
        temporary.write_bytes(b"partiel")
        raise OSError

    with pytest.raises(OSError):
        world.features.cutlist_export.replace_atomically(target, refuse)
    assert target.read_bytes() == b"garde"
    assert os.listdir(tmp_path) == ["debit.pdf"]


def test_nouveau_pdf_en_mode_ordinaire(world: World, tmp_path: Path) -> None:
    target = tmp_path / "nouveau.pdf"
    world.features.cutlist_export.replace_atomically(target, lambda t: t.write_bytes(b"%PDF"))
    assert target.stat().st_mode & 0o777 == 0o644


def test_html_du_pdf_titre_date_et_portee(world: World) -> None:
    export = world.features.cutlist_export
    cut_list = build_cut_list([entry("M1", quantity=2)])
    whole = export.pdf_html(cut_list, "Bureau <1>", None, NOW)
    assert "<h1>Liste de débit - Bureau &lt;1&gt;</h1>" in whole
    assert "2026-10-22 14:30" in whole
    assert "Tout le document" in whole
    assert "<script" not in whole
    assert "Sélection : 3 objets" in export.pdf_html(cut_list, "", 3, NOW)
    assert "<h1>Liste de débit</h1>" in export.pdf_html(cut_list, "", None, NOW)


def test_le_module_qt_est_cote_interface_et_ne_garde_aucune_reference() -> None:
    """Qt n'est importé qu'à l'intérieur de la fonction de dessin (jamais à l'import du module)
    et aucun objet Qt n'est stocké au niveau du module."""
    tree = ast.parse(PDF_MODULE.read_text(encoding="utf-8"))
    top_level = [node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom))]
    assert all("PySide" not in ast.unparse(node) for node in top_level)
    assert not any(isinstance(node, ast.Global) for node in ast.walk(tree))
