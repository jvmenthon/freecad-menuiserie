# SPDX-License-Identifier: LGPL-2.1-or-later
"""Ensemble à la souris, règles pures (EN-a, critères A1 à A3) : disposition, taille."""

from __future__ import annotations

import math

import pytest

from freecad.menuiserie.core.furniture import (
    furniture_layout,
    resized_box,
    resized_by,
)
from freecad.menuiserie.core.furniture._mouse import MIN_FURNITURE_MM
from freecad.menuiserie.core.geometry import Box, RigidTransform, Vec3
from freecad.menuiserie.core.magnet import Guide, GuideKind, Handle, arrows, resize
from freecad.menuiserie.core.part_model import Dimensions
from freecad.menuiserie.core.rotation import (
    matrix_of,
    ring_of,
    turned_about,
    turned_about_point,
    turned_to,
)
from freecad.menuiserie.core.snap import Frame
from tests.unit.aides import ROOT, imported_modules

BOX = Box.from_ranges([(100, 1300), (50, 650), (0, 720)])
UP = Vec3(0.0, 0.0, 1.0)
WORLD = Frame(Vec3(0.0, 0.0, 0.0), Vec3(1.0, 0.0, 0.0), Vec3(0.0, 1.0, 0.0), UP)
QUARTER = Frame(Vec3(1000.0, 0.0, 0.0), Vec3(0.0, 1.0, 0.0), Vec3(-1.0, 0.0, 0.0), UP)


def xyz(vector: Vec3) -> tuple[float, float, float]:
    return (vector.x, vector.y, vector.z)


# --- A1 : disposition ---------------------------------------------------------------------------


def test_six_poignees_au_milieu_des_faces() -> None:
    layout = furniture_layout(BOX, WORLD, 200.0)
    found = {handle.key: handle for handle in layout.handles}
    assert sorted(found) == ["+X", "+Y", "+Z", "-X", "-Y", "-Z"]
    assert (found["-X"].point.x, found["-X"].point.y, found["-X"].point.z) == (100, 350, 360)
    assert (found["+Z"].point.x, found["+Z"].point.y, found["+Z"].point.z) == (700, 350, 720)
    assert found["-Y"].normal == Vec3(0.0, -1.0, 0.0)
    assert found["+X"].handle == Handle(0, True)


def test_la_disposition_suit_le_repere() -> None:
    layout = furniture_layout(BOX, QUARTER, 200.0)
    found = {handle.key: handle for handle in layout.handles}
    # x local → y global : la face -X (x local 100) est à y global 100, centrée ailleurs
    assert found["-X"].point.y == pytest.approx(100.0)
    assert found["-X"].point.x == pytest.approx(1000.0 - 350.0)
    assert found["+X"].normal == Vec3(0.0, 1.0, 0.0)
    assert found["+Y"].normal == Vec3(-1.0, 0.0, 0.0)


def test_les_fleches_et_les_anneaux_sont_ceux_de_la_piece() -> None:
    layout = furniture_layout(BOX, QUARTER, 200.0)
    assert layout.arrows == arrows(QUARTER, BOX, 200.0)
    expected = tuple(ring_of(BOX, QUARTER.to_transform(), axis) for axis in range(3))
    assert layout.rings == expected
    assert [ring.axis for ring in layout.rings] == [0, 1, 2]
    center = QUARTER.to_transform().apply(Vec3(700.0, 350.0, 360.0))
    assert all(ring.center == center for ring in layout.rings)
    assert all(arrow.start == center for arrow in layout.arrows)


def test_boite_sans_volume_ne_donne_rien() -> None:
    flat = Box.from_ranges([(0, 100), (0, 100), (5, 5)])
    assert furniture_layout(flat, WORLD, 100.0).is_empty
    assert not furniture_layout(BOX, WORLD, 100.0).is_empty


@pytest.mark.parametrize("size", [0.0, -1.0, math.nan, math.inf])
def test_longueur_de_fleche_invalide(size: float) -> None:
    with pytest.raises(ValueError, match="size_mm"):
        furniture_layout(BOX, WORLD, size)


# --- A2 : redimensionnement ---------------------------------------------------------------------


