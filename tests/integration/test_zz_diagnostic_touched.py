# SPDX-License-Identifier: LGPL-2.1-or-later
"""Diagnostic temporaire : état « Touched » d'une pièce en bois dans un ensemble."""

from __future__ import annotations

from typing import Any

import pytest

from tests.integration import test_piece_en_bois_croisements as croisements

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")


def _run(test: Any, *args: Any) -> str:
    doc = App.newDocument("Diag")
    try:
        test(doc, *args)
    except AssertionError as error:
        return f"ECHEC {str(error)[:300]}"
    finally:
        App.closeDocument(doc.Name)
    return "OK"


def test_diagnostic_ordre() -> None:
    seul = _run(croisements.test_piece_en_bois_tournee_dans_un_ensemble)
    apres_annul = _run(croisements.test_annuler_retablir_l_assemblage)
    ensuite = _run(croisements.test_piece_en_bois_tournee_dans_un_ensemble)
    apres_suppr = _run(croisements.test_source_supprimee_d_une_piece_assemblee_puis_annulation)
    enfin = _run(croisements.test_piece_en_bois_tournee_dans_un_ensemble)
    pytest.fail(f"DIAG {seul} | {apres_annul} -> {ensuite} | {apres_suppr} -> {enfin}")
