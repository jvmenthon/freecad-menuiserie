# SPDX-License-Identifier: LGPL-2.1-or-later
"""Aimantation de l'angle sur l'orientation des pièces voisines (core/rotation/_align)."""

from __future__ import annotations

import pytest

from freecad.menuiserie.core.geometry import Vec3
from freecad.menuiserie.core.rotation import (
    align_offsets,
    aligned_turn,
    edge_angles,
    matrix_of,
)

U, V = Vec3(1.0, 0.0, 0.0), Vec3(0.0, 1.0, 0.0)


def test_edge_angles_of_a_turned_box() -> None:
    angles = edge_angles(matrix_of((0.0, 0.0, 30.0)), U, V)
    assert angles == pytest.approx((30.0, 30.0))


def test_offsets_align_on_a_neighbor() -> None:
    own = matrix_of((0.0, 0.0, 0.0))
    offsets = align_offsets(own, [matrix_of((0.0, 0.0, 37.0))], U, V)
    assert offsets == pytest.approx((37.0,))


def test_offsets_account_for_own_angle() -> None:
    own = matrix_of((0.0, 0.0, 10.0))
    offsets = align_offsets(own, [matrix_of((0.0, 0.0, 37.0))], U, V)
    assert offsets == pytest.approx((27.0,))


def test_duplicate_neighbors_give_one_offset() -> None:
    same = matrix_of((0.0, 0.0, 37.0))
    assert len(align_offsets(matrix_of((0.0, 0.0, 0.0)), [same, same], U, V)) == 1


def test_no_edge_in_plane_gives_no_offset() -> None:
    assert align_offsets(matrix_of((0.0, 0.0, 0.0)), [], U, V) == ()


@pytest.mark.parametrize(
    ("travelled", "expected"),
    [(35.0, 37.0), (39.5, 37.0), (126.0, 127.0), (-52.0, -53.0), (30.0, None), (44.0, None)],
)
def test_aligned_turn(travelled: float, expected: float | None) -> None:
    assert aligned_turn(travelled, (37.0,)) == (
        pytest.approx(expected) if expected is not None else None
    )


def test_aligned_turn_without_offsets() -> None:
    assert aligned_turn(10.0, ()) is None
