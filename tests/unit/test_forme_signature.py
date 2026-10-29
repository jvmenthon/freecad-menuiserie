# SPDX-License-Identifier: LGPL-2.1-or-later
"""Empreinte de forme (C4) et contrôle de la matière manquante (E3)."""

from __future__ import annotations

import math

import pytest

from freecad.menuiserie.core.shaped import (
    MISSING_MATERIAL_THRESHOLD,
    ShapeSignature,
    missing_material_ratio,
    missing_material_warning_due,
)


def test_formes_egales_aux_arrondis_pres_ont_la_meme_empreinte() -> None:
    first = ShapeSignature(1_234_567.0, 98_765.4, 12)
    second = ShapeSignature(1_234_567.0 + 0.0003, 98_765.4 - 0.00002, 12)
    assert first == second
    assert hash(first) == hash(second)
    assert len({first, second}) == 1


def test_valeurs_arrondies_a_quatre_chiffres_significatifs() -> None:
    signature = ShapeSignature(1_234_567.0, 98_765.4, 12)
    assert signature.volume == 1_235_000.0
    assert signature.area == 98_770.0


@pytest.mark.parametrize(
    "other",
    [
        ShapeSignature(1_300_000.0, 98_765.4, 12),
        ShapeSignature(1_234_567.0, 90_000.0, 12),
        ShapeSignature(1_234_567.0, 98_765.4, 13),
    ],
)
def test_formes_differentes_ont_des_empreintes_differentes(other: ShapeSignature) -> None:
    assert other != ShapeSignature(1_234_567.0, 98_765.4, 12)


@pytest.mark.parametrize(
    ("args", "field"),
    [
        ((0.0, 1.0, 1), "volume"),
        ((math.nan, 1.0, 1), "volume"),
        ((1.0, -1.0, 1), "area"),
        ((1.0, math.inf, 1), "area"),
        ((1.0, 1.0, 0), "faces"),
        ((1.0, 1.0, True), "faces"),
        ((1.0, 1.0, 2.5), "faces"),
    ],
)
def test_empreinte_invalide_cite_le_champ(args: tuple[float, float, int], field: str) -> None:
    with pytest.raises(ValueError, match=f"^{field} "):
        ShapeSignature(*args)


def test_seuil_de_cinq_pour_cent() -> None:
    assert MISSING_MATERIAL_THRESHOLD == 0.05


@pytest.mark.parametrize(
    ("on_box", "on_shape", "ratio"),
    [
        (100.0, 100.0, 0.0),
        (100.0, 90.0, 0.1),
        (100.0, 0.0, 1.0),
        (100.0, 120.0, 0.0),
        (0.0, 0.0, 0.0),
    ],
)
def test_part_de_matiere_manquante(on_box: float, on_shape: float, ratio: float) -> None:
    assert missing_material_ratio(on_box, on_shape) == pytest.approx(ratio)


@pytest.mark.parametrize(
    ("on_shape", "due"), [(100.0, False), (95.0, False), (94.9, True), (0.0, True)]
)
def test_avertissement_au_dela_de_cinq_pour_cent(on_shape: float, due: bool) -> None:
    assert missing_material_warning_due(100.0, on_shape) is due


@pytest.mark.parametrize(
    ("on_box", "on_shape", "field"),
    [
        (-1.0, 0.0, "on_box"),
        (math.nan, 0.0, "on_box"),
        (1.0, -0.1, "on_shape"),
        (1.0, math.inf, "on_shape"),
    ],
)
def test_volumes_invalides_citent_le_champ(on_box: float, on_shape: float, field: str) -> None:
    with pytest.raises(ValueError, match=f"^{field} "):
        missing_material_ratio(on_box, on_shape)
