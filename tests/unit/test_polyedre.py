# SPDX-License-Identifier: LGPL-2.1-or-later
"""Polyèdre convexe : boîte dans un repère quelconque coupée par des demi-espaces (AB-a, A1)."""

from __future__ import annotations

import math

import pytest

from freecad.menuiserie.core._polyhedron import Plane, Polyhedron, clipped_box
from freecad.menuiserie.core.geometry import Box, RigidTransform, Vec3
from tests.unit.aides_assemblages import matrix, rotation_z
from tests.unit.aides_biais import product, rotation_x, rotation_y

CUBE = Box(Vec3(0.0, 0.0, 0.0), Vec3(100.0, 100.0, 100.0))
IDENTITY = RigidTransform.identity()


def pose(rotation: list[list[float]], base: tuple[float, float, float]) -> RigidTransform:
    return RigidTransform.from_matrix(matrix(rotation, base))


def test_boite_nue_huit_sommets_six_faces_volume() -> None:
    cube = Polyhedron(CUBE, IDENTITY)
    assert len(cube.vertices()) == 8
    assert len(cube.faces()) == 6
    assert cube.volume() == pytest.approx(1e6)


def test_la_rotation_du_repere_ne_change_pas_le_volume() -> None:
    frame = pose(product(rotation_z(33.0), rotation_y(17.0), rotation_x(5.0)), (10.0, -4.0, 7.0))
    assert Polyhedron(CUBE, frame).volume() == pytest.approx(1e6)


def test_coin_coupe_est_un_tetraedre() -> None:
    plane = Plane(Vec3(60.0, 0.0, 0.0), Vec3(1.0, 1.0, 1.0))
    corner = clipped_box(CUBE, IDENTITY, (plane,))
    assert corner is not None
    assert len(corner.vertices()) == 4
    assert corner.volume() == pytest.approx(60.0**3 / 6)


def test_biseau_par_le_milieu_garde_la_moitie() -> None:
    plane = Plane(Vec3(50.0, 50.0, 50.0), Vec3(1.0, 1.0, 0.0))
    half = clipped_box(CUBE, IDENTITY, (plane,))
    assert half is not None
    assert half.volume() == pytest.approx(5e5)


def test_double_biseau_deux_plans() -> None:
    first = Plane(Vec3(50.0, 0.0, 0.0), Vec3(1.0, 0.0, 0.0))
    second = Plane(Vec3(0.0, 50.0, 0.0), Vec3(0.0, 1.0, 0.0))
    quarter = clipped_box(CUBE, IDENTITY, (first, second))
    assert quarter is not None
    assert quarter.volume() == pytest.approx(25e4)


def test_plan_confondu_avec_une_face_ne_change_rien() -> None:
    plane = Plane(Vec3(100.0, 0.0, 0.0), Vec3(1.0, 0.0, 0.0))
    same = clipped_box(CUBE, IDENTITY, (plane,))
    assert same is not None
    assert same.volume() == pytest.approx(1e6)
    assert len(same.faces()) == 6


def test_polyedre_vide_ou_trop_mince_est_none() -> None:
    assert clipped_box(CUBE, IDENTITY, (Plane(Vec3(-5.0, 0.0, 0.0), Vec3(1.0, 0.0, 0.0)),)) is None
    sliver = Plane(Vec3(0.005, 0.0, 0.0), Vec3(1.0, 0.0, 0.0))
    assert clipped_box(CUBE, IDENTITY, (sliver,)) is None


def test_moved_conserve_le_volume_et_deplace_les_sommets() -> None:
    plane = Plane(Vec3(60.0, 0.0, 0.0), Vec3(1.0, 1.0, 1.0))
    corner = Polyhedron(CUBE, IDENTITY, (plane,))
    shift = pose(product(rotation_z(90.0)), (5.0, 0.0, 0.0))
    other = corner.moved(shift)
    assert other.volume() == pytest.approx(corner.volume())
    expected = {rounded(shift.apply(v)) for v in corner.vertices()}
    assert {rounded(v) for v in other.vertices()} == expected


def rounded(point: Vec3) -> tuple[float, float, float]:
    return (round(point.x, 4) + 0.0, round(point.y, 4) + 0.0, round(point.z, 4) + 0.0)


def test_bounds_et_contains() -> None:
    plane = Plane(Vec3(60.0, 0.0, 0.0), Vec3(1.0, 1.0, 1.0))
    corner = Polyhedron(CUBE, IDENTITY, (plane,))
    assert corner.bounds().size(0) == pytest.approx(60.0)
    assert corner.contains(Vec3(5.0, 5.0, 5.0))
    assert not corner.contains(Vec3(50.0, 50.0, 50.0))


def test_plan_invalide_refuse() -> None:
    with pytest.raises(ValueError, match="plan"):
        Plane(Vec3(0.0, 0.0, 0.0), Vec3(0.0, 0.0, 0.0))
    with pytest.raises(ValueError, match="plan"):
        Plane(Vec3(math.nan, 0.0, 0.0), Vec3(1.0, 0.0, 0.0))


def test_trop_de_plans_refuse() -> None:
    planes = tuple(Plane(Vec3(float(i), 0.0, 0.0), Vec3(1.0, 0.0, 0.0)) for i in range(7))
    with pytest.raises(ValueError, match="plans"):
        Polyhedron(CUBE, IDENTITY, planes)
