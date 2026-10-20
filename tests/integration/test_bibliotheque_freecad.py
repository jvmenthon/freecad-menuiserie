# SPDX-License-Identifier: LGPL-2.1-or-later
"""Bibliothèque de matériaux vue de FreeCAD : chemins, cache de session, journal (B14)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
library = pytest.importorskip("freecad.menuiserie.features.library")
wood_part = pytest.importorskip("freecad.menuiserie.features.wood_part")

MAPLE = {
    "id": "erable",
    "kind": "solid",
    "name": "Érable",
    "density": 650,
    "thicknesses": [22],
    "color": "#E8D2A8",
}


# --- B14 : bibliothèque utilisateur -------------------------------------------------------


def test_anomalie_signalee_une_seule_fois(
    document: Any, bibliotheque_temporaire: Any, vue_rapport: Any
) -> None:
    invalid = {**MAPLE, "id": "invalide", "name": "Invalide", "density": 0}
    path = bibliotheque_temporaire.installer(MAPLE, invalid)
    library.get_library()
    library.get_library()
    obj = wood_part.create_wood_part(document, material_id="erable")
    document.recompute()
    assert obj.isValid()
    [error] = vue_rapport.de_niveau("Error")
    assert str(path) in error
    assert "« invalide »" in error
    assert "« density »" in error
    assert "{" not in error
    assert vue_rapport.de_niveau("Warning") == []


def test_remplacement_signale_dans_le_journal(
    bibliotheque_temporaire: Any, vue_rapport: Any
) -> None:
    bibliotheque_temporaire.installer({**MAPLE, "id": "chene", "name": "Chêne"})
    [info] = vue_rapport.de_niveau("Log")
    assert "« chene » remplace" in info
    assert library.get_library().get("chene").density == 650


def test_rechargement_de_la_bibliotheque(bibliotheque_temporaire: Any) -> None:
    assert "erable" not in library.get_library()
    bibliotheque_temporaire.installer(MAPLE)
    assert "erable" in library.get_library()
    bibliotheque_temporaire.retirer()
    assert "erable" not in library.get_library()
    assert len(library.get_library()) == 12


def test_chemins_de_la_bibliotheque(bibliotheque_temporaire: Any) -> None:
    assert library.builtin_library_path().is_file()
    assert library.user_library_path() == bibliotheque_temporaire.path
    App.ParamGet(library.PARAM_PATH).RemString(library.USER_LIBRARY_PARAM)
    expected = Path(App.getUserAppDataDir()) / "Menuiserie" / "materiaux.json"
    assert library.user_library_path() == expected
    assert library.display_language() == "fr"
