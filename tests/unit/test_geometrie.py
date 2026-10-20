# SPDX-License-Identifier: LGPL-2.1-or-later
"""Géométrie pure des assemblages (J3a, critères M1 et M2)."""

from __future__ import annotations

import math

import pytest

from freecad.menuiserie.core.geometry import (
    Axis,
    Box,
    Contact,
    Cylinder,
    JointError,
    Overlap,
    RigidTransform,
    Separated,
    Vec3,
    classify,
    relative_axes,
    to_guest,
    to_host,
)
from tests.unit.aides_assemblages import block, matrix, rail, rotation_z, stile

ORIGIN = Vec3(0.0, 0.0, 0.0)


def close(a: Vec3, b: Vec3) -> bool:
    return all(math.isclose(a.component(i), b.component(i), abs_tol=1e-9) for i in range(3))


# --- M1 : transformations rigides ---------------------------------------------------------


def test_from_matrix_apply() -> None:
    transform = RigidTransform.from_matrix(matrix(rotation_z(90), (60.0, 60.0, 0.0)))
    assert close(transform.apply(Vec3(10.0, 0.0, 5.0)), Vec3(60.0, 70.0, 5.0))


def test_inverse_et_compose() -> None:
    transform = RigidTransform.from_matrix(matrix(rotation_z(90), (1.0, 2.0, 3.0)))
    point = Vec3(4.0, -5.0, 6.0)
    assert close(transform.inverse().apply(transform.apply(point)), point)
    identity = transform.compose(transform.inverse())
    assert close(identity.apply(point), point)
    twice = transform.compose(transform)
    assert close(twice.apply(point), transform.apply(transform.apply(point)))
    assert RigidTransform.identity().apply(point) == point


@pytest.mark.parametrize(
    "rows",
    [[[1.0, 0.0, 0.0, 0.0]] * 3, [[1.0, 0.0, 0.0]] * 4, [[math.nan, 0, 0, 0]] * 4],
    ids=["3 lignes", "3 colonnes", "NaN"],
)
def test_from_matrix_refuse(rows: list[list[float]]) -> None:
    with pytest.raises(ValueError):
        RigidTransform.from_matrix(rows)


@pytest.mark.parametrize(
    ("degrees", "expected"),
    [
        (0.0, (Axis.X_POS, Axis.Y_POS, Axis.Z_POS)),
        (90.0, (Axis.Y_POS, Axis.X_NEG, Axis.Z_POS)),
        (math.degrees(math.pi / 2 + 1e-9), (Axis.Y_POS, Axis.X_NEG, Axis.Z_POS)),
        (180.0, (Axis.X_NEG, Axis.Y_NEG, Axis.Z_POS)),
        (-90.0, (Axis.Y_NEG, Axis.X_POS, Axis.Z_POS)),
    ],
)
def test_relative_axes(degrees: float, expected: tuple[Axis, Axis, Axis]) -> None:
    assert relative_axes(stile(), block((10, 10, 10), degrees_z=degrees)) == expected


def test_relative_axes_ne_depend_que_de_la_rotation_relative() -> None:
    host = block((10, 10, 10), (5.0, 5.0, 5.0), 45.0)
    guest = block((10, 10, 10), (1.0, 2.0, 3.0), 135.0)
    assert relative_axes(host, guest) == (Axis.Y_POS, Axis.X_NEG, Axis.Z_POS)


@pytest.mark.parametrize("degrees", [45.0, 90.01])
def test_relative_axes_refuse_hors_equerre(degrees: float) -> None:
    with pytest.raises(JointError, match="d'équerre") as error:
        relative_axes(stile(), block((10, 10, 10), degrees_z=degrees))
    assert error.value.template.startswith("Les deux pièces doivent être d'équerre")
    assert error.value.params == {}


def test_relative_axes_refuse_axes_confondus() -> None:
    rows = matrix([[1.0, 1.0, 0.0], [0.0, 0.0, 0.0], [0.0, 0.0, 1.0]], (0.0, 0.0, 0.0))
    guest = block((10, 10, 10))
    flat = type(guest)(guest.dimensions, RigidTransform.from_matrix(rows))
    with pytest.raises(JointError):
        relative_axes(stile(), flat)


def test_axes_et_solides() -> None:
    assert Axis.of(1, -2.0) is Axis.Y_NEG
    assert Axis.Z_POS.opposite() is Axis.Z_NEG
    assert Axis.X_NEG.unit() == Vec3(-1.0, 0.0, 0.0)
    with pytest.raises(ValueError):
        Box(Vec3(1.0, 0.0, 0.0), ORIGIN)
    with pytest.raises(ValueError):
        Box(ORIGIN, Vec3(math.inf, 1.0, 1.0))
    with pytest.raises(ValueError):
        Cylinder(ORIGIN, Axis.X_POS, 0.0, 10.0)


def test_to_host_et_to_guest() -> None:
    host, guest = stile(), rail()
    box = Box(ORIGIN, Vec3(10.0, 20.0, 5.0))
    assert to_host(host, guest, box) == Box(Vec3(40.0, 60.0, 0.0), Vec3(60.0, 70.0, 5.0))
    assert to_guest(host, guest, to_host(host, guest, box)) == box
    cylinder = Cylinder(Vec3(0.0, 30.0, 11.0), Axis.X_NEG, 5.0, 20.0)
    moved = to_host(host, guest, cylinder)
    assert isinstance(moved, Cylinder)
    assert moved.axis is Axis.Y_NEG
    assert close(moved.base, Vec3(30.0, 60.0, 11.0))


# --- M2 : classement --------------------------------------------------------------------


def test_cadre_de_reference_contact() -> None:
    relation = classify(stile(), rail())
    assert isinstance(relation, Contact)
    assert relation.guest_face is Axis.X_NEG
    assert relation.host_face is Axis.Y_POS
    assert relation.rectangle == Box(ORIGIN, Vec3(0.0, 60.0, 22.0))
    assert relation.host_depth == 60.0


@pytest.mark.parametrize(
    ("y", "expected"),
    [(60.005, Contact), (59.995, Contact), (60.02, Separated), (55.0, Overlap)],
    ids=["reculée 0,005", "avancée 0,005", "reculée 0,02", "avancée 5"],
)
def test_classement_selon_l_ecart(y: float, expected: type) -> None:
    assert isinstance(classify(stile(), rail(y=y)), expected)


def test_chevauchement_boite_commune() -> None:
    relation = classify(stile(), rail(y=55.0))
    assert isinstance(relation, Overlap)
    assert relation.common == Box(Vec3(0.0, 55.0, 0.0), Vec3(60.0, 60.0, 22.0))


def test_contact_par_une_arete_ou_un_coin() -> None:
    host = block((100, 100, 20))
    assert isinstance(classify(host, block((50, 50, 20), (100.0, 100.0, 0.0))), Separated)
    assert isinstance(classify(host, block((50, 50, 20), (100.0, 100.0, 20.0))), Separated)


def test_contact_vu_de_l_invitee_au_dessus() -> None:
    relation = classify(block((100, 100, 20)), block((50, 50, 10), (10.0, 10.0, 20.0)))
    assert isinstance(relation, Contact)
    assert (relation.guest_face, relation.host_face) == (Axis.Z_NEG, Axis.Z_POS)
    assert relation.host_depth == 20.0
