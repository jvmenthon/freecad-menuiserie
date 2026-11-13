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
from freecad.menuiserie.gui.drag.rings import ring_basis

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


@pytest.mark.parametrize("axis", [0, 1, 2])
@pytest.mark.parametrize("sign", [1.0, -1.0])
def test_alignment_on_each_ring_axis(axis: int, sign: float) -> None:
    """De bout en bout : l'offset trouvé, appliqué autour de l'axe, aligne les arêtes."""
    normal = Vec3(*(sign if i == axis else 0.0 for i in range(3)))
    u, v = ring_basis(normal)
    angles = [0.0, 0.0, 0.0]
    angles[axis] = 30.0
    neighbor = matrix_of((angles[0], angles[1], angles[2]))
    (offset,) = align_offsets(matrix_of((0.0, 0.0, 0.0)), [neighbor], u, v)
    angles[axis] = sign * offset  # rotation directe autour de ``normal``
    turned = matrix_of((angles[0], angles[1], angles[2]))
    assert edge_angles(turned, u, v) == pytest.approx(edge_angles(neighbor, u, v))


def test_tilted_edges_are_ignored() -> None:
    """Une arête à 45° du plan de l'anneau ne compte pas (projection sans sens visuel)."""
    tilted = matrix_of((45.0, 0.0, 0.0))  # Y et Z à 45° du plan XY
    assert edge_angles(tilted, U, V) == pytest.approx((0.0,))


def test_every_own_edge_gives_an_offset() -> None:
    """Pièce inclinée : chaque arête proche du plan donne sa rotation d'alignement."""
    own = matrix_of((20.0, 0.0, 0.0))  # X dans le plan, Y à 20° du plan : projections à 90°
    offsets = align_offsets(own, [matrix_of((0.0, 0.0, 37.0))], U, V)
    assert offsets == pytest.approx((37.0,))


def test_aligned_turn_edges() -> None:
    assert aligned_turn(40.0, (37.0,)) == pytest.approx(37.0)  # tolérance exacte
    assert aligned_turn(40.01, (37.0,)) is None
    assert aligned_turn(-38.0, (52.0,)) == pytest.approx(-38.0)  # 52 - 90
    assert aligned_turn(11.0, (10.0, 12.5)) == pytest.approx(10.0)  # le plus proche
    assert aligned_turn(float("nan"), (10.0,)) is None
