# SPDX-License-Identifier: LGPL-2.1-or-later
"""Rotation d'une pièce (RO-a, critère A1) : angles du ``Placement`` et matrice, sans FreeCAD."""

from __future__ import annotations

import itertools
import math

import pytest

from freecad.menuiserie.core.geometry import Matrix3
from freecad.menuiserie.core.rotation import angles_of, matrix_of

TOLERANCE = 1e-9


def square_rotations() -> list[Matrix3]:
    """Les 24 rotations d'équerre : permutations signées de déterminant +1."""
    found = []
    for perm in itertools.permutations(range(3)):
        for signs in itertools.product((1.0, -1.0), repeat=3):
            r = [[signs[i] if perm[i] == j else 0.0 for j in range(3)] for i in range(3)]
            rows: Matrix3 = (
                (r[0][0], r[0][1], r[0][2]),
                (r[1][0], r[1][1], r[1][2]),
                (r[2][0], r[2][1], r[2][2]),
            )
            m = rows
            det = (
                m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1])
                - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
                + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0])
            )
            if det > 0:
                found.append(rows)
    return found


def close(first: Matrix3, second: Matrix3) -> bool:
    return all(
        abs(a - b) <= TOLERANCE
        for r, s in zip(first, second, strict=True)
        for a, b in zip(r, s, strict=True)
    )


def test_aller_retour_des_angles() -> None:
    for angles in [(10.0, 20.0, 30.0), (-170.0, 45.5, 120.0), (0.0, 0.0, 0.0), (90.0, -30.0, 5.0)]:
        back = angles_of(matrix_of(angles))
        assert back == pytest.approx(angles, abs=TOLERANCE)


def test_aller_retour_des_24_rotations_d_equerre() -> None:
    rotations = square_rotations()
    assert len(rotations) == 24
    for matrix in rotations:
        assert close(matrix_of(angles_of(matrix)), matrix)


def test_convention_du_placement() -> None:
    # Lacet de 90° : X devient Y ; roulis de 90° : Y devient Z (rotation = Rz · Ry · Rx).
    assert close(matrix_of((0.0, 0.0, 90.0)), ((0, -1, 0), (1, 0, 0), (0, 0, 1)))
    assert close(matrix_of((90.0, 0.0, 0.0)), ((1, 0, 0), (0, 0, -1), (0, 1, 0)))
    assert angles_of(((0, -1, 0), (1, 0, 0), (0, 0, 1))) == pytest.approx((0, 0, 90))


@pytest.mark.parametrize("pitch", [90.0, -90.0])
def test_blocage_de_cardan(pitch: float) -> None:
    matrix = matrix_of((25.0, pitch, 40.0))
    x, y, z = angles_of(matrix)
    assert x == 0.0
    assert y == pytest.approx(pitch)
    assert all(math.isfinite(value) for value in (x, y, z))
    assert close(matrix_of((x, y, z)), matrix)


def test_blocage_de_cardan_quasi_exact() -> None:
    # Pitch obtenu par calcul : cos(tangage) ~ 6e-17, jamais de nan.
    for pitch in (90.0, -90.0):
        angles = angles_of(matrix_of((0.0, pitch, 0.0)))
        assert all(math.isfinite(value) for value in angles)
        assert angles == pytest.approx((0.0, pitch, 0.0), abs=TOLERANCE)


def test_pas_de_zero_negatif() -> None:
    angles = angles_of(matrix_of((0.0, 0.0, 0.0)))
    assert [math.copysign(1.0, value) for value in angles] == [1.0, 1.0, 1.0]


def test_entrees_non_finies_refusees() -> None:
    bad = ((math.nan, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
    with pytest.raises(ValueError, match="matrice"):
        angles_of(bad)
    with pytest.raises(ValueError, match="angles"):
        matrix_of((0.0, math.inf, 0.0))
