# SPDX-License-Identifier: LGPL-2.1-or-later
"""Modèle de la pièce de bois : cotes, surcotes, calculs et règles (critères A5 à A8)."""

from __future__ import annotations

import math

import pytest

from freecad.menuiserie import DATA_DIR
from freecad.menuiserie.core.materials import Material, MaterialKind, load_library
from freecad.menuiserie.core.part_model import (
    DEFAULT_PANEL_ALLOWANCES,
    DEFAULT_SOLID_ALLOWANCES,
    MAX_DIMENSION_MM,
    MIN_DIMENSION_MM,
    Allowances,
    Dimensions,
    GrainDirection,
    InvalidDimensionsError,
    PartRecord,
    allowances_after_material_change,
    default_allowances,
    grain_after_material_change,
    is_standard_thickness,
    mass_kg,
    rough_dimensions,
    volume_m3,
)

BOARD = Dimensions(800, 200, 22)
LIBRARY, _ = load_library(DATA_DIR / "materiaux.json", None)


def material(material_id: str) -> Material:
    return LIBRARY.get(material_id)


# --- A5 : calculs ------------------------------------------------------------------------


def test_volume_et_masse_d_une_planche() -> None:
    assert volume_m3(BOARD) == pytest.approx(0.00352, abs=1e-9)
    assert mass_kg(BOARD, 710) == pytest.approx(2.4992, abs=1e-9)


def test_cotes_de_debit() -> None:
    assert rough_dimensions(BOARD, Allowances(20, 5, 0)) == Dimensions(820, 205, 22)


def test_enregistrement_de_debit() -> None:
    record = PartRecord(
        mark="M1",
        material_id="chene",
        material_name="Chêne",
        kind=MaterialKind.SOLID,
        finished=BOARD,
        allowances=DEFAULT_SOLID_ALLOWANCES,
        grain=GrainDirection.LENGTH,
        density=710,
    )
    assert record.rough == Dimensions(820, 205, 22)
    assert record.volume_m3() == pytest.approx(0.00352, abs=1e-9)
    assert record.mass_kg() == pytest.approx(2.4992, abs=1e-9)
    assert record.volume_m3(rough=True) == pytest.approx(0.0036982, abs=1e-9)
    assert record.mass_kg(rough=True) == pytest.approx(0.0036982 * 710, abs=1e-9)


def test_cotes_converties_en_flottants() -> None:
    assert isinstance(BOARD.length, float)
    assert isinstance(Allowances(20).length, float)


# --- A6 : bornes des cotes et des surcotes ------------------------------------------------

INVALID_DIMENSIONS: list[object] = [
    0,
    1e-9,
    0.09999999999999999,
    -1,
    -0.0,
    math.nan,
    math.inf,
    -math.inf,
    MAX_DIMENSION_MM + 0.01,
]
INVALID_TYPES: list[object] = ["800", None, True, 10**400]


@pytest.mark.parametrize("field", ["length", "width", "thickness"])
@pytest.mark.parametrize("value", INVALID_DIMENSIONS + INVALID_TYPES)
def test_cote_invalide_refusee(field: str, value: object) -> None:
    values: dict[str, object] = {"length": 800, "width": 200, "thickness": 22, field: value}
    with pytest.raises(InvalidDimensionsError) as error:
        Dimensions(**values)  # type: ignore[arg-type]
    assert error.value.params["field"] in {"longueur", "largeur", "épaisseur"}
    assert "Cote invalide" in str(error.value)


@pytest.mark.parametrize("field", ["length", "width", "thickness"])
@pytest.mark.parametrize("value", [-0.01, -1, math.nan, math.inf, MAX_DIMENSION_MM + 1, "5"])
def test_surcote_invalide_refusee(field: str, value: object) -> None:
    with pytest.raises(InvalidDimensionsError) as error:
        Allowances(**{field: value})  # type: ignore[arg-type]
    assert "Surcote invalide" in str(error.value)


def test_entier_trop_long_pour_etre_affiche_refuse() -> None:
    with pytest.raises(InvalidDimensionsError) as error:
        Dimensions(10**5000, 200, 22)
    assert error.value.params["value"] == "?"


def test_bornes_acceptees() -> None:
    assert Dimensions(MAX_DIMENSION_MM, MIN_DIMENSION_MM, 1).length == MAX_DIMENSION_MM
    assert Allowances(0, MAX_DIMENSION_MM, 0).width == MAX_DIMENSION_MM
    assert Allowances() == Allowances(0, 0, 0)


def test_message_d_erreur_rempli() -> None:
    with pytest.raises(InvalidDimensionsError) as error:
        Dimensions(800, 0, 22)
    assert error.value.params == {"field": "largeur", "value": "0", "min": "0.1", "max": "20000"}
    assert str(error.value) == error.value.template.format(**error.value.params)


@pytest.mark.parametrize(
    ("value", "shown"),
    [(MAX_DIMENSION_MM + 0.01, "20000.01"), (20_000.000000000004, "20000.000000000004")],
)
def test_valeur_refusee_affichee_exactement(value: float, shown: str) -> None:
    with pytest.raises(InvalidDimensionsError) as error:
        Dimensions(value, 200, 22)
    assert error.value.params["value"] == shown


