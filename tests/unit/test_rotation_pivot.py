# SPDX-License-Identifier: LGPL-2.1-or-later
"""Rotation d'une pièce (RO-a, critères A2 et A3) : rotation sur place et aimantation de l'angle."""

from __future__ import annotations

import math

import pytest

from freecad.menuiserie.core.geometry import RigidTransform, Vec3
from freecad.menuiserie.core.part_model import Dimensions
from freecad.menuiserie.core.rotation import matrix_of, snapped_angle, turned_about
from freecad.menuiserie.core.snap import Turn
from freecad.menuiserie.core.snap._frames import turned_in_place

TOLERANCE = 1e-9
DIMENSIONS = Dimensions(800.0, 300.0, 19.0)
CENTER = Vec3(400.0, 150.0, 9.5)
START = RigidTransform(matrix_of((20.0, -35.0, 70.0)), Vec3(120.0, -40.0, 15.0))


def distance(first: Vec3, second: Vec3) -> float:
    return math.dist((first.x, first.y, first.z), (second.x, second.y, second.z))


@pytest.mark.parametrize("axis", [0, 1, 2])
@pytest.mark.parametrize("angle", [15.0, 37.5, -90.0, 180.0])
def test_le_centre_ne_bouge_pas(axis: int, angle: float) -> None:
    turned = turned_about(START, DIMENSIONS, axis, angle)
    assert distance(turned.apply(CENTER), START.apply(CENTER)) <= TOLERANCE


@pytest.mark.parametrize("axis", [0, 1, 2])
def test_quatre_quarts_de_tour_redonnent_le_depart(axis: int) -> None:
    result = START
    for _ in range(4):
        result = turned_about(result, DIMENSIONS, axis, 90.0)
    for row, expected in zip(result.rotation, START.rotation, strict=True):
        assert row == pytest.approx(expected, abs=TOLERANCE)
    assert distance(result.translation, START.translation) <= TOLERANCE


def test_axe_fixe_du_document() -> None:
    # R' = R(axe, delta) · R : l'axe X de la pièce tourne autour de Z du document.
    flat = RigidTransform.identity()
    turned = turned_about(flat, DIMENSIONS, 2, 90.0)
    image = turned.rotate(Vec3(1.0, 0.0, 0.0))
    assert distance(image, Vec3(0.0, 1.0, 0.0)) <= TOLERANCE


@pytest.mark.parametrize(("axis", "turn"), [(0, Turn.X), (1, Turn.Y), (2, Turn.Z)])
def test_quart_de_tour_identique_a_turned_in_place(axis: int, turn: Turn) -> None:
    expected = turned_in_place(START, DIMENSIONS, turn)
    got = turned_about(START, DIMENSIONS, axis, 90.0)
    assert distance(got.translation, expected.translation) <= 1e-7
    for row, wanted in zip(got.rotation, expected.rotation, strict=True):
        assert row == pytest.approx(wanted, abs=1e-9)


def test_axe_ou_angle_invalide() -> None:
    with pytest.raises(ValueError, match="axis"):
        turned_about(START, DIMENSIONS, 3, 10.0)
    for bad in (math.nan, math.inf, -math.inf):
        with pytest.raises(ValueError, match="angle"):
            turned_about(START, DIMENSIONS, 0, bad)


@pytest.mark.parametrize(
    ("angle", "expected"),
    [
        (0.0, 0.0),
        (7.4, 0.0),
        (7.6, 15.0),
        (22.4, 15.0),
        (-8.0, -15.0),
        (44.0, 45.0),
        (370.0, 375.0),
    ],
)
def test_aimantation_tous_les_15_degres(angle: float, expected: float) -> None:
    assert snapped_angle(angle) == pytest.approx(expected)


def test_pas_personnalise() -> None:
    assert snapped_angle(47.0, step=5.0) == pytest.approx(45.0)


def test_angle_libre_au_dixieme() -> None:
    assert snapped_angle(37.46, free=True) == pytest.approx(37.5)
    assert snapped_angle(-12.34, free=True) == pytest.approx(-12.3)
    assert snapped_angle(10.0, free=True) == pytest.approx(10.0)


def test_pas_de_zero_negatif() -> None:
    assert math.copysign(1.0, snapped_angle(-0.0)) == 1.0
    assert math.copysign(1.0, snapped_angle(-0.04, free=True)) == 1.0


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
@pytest.mark.parametrize("free", [False, True])
def test_valeurs_non_finies_refusees(bad: float, free: bool) -> None:
    with pytest.raises(ValueError, match="angle"):
        snapped_angle(bad, free=free)


@pytest.mark.parametrize("step", [0.0, -5.0, math.nan, math.inf])
def test_pas_invalide_refuse(step: float) -> None:
    with pytest.raises(ValueError, match="step"):
        snapped_angle(10.0, step=step)
