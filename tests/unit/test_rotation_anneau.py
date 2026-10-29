# SPDX-License-Identifier: LGPL-2.1-or-later
"""Rotation d'une pièce (RO-a, critères A4 et A5) : anneaux, survol, angle parcouru."""

from __future__ import annotations

import math

import pytest

from freecad.menuiserie.core.geometry import Box, RigidTransform, Vec3
from freecad.menuiserie.core.magnet import Ray
from freecad.menuiserie.core.rotation import (
    MAX_RING_RADIUS_MM,
    MIN_RING_RADIUS_MM,
    matrix_of,
    ring_angle,
    ring_hit,
    ring_of,
)
from tests.unit.aides import ROOT, imported_modules

BOX = Box.from_ranges([(0, 300), (0, 400), (0, 1200)])  # demi-diagonale 650
PLACED = RigidTransform(matrix_of((0.0, 0.0, 0.0)), Vec3(1000.0, 2000.0, 3000.0))
PACKAGE = ROOT / "freecad" / "menuiserie" / "core" / "rotation"


def from_above(x: float, y: float) -> Ray:
    """Rayon vertical descendant, sur le plan XY de l'anneau de l'axe Z."""
    return Ray(Vec3(x, y, 10_000.0), Vec3(0.0, 0.0, -1.0))


def test_anneau_centre_sur_la_boite() -> None:
    for axis in range(3):
        ring = ring_of(BOX, PLACED, axis)
        assert (ring.center.x, ring.center.y, ring.center.z) == (1150.0, 2200.0, 3600.0)
        assert ring.normal.component(axis) == 1.0
        assert ring.axis == axis
        assert ring.radius == pytest.approx(1.15 * 650.0)


def test_centre_suit_la_rotation() -> None:
    turned = RigidTransform(matrix_of((0.0, 0.0, 90.0)), Vec3(0.0, 0.0, 0.0))
    ring = ring_of(Box.from_ranges([(0, 100), (0, 40), (0, 20)]), turned, 2)
    assert (ring.center.x, ring.center.y, ring.center.z) == pytest.approx((-20.0, 50.0, 10.0))


def test_rayon_minimal_et_plafonne() -> None:
    tiny = ring_of(Box.from_ranges([(0, 5), (0, 5), (0, 5)]), PLACED, 0)
    assert tiny.radius == MIN_RING_RADIUS_MM
    huge = ring_of(Box.from_ranges([(0, 1e6), (0, 1e6), (0, 1e6)]), PLACED, 0)
    assert huge.radius == MAX_RING_RADIUS_MM


def test_axe_invalide() -> None:
    with pytest.raises(ValueError, match="axis"):
        ring_of(BOX, PLACED, 3)


def test_survol_de_l_anneau() -> None:
    ring = ring_of(BOX, PLACED, 2)
    cx, cy, r = ring.center.x, ring.center.y, ring.radius
    assert ring_hit(from_above(cx + r, cy), ring, 1.0)
    assert ring_hit(from_above(cx + r + 4.0, cy), ring, 5.0)
    assert not ring_hit(from_above(cx + r + 6.0, cy), ring, 5.0)
    assert not ring_hit(from_above(cx, cy), ring, 5.0)  # au centre


def test_survol_incline() -> None:
    ring = ring_of(BOX, PLACED, 2)
    c = ring.center
    target = Vec3(c.x, c.y + ring.radius, c.z)
    origin = Vec3(target.x + 3000.0, target.y, target.z + 3000.0)  # 45° d'incidence
    ray = Ray(origin, Vec3(-1.0, 0.0, -1.0))
    assert ring_hit(ray, ring, 0.001)


def test_anneau_vu_par_la_tranche() -> None:
    ring = ring_of(BOX, PLACED, 2)
    c = ring.center
    grazing = Ray(Vec3(c.x - 5000.0, c.y, c.z + 100.0), Vec3(1.0, 0.0, 0.0))
    assert not ring_hit(grazing, ring, 1e6)
    assert ring_angle(grazing, ring, from_above(c.x + ring.radius, c.y)) is None
    assert ring_angle(from_above(c.x + 1, c.y), ring, grazing) is None


def test_limite_des_5_degres() -> None:
    ring = ring_of(BOX, PLACED, 2)
    c = ring.center

    def tilted(degrees: float) -> Ray:
        a = math.radians(degrees)
        return Ray(Vec3(c.x + ring.radius, c.y, c.z + 10.0), Vec3(0.0, math.cos(a), -math.sin(a)))

    assert ring_angle(tilted(4.0), ring, from_above(c.x + ring.radius, c.y)) is None
    assert ring_angle(tilted(6.0), ring, from_above(c.x + ring.radius, c.y)) is not None


def test_rayon_derriere_l_origine() -> None:
    ring = ring_of(BOX, PLACED, 2)
    c = ring.center
    away = Ray(Vec3(c.x + ring.radius, c.y, c.z + 100.0), Vec3(0.0, 0.0, 1.0))
    assert not ring_hit(away, ring, 5.0)


@pytest.mark.parametrize(("x", "y", "expected"), [(0, 1, 90.0), (-1, 0, 180.0), (0, -1, -90.0)])
def test_angle_signe_parcouru(x: float, y: float, expected: float) -> None:
    ring = ring_of(BOX, PLACED, 2)
    c = ring.center
    start = from_above(c.x + ring.radius, c.y)
    now = from_above(c.x + x * ring.radius, c.y + y * ring.radius)
    assert ring_angle(now, ring, start) == pytest.approx(expected)


def test_angle_nul_au_depart_et_sens_oppose_autour_de_la_normale() -> None:
    ring = ring_of(BOX, PLACED, 1)  # normale +Y : sens direct = de Z vers X
    c = ring.center
    start = Ray(Vec3(c.x, c.y + 5000.0, c.z + ring.radius), Vec3(0.0, -1.0, 0.0))
    assert ring_angle(start, ring, start) == pytest.approx(0.0)
    now = Ray(Vec3(c.x + ring.radius, c.y + 5000.0, c.z), Vec3(0.0, -1.0, 0.0))
    assert ring_angle(now, ring, start) == pytest.approx(90.0)


def test_rayon_par_le_centre() -> None:
    ring = ring_of(BOX, PLACED, 2)
    c = ring.center
    assert ring_angle(from_above(c.x, c.y), ring, from_above(c.x + ring.radius, c.y)) is None


def test_tolerance_invalide() -> None:
    ring = ring_of(BOX, PLACED, 2)
    for bad in (-1.0, math.nan):
        with pytest.raises(ValueError, match="tolerance"):
            ring_hit(from_above(0, 0), ring, bad)


def test_paquet_sans_freecad_ni_qt() -> None:
    """``core/rotation/`` reste du Python pur (règle FreeCAD n° 1, critère A5)."""
    forbidden = ("FreeCAD", "FreeCADGui", "Part", "PySide", "PySide2", "PySide6", "pivy")
    files = sorted(PACKAGE.glob("*.py"))
    assert len(files) == 4
    for path in files:
        modules = imported_modules(path, ROOT)
        assert not [m for m in modules if m.split(".")[0] in forbidden], path.name
