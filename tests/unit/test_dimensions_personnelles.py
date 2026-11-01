# SPDX-License-Identifier: LGPL-2.1-or-later
"""Épaisseurs et formats de panneaux personnels (issue #71, ADR 0028) : lecture, ajout, refus."""

from __future__ import annotations

import pytest

from freecad.menuiserie.core.i18n import TemplatedError
from freecad.menuiserie.core.user_dimensions import (
    MAX_FILE_BYTES,
    MAX_SHEETS,
    UserDimensions,
    dimensions_from_text,
    dimensions_to_text,
    with_sheet,
    with_thickness,
)


def test_aller_retour() -> None:
    dimensions = UserDimensions((12.0, 19.0), ((2800.0, 2070.0),))
    assert dimensions_from_text(dimensions_to_text(dimensions)) == dimensions


def test_fichier_minimal_et_valeurs_triees_sans_doublon() -> None:
    assert dimensions_from_text('{"format": 1}') == UserDimensions()
    text = '{"format": 1, "thicknesses": [19, 12, 19.01], "sheets": [[2000, 1000], [2000, 1000]]}'
    assert dimensions_from_text(text) == UserDimensions((12.0, 19.0), ((2000.0, 1000.0),))


@pytest.mark.parametrize(
    "text",
    [
        "",
        "[]",
        '{"format": 2}',
        '{"format": true}',
        '{"format": 1, "thicknesses": "12"}',
        '{"format": 1, "thicknesses": [0]}',
        '{"format": 1, "thicknesses": [301]}',
        '{"format": 1, "thicknesses": [NaN]}',
        '{"format": 1, "thicknesses": [true]}',
        '{"format": 1, "thicknesses": ["12"]}',
        '{"format": 1, "sheets": [[2000]]}',
        '{"format": 1, "sheets": [[2000, 0]]}',
        '{"format": 1, "sheets": [[2000, 30000]]}',
        '{"format": 1, "sheets": [["a", 1000]]}',
        "[" * 10000,
    ],
)
def test_fichier_refuse(text: str) -> None:
    with pytest.raises(TemplatedError, match="invalide"):
        dimensions_from_text(text)


def test_fichier_trop_gros_ou_trop_de_valeurs() -> None:
    with pytest.raises(TemplatedError, match="volumineux"):
        dimensions_from_text('{"format": 1, "x": "' + "a" * MAX_FILE_BYTES + '"}')
    sheets = ",".join(f"[{1000 + i}, 500]" for i in range(MAX_SHEETS + 1))
    with pytest.raises(TemplatedError, match="trop de valeurs"):
        dimensions_from_text('{"format": 1, "sheets": [' + sheets + "]}")


def test_ajout_d_une_epaisseur() -> None:
    dimensions = with_thickness(UserDimensions((19.0,)), 12.0)
    assert dimensions.thicknesses == (12.0, 19.0)
    assert with_thickness(dimensions, 19.0) == dimensions  # déjà présente


@pytest.mark.parametrize("value", [0.0, -3.0, 301.0, float("nan"), float("inf")])
def test_epaisseur_refusee(value: float) -> None:
    with pytest.raises(TemplatedError, match="comprise entre"):
        with_thickness(UserDimensions(), value)


def test_ajout_d_un_format() -> None:
    dimensions = with_sheet(UserDimensions(), 2800.0, 2070.0)
    assert dimensions.sheets == ((2800.0, 2070.0),)
    assert with_sheet(dimensions, 2800.0, 2070.0) == dimensions


@pytest.mark.parametrize("size", [(0.0, 100.0), (100.0, 20001.0), (float("nan"), 100.0)])
def test_format_refuse(size: tuple[float, float]) -> None:
    with pytest.raises(TemplatedError, match="comprises entre"):
        with_sheet(UserDimensions(), *size)


def test_liste_pleine() -> None:
    full = UserDimensions(tuple(float(i + 1) for i in range(50)))
    with pytest.raises(TemplatedError, match="Trop de valeurs"):
        with_thickness(full, 99.5)
