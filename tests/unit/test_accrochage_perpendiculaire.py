# SPDX-License-Identifier: LGPL-2.1-or-later
"""Pièce créée perpendiculairement à la face d'une autre pièce (#136) : géométrie pure."""

from __future__ import annotations

import pytest

from freecad.menuiserie.core.geometry import Matrix3, Vec3
from freecad.menuiserie.core.part_model import Dimensions
from freecad.menuiserie.core.snap import (
    FaceTarget,
    Frame,
    perpendicular_orientation,
    snap,
    support_rotation,
)

X, Y, Z = Vec3(1, 0, 0), Vec3(0, 1, 0), Vec3(0, 0, 1)
MINUS_X = Vec3(-1, 0, 0)
IDENTITY: Matrix3 = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
# Pièce portant la face : 800 x 100 x 30 à l'origine ; la nouvelle a 500 de long, même section.
NEW = Dimensions(500, 100, 30)


def face(origin: Vec3, x: Vec3, y: Vec3, normal: Vec3) -> FaceTarget:
    return FaceTarget("Face", Frame(origin, x, y, normal), (100.0, 30.0), planar=True)


def occupied(target: FaceTarget, owner: Matrix3 = IDENTITY) -> tuple[Vec3, Vec3]:
    """Boîte (minimum, maximum) occupée par la nouvelle pièce posée contre ``target``."""
    support = support_rotation([target])
    assert support is not None
    orientation = perpendicular_orientation(support, owner)
    assert orientation is not None
    placement = snap(NEW, orientation, [target]).placement
    corners = [
        placement.apply(Vec3(a * 500, b * 100, c * 30))
        for a in (0, 1)
        for b in (0, 1)
        for c in (0, 1)
    ]
    low = Vec3(*(min(c.component(i) for c in corners) for i in range(3)))
    high = Vec3(*(max(c.component(i) for c in corners) for i in range(3)))
    return low, high


def test_extremite_angle_droit_avec_la_piece() -> None:
    """Contre l'extrémité (x = 800), la pièce est perpendiculaire à l'autre : sa longueur suit la
    largeur de l'autre (Y), son épaisseur reste selon Z, sa largeur s'appuie sur la face."""
    low, high = occupied(face(Vec3(800, 0, 0), Y, Z, X))
    assert (high.y - low.y, high.z - low.z, high.x - low.x) == (500, 30, 100)
    assert low.x == 800


def test_grande_face_dresse_la_piece_largeur_parallele() -> None:
    """Sur la grande face (z = 30), la longueur monte, la largeur reste selon Y."""
    low, high = occupied(face(Vec3(0, 0, 30), X, Y, Z))
    assert (high.z - low.z, high.y - low.y, high.x - low.x) == (500, 100, 30)
    assert low.z == 30


def test_chant_epaisseur_parallele() -> None:
    """Sur le chant (y = 100), la longueur part du chant, l'épaisseur reste selon Z."""
    low, high = occupied(face(Vec3(0, 100, 0), Z, X, Y))
    assert (high.y - low.y, high.z - low.z, high.x - low.x) == (500, 30, 100)
    assert low.y == 100


def test_face_orientee_vers_moins_x() -> None:
    """La pièce part toujours du côté sortant de la face."""
    target = face(Vec3(0, 0, 0), Z, Y, MINUS_X)
    low, high = occupied(target)
    assert (low.x, high.x) == (-100, 0)


def test_piece_oblique_donne_la_main_a_l_orientation_habituelle() -> None:
    oblique: Matrix3 = ((0.9, -0.43, 0.0), (0.43, 0.9, 0.0), (0.0, 0.0, 1.0))
    assert perpendicular_orientation(IDENTITY, oblique) is None


@pytest.mark.parametrize("quarter", [((0.0, -1.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0))])
def test_piece_tournee_d_un_quart_de_tour(quarter: Matrix3) -> None:
    """La pièce de départ tournée de 90° autour de Z : la face +Y est son extrémité."""
    target = face(Vec3(0, 800, 0), Z, X, Y)  # normale +Y = longueur de la pièce tournée
    low, high = occupied(target, quarter)
    assert (low.y, high.y) == (800, 900)