@pytest.mark.parametrize("axis", [0, 1, 2])
def test_la_face_opposee_ne_bouge_pas(axis: int) -> None:
    end = resized_box(BOX, Handle(axis, True), 40.0)
    assert end.lo(axis) == BOX.lo(axis) and end.hi(axis) == BOX.hi(axis) + 40.0
    start = resized_box(BOX, Handle(axis, False), -40.0)
    assert start.hi(axis) == BOX.hi(axis) and start.lo(axis) == BOX.lo(axis) - 40.0
    other = [i for i in range(3) if i != axis]
    assert all(end.ranges()[i] == BOX.ranges()[i] for i in other)


def test_rentrer_une_face_raccourcit() -> None:
    box = resized_box(BOX, Handle(0, False), 300.0)
    assert (box.lo(0), box.hi(0)) == (400.0, 1300.0)


def test_cote_minimale_une_face_de_debut_et_de_fin() -> None:
    end = resized_box(BOX, Handle(1, True), -10_000.0)
    assert end.size(1) == pytest.approx(MIN_FURNITURE_MM) and MIN_FURNITURE_MM == 0.1
    assert end.lo(1) == BOX.lo(1)
    start = resized_box(BOX, Handle(1, False), 10_000.0)
    assert start.size(1) == pytest.approx(0.1)
    assert start.hi(1) == BOX.hi(1)


@pytest.mark.parametrize("delta", [math.nan, math.inf, -math.inf])
def test_entree_non_finie_refusee(delta: float) -> None:
    with pytest.raises(ValueError, match="fini"):
        resized_box(BOX, Handle(0, True), delta)


def test_resized_by_reprend_un_resultat_aimante() -> None:
    wall = Guide(
        GuideKind.PLANE, Box.from_ranges([(1400, 1400), (0, 700), (0, 800)]), axis=0, sign=-1
    )
    result = resize(BOX, Handle(0, True), 95.0, [wall], 10.0)
    assert result.hit is not None
    assert resized_by(BOX, Handle(0, True), result).hi(0) == pytest.approx(1400.0)
    left = resize(BOX, Handle(0, False), -30.0, [], 10.0)
    assert resized_by(BOX, Handle(0, False), left) == Box.from_ranges(
        [(70, 1300), (50, 650), (0, 720)]
    )


# --- Rotation autour du centre de la boîte ------------------------------------------------------


def test_rotation_autour_d_un_point_garde_le_point() -> None:
    start = RigidTransform(matrix_of((0.0, 0.0, 30.0)), Vec3(500.0, -200.0, 40.0))
    center = Vec3(700.0, 350.0, 360.0)
    for axis in range(3):
        turned = turned_about_point(start, center, axis, 37.0)
        assert xyz(turned.apply(center)) == pytest.approx(xyz(start.apply(center)))
    same = turned_about_point(start, center, 2, 0.0).rotation
    assert [v for row in same for v in row] == pytest.approx(
        [v for row in start.rotation for v in row]
    )


def test_turned_about_est_le_cas_du_centre_de_la_boite() -> None:
    start = RigidTransform(matrix_of((10.0, 20.0, 30.0)), Vec3(1.0, 2.0, 3.0))
    size = Dimensions(300.0, 200.0, 20.0)
    center = Vec3(150.0, 100.0, 10.0)
    assert turned_about(start, size, 1, 45.0) == turned_about_point(start, center, 1, 45.0)


def test_turned_to_pose_la_rotation_demandee() -> None:
    start = RigidTransform(matrix_of((0.0, 0.0, 0.0)), Vec3(100.0, 0.0, 0.0))
    center = Vec3(50.0, 50.0, 50.0)
    rotation = matrix_of((0.0, 0.0, 90.0))
    turned = turned_to(start, center, rotation)
    assert turned.rotation == rotation
    assert xyz(turned.apply(center)) == pytest.approx(xyz(start.apply(center)))


@pytest.mark.parametrize("angle", [math.nan, math.inf])
def test_angle_non_fini_refuse(angle: float) -> None:
    with pytest.raises(ValueError, match="angle"):
        turned_about_point(RigidTransform.identity(), Vec3(0.0, 0.0, 0.0), 0, angle)


# --- A3 : pureté --------------------------------------------------------------------------------


def test_aucun_import_freecad_qt_ni_pivy() -> None:
    path = ROOT / "freecad" / "menuiserie" / "core" / "furniture" / "_mouse.py"
    forbidden = {"FreeCAD", "FreeCADGui", "PySide", "PySide2", "PySide6", "pivy"}
    assert not {name.split(".")[0] for name in imported_modules(path)} & forbidden
