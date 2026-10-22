# SPDX-License-Identifier: LGPL-2.1-or-later
"""Export PDF de la liste de débit par l'api (J2g, critère P2 de ``docs/specs/J2`` § 10).

Les refus de chemin précèdent toute écriture et ne modifient pas le document. Le dessin du PDF
exige l'interface de FreeCAD : sans elle (CI en ligne de commande), l'api refuse ; avec elle, le
fichier est écrit. Le PDF produit par la commande est vérifié par ``tests/gui``.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest

from tests.integration.aides import touched_names
from tests.integration.debit import part, sheets

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
api = pytest.importorskip("freecad.menuiserie.api")


def test_export_pdf_refuse_sans_modifier_le_document(document: Any, tmp_path: Path) -> None:
    document.UndoMode = 1
    part(document, "M1")
    undo_count = document.UndoCount
    (tmp_path / "dossier.pdf").mkdir()
    refused = [
        (tmp_path / "debit.csv", "extension .pdf"),
        (tmp_path / "debit", "extension .pdf"),
        (tmp_path / "dossier.pdf", "dossier"),
        (tmp_path / "absent" / "debit.pdf", "n'existe pas"),
    ]
    for path, reason in refused:
        with pytest.raises(ValueError, match=reason):
            api.export_cut_list_pdf(document, path)
    assert sorted(set(os.listdir(tmp_path)) - {"bibliotheque"}) == ["dossier.pdf"]
    assert not (tmp_path / "absent").exists()
    assert (document.UndoCount, sheets(document), touched_names(document)) == (undo_count, [], [])


@pytest.mark.skipif(App.GuiUp, reason="le dessin du PDF est disponible avec l'interface")
def test_export_pdf_sans_interface_est_refuse_sans_fichier(document: Any, tmp_path: Path) -> None:
    part(document, "M1")
    with pytest.raises(ValueError, match="demande l'interface"):
        api.export_cut_list_pdf(document, tmp_path / "debit.pdf")
    assert sorted(set(os.listdir(tmp_path)) - {"bibliotheque"}) == []


@pytest.mark.skipif(not App.GuiUp, reason="le dessin du PDF exige l'interface")
def test_export_pdf_avec_interface(document: Any, tmp_path: Path) -> None:
    part(document, "M1")
    target = tmp_path / "debit.pdf"
    assert Path(api.export_cut_list_pdf(document, target)) == target
    assert target.read_bytes().startswith(b"%PDF")
    assert sorted(set(os.listdir(tmp_path)) - {"bibliotheque"}) == ["debit.pdf"]
