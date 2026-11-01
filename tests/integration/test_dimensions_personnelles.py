# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fichier des dimensions personnelles dans le dossier utilisateur (issue #71, ADR 0028)."""

from __future__ import annotations

from typing import Any

import pytest

pytestmark = pytest.mark.integration

pytest.importorskip("FreeCAD")
user_dimensions = pytest.importorskip("freecad.menuiserie.features.user_dimensions")


def test_ajout_relecture_et_fichier_a_cote_de_la_bibliotheque(bibliotheque_temporaire: Any) -> None:
    path = user_dimensions.dimensions_path()
    assert path.parent == bibliotheque_temporaire.path.parent
    assert user_dimensions.read_dimensions().thicknesses == ()
    user_dimensions.add_thickness(19.0)
    user_dimensions.add_sheet(2800.0, 2070.0)
    assert path.is_file()
    again = user_dimensions.read_dimensions()
    assert again.thicknesses == (19.0,)
    assert again.sheets == ((2800.0, 2070.0),)


def test_refus_sans_ecriture(bibliotheque_temporaire: Any) -> None:
    with pytest.raises(ValueError, match="comprise entre"):
        user_dimensions.add_thickness(0.0)
    assert not user_dimensions.dimensions_path().exists()


def test_fichier_invalide_ignore(bibliotheque_temporaire: Any) -> None:
    path = user_dimensions.dimensions_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("pas du json", encoding="utf-8")
    assert user_dimensions.read_dimensions().thicknesses == ()
