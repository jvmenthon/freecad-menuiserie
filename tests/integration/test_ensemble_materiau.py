# SPDX-License-Identifier: LGPL-2.1-or-later
"""Matériau commun à toutes les pièces d'un ensemble, sous-ensembles compris (issue #77)."""

from __future__ import annotations

from typing import Any

import pytest

from tests.integration.bureau import build_parts
from tests.integration.test_ensemble_membres import caisson

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
api = pytest.importorskip("freecad.menuiserie.api")


def materials(parts: Any) -> list[str]:
    return [part.MaterialId for part in parts]


def test_toutes_les_pieces_et_les_sous_ensembles(document: Any) -> None:
    bureau = build_parts(document)
    sub, sub_parts = caisson(document)
    desk = [bureau.parts[mark] for mark in ("P", "JG", "JD")]
    furniture, _ = api.make_furniture([*desk, sub], label="Bureau")
    assert api.set_furniture_material(furniture, "hetre") == ()
    assert materials([*desk, *sub_parts.values()]) == ["hetre"] * 6
    assert bureau.parts["V"].MaterialId == "chene"  # hors de l'ensemble : inchangée


def test_materiau_inconnu_ne_change_rien(document: Any) -> None:
    bureau = build_parts(document)
    furniture, _ = api.make_furniture(list(bureau.parts.values()), label="Bureau")
    with pytest.raises(KeyError):
        api.set_furniture_material(furniture, "inconnu")
    assert materials(bureau.parts.values()) == ["chene"] * 4


def test_refus_hors_ensemble(document: Any) -> None:
    bureau = build_parts(document)
    with pytest.raises(TypeError):
        api.set_furniture_material(bureau.parts["P"], "hetre")


def test_materiau_pilote_par_une_expression(document: Any) -> None:
    bureau = build_parts(document)
    furniture, _ = api.make_furniture(list(bureau.parts.values()), label="Bureau")
    driven = bureau.parts["P"]
    driven.setExpression("MaterialId", "'chene'")
    notices = api.set_furniture_material(furniture, "hetre")
    assert len(notices) == 1
    assert driven.MaterialId == "chene"
    assert materials(part for mark, part in bureau.parts.items() if mark != "P") == ["hetre"] * 3


def test_annulable_en_une_transaction(document: Any) -> None:
    bureau = build_parts(document)
    furniture, _ = api.make_furniture(list(bureau.parts.values()), label="Bureau")
    document.openTransaction("Matériau")
    api.set_furniture_material(furniture, "hetre")
    document.commitTransaction()
    document.undo()
    assert materials(bureau.parts.values()) == ["chene"] * 4
