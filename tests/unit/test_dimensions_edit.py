# SPDX-License-Identifier: LGPL-2.1-or-later
"""Éditeur des dimensions personnelles, partie sans Qt (``features/dimensions_edit``, ADR 0069)."""

from __future__ import annotations

import importlib
from collections.abc import Iterator
from typing import Any

import pytest

from freecad.menuiserie.core.user_dimensions import DEFAULT_SHEETS, UserDimensions
from tests.unit.aides_freecad import simulated_freecad

DIMENSIONS = UserDimensions((15.0, 27.0, 30.0), ((2800.0, 2070.0),))


@pytest.fixture
def edit(monkeypatch: pytest.MonkeyPatch) -> Iterator[Any]:
    with simulated_freecad(monkeypatch):
        yield importlib.import_module("freecad.menuiserie.features.dimensions_edit")


def test_resume(edit: Any) -> None:
    assert edit.summary(DIMENSIONS) == "3 épaisseurs, 1 format"
    assert edit.summary(UserDimensions((12.0,), ((2000.0, 1000.0), (2400.0, 1200.0)))) == (
        "1 épaisseur, 2 formats"
    )
    assert edit.summary(UserDimensions((12.0,))) == "1 épaisseur, 0 format"
    assert edit.summary(UserDimensions()) == "aucune valeur personnelle"


def test_resume_traduit(edit: Any) -> None:
    def english(text: str) -> str:
        return {"{count} épaisseurs": "{count} thicknesses", "{count} format": "{count} sheet"}.get(
            text, text
        )

    assert edit.summary(DIMENSIONS, english) == "3 thicknesses, 1 sheet"


def test_valeurs_ecrites_pour_l_utilisateur(edit: Any) -> None:
    assert edit.format_mm(19.0) == "19"
    assert edit.format_mm(12.5) == "12,5"
    assert edit.format_sheet(2800.0, 2070.0) == "2800 x 2070"
    assert edit.describe(DIMENSIONS) == "15, 27, 30 mm ; 2800 x 2070 mm"
    assert edit.describe(UserDimensions((15.0,))) == "15 mm"
    assert edit.describe(UserDimensions()) == "aucune"


def test_description_limitee_en_longueur(edit: Any) -> None:
    many = UserDimensions(tuple(float(value) for value in range(1, 12)))
    assert edit.describe(many) == "1, 2, 3, 4, 5, 6, … mm"


def test_ligne_d_apercu_des_dimensions(edit: Any) -> None:
    current = UserDimensions((15.0, 27.0))
    row = edit.import_row(current, DIMENSIONS)
    assert (row.key, row.group, row.label) == (
        "dimensions",
        "Épaisseurs et formats",
        "Épaisseurs et formats personnels",
    )
    assert (row.current, row.value) == ("15, 27 mm", DIMENSIONS)
    assert row.imported == "15, 27, 30 mm ; 2800 x 2070 mm"
    assert edit.import_row(DIMENSIONS, DIMENSIONS) is None  # rien à changer : pas de ligne


def test_epaisseurs_integrees_triees_sans_doublon(edit: Any) -> None:
    assert edit.builtin_thicknesses([(19.0, 12.0), (12.0, 22.0), ()]) == (12.0, 19.0, 22.0)
    assert edit.builtin_thicknesses([]) == ()


def test_listes_de_l_editeur_integrees_puis_personnelles(edit: Any) -> None:
    thicknesses = edit.thickness_entries((12.0, 19.0), UserDimensions((15.0,)))
    assert [(entry.text, entry.personal) for entry in thicknesses] == [
        ("12", False),
        ("19", False),
        ("15", True),
    ]
    sheets = edit.sheet_entries(DIMENSIONS)
    assert [entry.personal for entry in sheets] == [False] * len(DEFAULT_SHEETS) + [True]
    assert sheets[-1].value == (2800.0, 2070.0)
    assert sheets[-1].text == "2800 x 2070"
