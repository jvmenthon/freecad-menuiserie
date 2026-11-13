# SPDX-License-Identifier: LGPL-2.1-or-later
"""Alignement de deux faces (AL-a, ADR 0054) : règles pures."""

from __future__ import annotations

import math

import pytest

from freecad.menuiserie.core.align import AlignError, Alignment, AlignMode, align
from freecad.menuiserie.core.geometry import Vec3
from freecad.menuiserie.core.snap import FaceTarget, Frame
from freecad.menuiserie.core.vectors import dot, unit


def _face(origin: Vec3, normal: Vec3, planar: bool = True) -> FaceTarget:
    """Face dont la normale sortante est ``normal`` (unitaire, sur un axe ou un plan diagonal)."""
    helper = Vec3(1.0, 0.0, 0.0) if abs(normal.x) < 0.9 else Vec3(0.0, 1.0, 0.0)
    x = Vec3(
        helper.y * normal.z - helper.z * normal.y,
        helper.z * normal.x - helper.x * normal.z,
        helper.x * normal.y - helper.y * normal.x,
    )
    y = Vec3(
        normal.y * x.z - normal.z * x.y,
        normal.z * x.x - normal.x * x.z,
        normal.x * x.y - normal.y * x.x,
    )
    return FaceTarget("Face1", Frame(origin, unit(x), unit(y), normal), (10.0, 10.0), planar)


def _apply(motion: Alignment, point: Vec3) -> Vec3:
    rel = point - motion.pivot
    turned = Vec3.of(
        [sum(r * rel.component(j) for j, r in enumerate(row)) for row in motion.rotation]
    )
    return turned + motion.pivot + motion.shift


def _unit(x: float, y: float, z: float) -> Vec3:
    length = math.sqrt(x * x + y * y + z * z)
    return Vec3(x / length, y / length, z / length)


def test_faces_deja_paralleles_translation_seule() -> None:
    fixed = _face(Vec3(0, 0, 10), Vec3(0, 0, 1))
    moving = _face(Vec3(5, 5, 40), Vec3(0, 0, 1))
    motion = align(fixed, moving)
    assert motion.angle == 0.0
    assert motion.mode is AlignMode.FLUSH
    assert _apply(motion, moving.frame.origin).z == pytest.approx(10.0)
    assert (motion.shift.x, motion.shift.y) == (0.0, 0.0)  # glisse seulement le long de la normale


def test_face_contre_face_choisi_automatiquement() -> None:
    fixed = _face(Vec3(0, 0, 10), Vec3(0, 0, 1))
    moving = _face(Vec3(0, 0, 40), Vec3(0, 0, -1))
    motion = align(fixed, moving)
    assert (motion.angle, motion.mode) == (0.0, AlignMode.FACING)
    assert _apply(motion, moving.frame.origin).z == pytest.approx(10.0)


def test_mode_force_demi_tour() -> None:
    fixed = _face(Vec3(0, 0, 10), Vec3(0, 0, 1))
    moving = _face(Vec3(0, 0, 40), Vec3(0, 0, -1))
    motion = align(fixed, moving, AlignMode.FLUSH)
    assert motion.angle == pytest.approx(180.0)
    turned = Vec3.of(
        [sum(r * c for r, c in zip(row, (0, 0, -1), strict=True)) for row in motion.rotation]
    )
    assert (turned.x, turned.y, turned.z) == pytest.approx((0.0, 0.0, 1.0), abs=1e-9)


def test_rotation_minimale_vers_un_plan_incline() -> None:
    fixed = _face(Vec3(0, 0, 0), Vec3(0, 0, 1))
    normal = _unit(1, 0, 1)  # 45° de la normale de référence
    moving = _face(Vec3(3, 2, 7), normal)
    motion = align(fixed, moving)
    assert motion.angle == pytest.approx(45.0)
    assert motion.mode is AlignMode.FLUSH
    rotated = [
        sum(r * c for r, c in zip(row, (normal.x, normal.y, normal.z), strict=True))
        for row in motion.rotation
    ]
    assert rotated == pytest.approx([0.0, 0.0, 1.0], abs=1e-9)
    assert _apply(motion, moving.frame.origin).z == pytest.approx(0.0, abs=1e-9)


def test_auto_prend_la_plus_petite_rotation() -> None:
    fixed = _face(Vec3(0, 0, 0), Vec3(0, 0, 1))
    moving = _face(Vec3(0, 0, 0), _unit(1, 0, -1))  # 135° du sens de référence, 45° de l'opposé
    motion = align(fixed, moving)
    assert (motion.mode, round(motion.angle, 6)) == (AlignMode.FACING, 45.0)


def test_mouvement_rigide_et_le_plan_est_atteint() -> None:
    fixed = _face(Vec3(1, 2, 3), _unit(1, 2, 2))
    moving = _face(Vec3(9, -4, 6), _unit(-3, 1, 0.5))
    motion = align(fixed, moving)
    for row in motion.rotation:  # matrice orthonormée
        assert dot(Vec3(*row), Vec3(*row)) == pytest.approx(1.0)
    gap = dot(_apply(motion, moving.frame.origin) - fixed.frame.origin, fixed.frame.z)
    assert gap == pytest.approx(0.0, abs=1e-9)


def test_face_non_plane_refusee() -> None:
    fixed = _face(Vec3(0, 0, 0), Vec3(0, 0, 1))
    curved = _face(Vec3(0, 0, 0), Vec3(0, 0, 1), planar=False)
    with pytest.raises(AlignError):
        align(fixed, curved)
    with pytest.raises(AlignError):
        align(curved, fixed)
