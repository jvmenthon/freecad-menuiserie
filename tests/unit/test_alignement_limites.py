# SPDX-License-Identifier: LGPL-2.1-or-later
"""Alignement de deux faces (AL-a, ADR 0054) : cas limites de ``core/align`` (testeur)."""

from __future__ import annotations

import math

import pytest

from freecad.menuiserie.core.align import Alignment, AlignMode, align
from freecad.menuiserie.core.geometry import Vec3
from freecad.menuiserie.core.snap import FaceTarget, Frame
from freecad.menuiserie.core.vectors import cross, dot, norm, unit


def face(origin: Vec3, normal: Vec3) -> FaceTarget:
    """Face plane de normale sortante ``normal`` (unitaire), repère orthonormé direct."""
    helper = Vec3(1.0, 0.0, 0.0) if abs(normal.x) < 0.9 else Vec3(0.0, 1.0, 0.0)
    x = unit(cross(helper, normal))
    y = cross(normal, x)
    return FaceTarget("Face1", Frame(origin, x, y, normal), (10.0, 10.0), True)


def moved(motion: Alignment, point: Vec3) -> Vec3:
    rel = point - motion.pivot
    return _turn(motion, rel) + motion.pivot + motion.shift


def unit_of(x: float, y: float, z: float) -> Vec3:
    length = math.sqrt(x * x + y * y + z * z)
    return Vec3(x / length, y / length, z / length)


REFERENCE = face(Vec3(0, 0, 10), Vec3(0, 0, 1))


def _turn(motion: Alignment, vector: Vec3) -> Vec3:
    return Vec3.of(
        [sum(r * vector.component(j) for j, r in enumerate(row)) for row in motion.rotation]
    )


@pytest.mark.parametrize("mode", [AlignMode.AUTO, AlignMode.FLUSH, AlignMode.FACING])
def test_faces_deja_alignees_ne_bougent_pas(mode: AlignMode) -> None:
    if mode is AlignMode.FACING:
        moving = face(Vec3(3, 4, 10), Vec3(0, 0, -1))
    else:
        moving = face(Vec3(3, 4, 10), Vec3(0, 0, 1))
    motion = align(REFERENCE, moving, mode)
    assert motion.angle == pytest.approx(0.0)
    assert norm(motion.shift) == pytest.approx(0.0)


@pytest.mark.parametrize("mode", [AlignMode.FLUSH, AlignMode.FACING])
def test_modes_forces_atteignent_la_bonne_orientation(mode: AlignMode) -> None:
    moving = face(Vec3(1, 2, 3), unit_of(2, -1, 1))
    motion = align(REFERENCE, moving, mode)
    normal = _turn(motion, moving.frame.z)
    expected = 1.0 if mode is AlignMode.FLUSH else -1.0
    assert (normal.x, normal.y, normal.z) == pytest.approx((0.0, 0.0, expected), abs=1e-9)
    assert motion.mode is mode
    assert moved(motion, moving.frame.origin).z == pytest.approx(10.0)


def test_a_90_degres_exacts_au_ras() -> None:
    moving = face(Vec3(0, 0, 0), Vec3(1, 0, 0))
    motion = align(REFERENCE, moving)
    assert motion.mode is AlignMode.FLUSH
    assert motion.angle == pytest.approx(90.0)


@pytest.mark.parametrize("degrees", [90.0, 270.0, -90.0])
def test_a_90_degres_avec_bruit_numerique_reste_au_ras(degrees: float) -> None:
    """Les normales lues dans FreeCAD portent du bruit (cos 270° = -1.8e-16) : « à 90° exacts, au
    ras » (ADR 0054, décision 3) ne doit pas dépendre du signe de ce bruit."""
    a = math.radians(degrees)
    moving = face(Vec3(0, 0, 0), Vec3(math.sin(a), 0, math.cos(a)))
    assert align(REFERENCE, moving).mode is AlignMode.FLUSH


def test_faces_opposees_auto_demi_tour_inutile() -> None:
    moving = face(Vec3(0, 0, 50), Vec3(0, 0, -1))
    assert align(REFERENCE, moving).angle == 0.0


def test_quasi_opposees_mode_au_ras_demi_tour_sans_derive() -> None:
    e = 1e-7
    moving = face(Vec3(2, 3, 0), Vec3(math.sin(e), 0, -math.cos(e)))
    motion = align(REFERENCE, moving, AlignMode.FLUSH)
    assert motion.angle == pytest.approx(180.0, abs=1e-4)
    assert moved(motion, moving.frame.origin).z == pytest.approx(10.0)


def test_normales_non_unitaires_acceptees() -> None:
    frame = Frame(Vec3(0, 0, 10), Vec3(1, 0, 0), Vec3(0, 1, 0), Vec3(0, 0, 1))
    motion = align(
        FaceTarget("Face1", frame, (1.0, 1.0), True), face(Vec3(0, 0, 0), unit_of(1, 1, 1))
    )
    assert motion.angle == pytest.approx(math.degrees(math.acos(1 / math.sqrt(3))))


def test_la_pivot_ne_change_pas_de_position_dans_le_plan() -> None:
    """Aucun glissement dans le plan de la face : le point pivot arrive à l'aplomb de lui-même."""
    moving = face(Vec3(7, -3, 90), unit_of(1, 1, 1))
    motion = align(REFERENCE, moving)
    end = moved(motion, moving.frame.origin)
    assert (end.x, end.y) == pytest.approx((7.0, -3.0))


def test_tres_grandes_cotes() -> None:
    moving = face(Vec3(1e9, -1e9, 1e9), unit_of(1, 2, 3))
    motion = align(REFERENCE, moving)
    assert moved(motion, moving.frame.origin).z == pytest.approx(10.0, abs=1e-3)
    assert dot(_turn(motion, moving.frame.z), Vec3(0, 0, 1)) == pytest.approx(1.0)


def test_mouvement_idempotent() -> None:
    """Réaligner une face déjà alignée ne fait rien."""
    moving = face(Vec3(1, 1, 4), unit_of(1, 2, 3))
    motion = align(REFERENCE, moving)
    new_normal = _turn(motion, moving.frame.z)
    again = align(REFERENCE, face(moved(motion, moving.frame.origin), new_normal))
    assert again.angle == pytest.approx(0.0, abs=1e-6)
    assert norm(again.shift) == pytest.approx(0.0, abs=1e-9)
