# SPDX-License-Identifier: LGPL-2.1-or-later
"""Écart entre deux pièces proches qui ne se touchent pas (rapprochement avant assemblage)."""

from __future__ import annotations

import math

import pytest

from freecad.menuiserie.core.geometry import PlacedBlock, RigidTransform, Vec3
from freecad.menuiserie.core.near_gap import NEAR_GAP_MM, near_gap
from freecad.menuiserie.core.part_model import Dimensions

ROTATION_Z_90 = ((0.0, -1.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0))
IDENTITY = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))


Matrix = tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]


def block(
    size: tuple[float, float, float], at: tuple[float, float, float], rotation: Matrix = IDENTITY
) -> PlacedBlock:
    dimensions = Dimensions(*size)
    return PlacedBlock(dimensions, RigidTransform(rotation, Vec3(*at)))


def test_ecart_sur_un_axe() -> None:
    a = block((100, 100, 20), (0, 0, 0))
    b = block((100, 100, 20), (0, 0, 25))  # 5 mm au-dessus
    found = near_gap(a, b)
    assert found is not None
    assert (found.axis, found.side) == (2, 1)
    assert found.distance == pytest.approx(5.0)
    assert (found.b_axis, found.b_low) == (2, True)


def test_cote_oppose_et_face_haute() -> None:
    a = block((100, 100, 20), (0, 0, 25))
    b = block((100, 100, 20), (0, 0, 0))  # b sous a
    found = near_gap(a, b)
    assert found is not None
    assert (found.axis, found.side, found.b_low) == (2, -1, False)


def test_axe_de_b_tourne() -> None:
    a = block((100, 100, 20), (0, 0, 0))
    # b tourné de 90° autour de Z : son axe Y local suit -X global, son axe X local suit +Y
    b = block((100, 40, 20), (140, 0, 0), ROTATION_Z_90)  # occupe x de 100 à 140 : contact
    assert near_gap(a, b) is None  # contact : rien à combler
    b = block((100, 40, 20), (145, 0, 0), ROTATION_Z_90)  # x de 105 à 145 : écart de 5
    found = near_gap(a, b)
    assert found is not None
    assert found.axis == 0
    assert found.b_axis == 1  # largeur de b parallèle à X
    assert found.b_low is False  # +Y local de b suit -X?  vérifié ci-dessous
    assert found.distance == pytest.approx(5.0)


@pytest.mark.parametrize(
    "at",
    [
        (0, 0, 20),  # contact
        (0, 0, 15),  # chevauchement
        (0, 0, 20 + NEAR_GAP_MM + 1),  # trop loin
        (100 + 5, 0, 25),  # écarté sur deux axes
        (100 + 5, 0, 20),  # écart sur X, contact sur Z : arête contre arête
    ],
)
def test_pas_d_ecart_a_combler(at: tuple[float, float, float]) -> None:
    assert near_gap(block((100, 100, 20), (0, 0, 0)), block((100, 100, 20), at)) is None


def test_pieces_en_biais_ignorees() -> None:
    c, s = math.cos(math.radians(30)), math.sin(math.radians(30))
    tilted = ((c, -s, 0.0), (s, c, 0.0), (0.0, 0.0, 1.0))
    assert (
        near_gap(block((100, 100, 20), (0, 0, 0)), block((100, 100, 20), (0, 0, 25), tilted))
        is None
    )


def test_seuil_personnalise() -> None:
    a = block((100, 100, 20), (0, 0, 0))
    b = block((100, 100, 20), (0, 0, 30))  # 10 mm
    assert near_gap(a, b, max_gap=5.0) is None
    assert near_gap(a, b, max_gap=10.0) is not None
