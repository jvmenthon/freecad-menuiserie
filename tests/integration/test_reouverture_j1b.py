# SPDX-License-Identifier: LGPL-2.1-or-later
"""Réouverture de documents altérés ou hostiles (audit de sécurité de J1b, S1 à S3).

Un document ``.FCStd`` est une donnée externe : ses textes sont cités tronqués et échappés
dans la vue rapport, ses énumérations et sa ``Version`` sont contrôlées avant la migration.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
wood_part = pytest.importorskip("freecad.menuiserie.features.wood_part")

Reopen = Callable[[Any], Any]
HOSTILE = "\n‮" + "x" * 40


def board(doc: Any, material_id: str = "chene") -> Any:
    """Pièce de 800 x 200 x 22 mm du matériau donné, recalculée."""
    obj = wood_part.create_wood_part(doc, material_id=material_id)
    doc.recompute()
    return obj


def assert_safe(warning: str) -> None:
    """Une seule ligne, sans caractère bidi ni texte démesuré."""
    assert warning.endswith("\n")
    assert warning.count("\n") == 1
    assert "‮" not in warning
    assert len(warning) < 400


# --- S1 : textes du document cités dans la vue rapport ------------------------------------


def test_libelle_et_identifiant_cites_tronques_et_echappes(
    document: Any, rouvrir: Reopen, vue_rapport: Any
) -> None:
    obj = board(document)
    obj.Label = "Pièce" + HOSTILE
    obj.MaterialId = "inconnu" + HOSTILE + "y" * 2_000_000
    vue_rapport.messages.clear()
    rouvrir(document)
    [warning] = vue_rapport.de_niveau("Warning")
    assert_safe(warning)
    assert "« Pièce\\n\\u202exxx" in warning
    assert "« inconnu\\n\\u202exxx" in warning
    assert warning.count("…") == 2