def test_cotes_de_debit_hors_bornes_refusees() -> None:
    with pytest.raises(InvalidDimensionsError):
        rough_dimensions(Dimensions(MAX_DIMENSION_MM, 200, 22), Allowances(20))


def test_erreur_de_cote_est_une_valueerror() -> None:
    assert issubclass(InvalidDimensionsError, ValueError)


# --- A7 : règles de changement de matériau ----------------------------------------------


@pytest.mark.parametrize(
    ("new_id", "current", "expected"),
    [
        ("mdf", GrainDirection.LENGTH, GrainDirection.NONE),
        ("melamine-blanc", GrainDirection.WIDTH, GrainDirection.NONE),
        ("mdf", GrainDirection.NONE, GrainDirection.NONE),
        ("chene", GrainDirection.NONE, GrainDirection.LENGTH),
        ("cp-bouleau", GrainDirection.NONE, GrainDirection.LENGTH),
        ("chene", GrainDirection.WIDTH, GrainDirection.WIDTH),
        ("cp-bouleau", GrainDirection.LENGTH, GrainDirection.LENGTH),
    ],
)
def test_fil_apres_changement_de_materiau(
    new_id: str, current: GrainDirection, expected: GrainDirection
) -> None:
    assert grain_after_material_change(material(new_id), current) is expected


CUSTOM = Allowances(30, 10, 2)


@pytest.mark.parametrize(
    ("old_kind", "new_kind", "current", "expected"),
    [
        (MaterialKind.SOLID, MaterialKind.MDF, DEFAULT_SOLID_ALLOWANCES, DEFAULT_PANEL_ALLOWANCES),
        (
            MaterialKind.PLYWOOD,
            MaterialKind.SOLID,
            DEFAULT_PANEL_ALLOWANCES,
            DEFAULT_SOLID_ALLOWANCES,
        ),
        (
            MaterialKind.SOLID,
            MaterialKind.SOLID,
            DEFAULT_SOLID_ALLOWANCES,
            DEFAULT_SOLID_ALLOWANCES,
        ),
        (
            MaterialKind.MDF,
            MaterialKind.PLYWOOD,
            DEFAULT_PANEL_ALLOWANCES,
            DEFAULT_PANEL_ALLOWANCES,
        ),
        (MaterialKind.SOLID, MaterialKind.MDF, CUSTOM, CUSTOM),
        (MaterialKind.MDF, MaterialKind.SOLID, CUSTOM, CUSTOM),
        (MaterialKind.SOLID, MaterialKind.MDF, Allowances(20, 5, 0.001), Allowances(20, 5, 0.001)),
        # Surcotes de panneau sur une pièce massive : déjà modifiées, donc conservées.
        (MaterialKind.SOLID, MaterialKind.MDF, DEFAULT_PANEL_ALLOWANCES, DEFAULT_PANEL_ALLOWANCES),
        (MaterialKind.MDF, MaterialKind.SOLID, DEFAULT_SOLID_ALLOWANCES, DEFAULT_SOLID_ALLOWANCES),
        # Ancienne famille inconnue : des valeurs par défaut sont considérées non modifiées.
        (None, MaterialKind.MDF, DEFAULT_SOLID_ALLOWANCES, DEFAULT_PANEL_ALLOWANCES),
        (None, MaterialKind.SOLID, DEFAULT_PANEL_ALLOWANCES, DEFAULT_SOLID_ALLOWANCES),
        (None, MaterialKind.SOLID, CUSTOM, CUSTOM),
    ],
)
def test_surcotes_apres_changement_de_materiau(
    old_kind: MaterialKind | None,
    new_kind: MaterialKind,
    current: Allowances,
    expected: Allowances,
) -> None:
    assert allowances_after_material_change(old_kind, new_kind, current) == expected


@pytest.mark.parametrize(
    ("kind", "expected"),
    [
        (MaterialKind.SOLID, Allowances(20, 5, 0)),
        (MaterialKind.PLYWOOD, Allowances()),
        (MaterialKind.MDF, Allowances()),
        (MaterialKind.MELAMINE, Allowances()),
    ],
)
def test_surcotes_par_defaut(kind: MaterialKind, expected: Allowances) -> None:
    assert default_allowances(kind) == expected


def test_valeurs_du_sens_du_fil_figees() -> None:
    assert [g.value for g in GrainDirection] == ["Length", "Width", "None"]


# --- A8 : épaisseurs standard ------------------------------------------------------------


@pytest.mark.parametrize(
    ("thickness", "expected"),
    [(18, True), (17, False), (18.05, True), (17.95, True), (18.06, False), (6.5, True)],
)
def test_epaisseur_standard_du_contreplaque_bouleau(thickness: float, expected: bool) -> None:
    assert is_standard_thickness(material("cp-bouleau"), thickness) is expected


def test_tolerance_personnalisee() -> None:
    assert is_standard_thickness(material("cp-bouleau"), 17, tolerance=1.0)
    assert not is_standard_thickness(material("cp-bouleau"), 18.01, tolerance=0)
