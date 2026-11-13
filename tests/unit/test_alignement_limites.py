# SPDX-License-Identifier: LGPL-2.1-or-later
"""Alignement de deux faces (AL-a, ADR 0054) : cas limites de ``core/align`` (testeur)."""

from __future__ import annotations

import math

import pytest

from freecad.menuiserie.core.align import AlignError, Alignment, AlignMode, align
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


# --- Alignement sur un axe ---------------------------------------------------------------------


def test_sur_un_axe_oblique_atteint_le_plan_sans_toucher_aux_autres_composantes() -> None:
    moving = face(Vec3(5, 5, 40), Vec3(0, 0, 1))
    axis = unit_of(1, 2, 2)
    motion = align(REFERENCE, moving, axis=axis)
    end = moved(motion, moving.frame.origin)
    assert end.z == pytest.approx(10.0)
    assert motion.angle == 0.0
    shift = motion.shift
    assert abs(dot(shift, axis)) == pytest.approx(norm(shift))  # colinéaire à l'axe
    assert (shift.x, shift.y) == pytest.approx((shift.z / 2, shift.z))


def test_sur_un_axe_non_unitaire_equivaut_a_l_axe_unitaire() -> None:
    moving = face(Vec3(0, 0, 40), Vec3(0, 0, 1))
    short = align(REFERENCE, moving, axis=Vec3(0, 0, 1))
    long = align(REFERENCE, moving, axis=Vec3(0, 0, 250))
    assert (long.shift.x, long.shift.y) == pytest.approx((0.0, 0.0))
    assert long.shift.z == pytest.approx(short.shift.z)


def test_sur_un_axe_sens_negatif_donne_le_meme_deplacement() -> None:
    moving = face(Vec3(1, 2, 40), unit_of(0, 0, 1))
    up = align(REFERENCE, moving, axis=unit_of(0, 1, 1))
    down = align(REFERENCE, moving, axis=unit_of(0, -1, -1))
    assert (down.shift.x, down.shift.y, down.shift.z) == pytest.approx(
        (up.shift.x, up.shift.y, up.shift.z)
    )


@pytest.mark.parametrize("axis", [Vec3(1, 0, 0), Vec3(0, 1, 0), unit_of(1, 1, 0)])
def test_sur_un_axe_dans_le_plan_refuse(axis: Vec3) -> None:
    moving = face(Vec3(0, 0, 40), Vec3(0, 0, 1))
    with pytest.raises(AlignError):
        align(REFERENCE, moving, axis=axis)


@pytest.mark.parametrize("slope", [1e-12, 0.01, 0.049])
def test_sur_un_axe_quasi_dans_le_plan_refuse_sans_deplacement_gigantesque(slope: float) -> None:
    moving = face(Vec3(0, 0, 40), Vec3(0, 0, 1))
    with pytest.raises(AlignError):
        align(REFERENCE, moving, axis=unit_of(1, 0, slope))


def test_sur_un_axe_pente_suffisante_acceptee_et_deplacement_borne() -> None:
    moving = face(Vec3(0, 0, 40), Vec3(0, 0, 1))
    motion = align(REFERENCE, moving, axis=unit_of(1, 0, 0.06))
    assert moved(motion, moving.frame.origin).z == pytest.approx(10.0)
    assert norm(motion.shift) < 30.0 / 0.05 + 1.0


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
@pytest.mark.parametrize("axis", [None, Vec3(0, 0, 1)])
def test_decalage_non_fini_refuse(bad: float, axis: Vec3 | None) -> None:
    moving = face(Vec3(0, 0, 40), Vec3(0, 0, 1))
    for offset in (Vec3(bad, 0, 0), Vec3(0, bad, 0), Vec3(0, 0, bad)):
        with pytest.raises(AlignError):
            align(REFERENCE, moving, offset=offset, axis=axis)


def test_sur_un_axe_nul_refuse() -> None:
    """Un axe nul ne doit jamais produire de division par zéro non traduite."""
    moving = face(Vec3(0, 0, 40), Vec3(0, 0, 1))
    with pytest.raises(AlignError):
        align(REFERENCE, moving, axis=Vec3(0, 0, 0))


@pytest.mark.parametrize("normal", [unit_of(1, 0, 1), unit_of(0, 1, 5), Vec3(1, 0, 0)])
def test_sur_un_axe_faces_non_paralleles_refusees(normal: Vec3) -> None:
    moving = face(Vec3(0, 0, 40), normal)
    with pytest.raises(AlignError):
        align(REFERENCE, moving, axis=Vec3(0, 0, 1))


def test_sur_un_axe_faces_opposees_acceptees_sans_rotation() -> None:
    moving = face(Vec3(0, 0, 40), Vec3(0, 0, -1))
    motion = align(REFERENCE, moving, axis=Vec3(0, 0, 1))
    assert motion.angle == 0.0
    assert motion.rotation == ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
    assert moved(motion, moving.frame.origin).z == pytest.approx(10.0)
    assert motion.mode is AlignMode.FACING


def test_sur_un_axe_non_planes_refuse_avant_l_axe() -> None:
    curved = FaceTarget("Face1", REFERENCE.frame, (1.0, 1.0), False)
    with pytest.raises(AlignError):
        align(REFERENCE, curved, axis=Vec3(0, 0, 1))


@pytest.mark.parametrize("normal_z", [1.0, -1.0])
def test_sur_un_axe_mode_d_equerre_refuse(normal_z: float) -> None:
    """« D'équerre » exigerait une rotation : refusé sur un axe, quelle que soit l'orientation."""
    moving = face(Vec3(2, 3, 40), Vec3(0, 0, normal_z))
    with pytest.raises(AlignError):
        align(REFERENCE, moving, AlignMode.PERPENDICULAR, axis=Vec3(0, 0, 1))


@pytest.mark.parametrize("mode", [AlignMode.AUTO, AlignMode.FLUSH, AlignMode.FACING])
def test_sur_un_axe_autres_modes_acceptes_sans_rotation(mode: AlignMode) -> None:
    moving = face(Vec3(2, 3, 40), Vec3(0, 0, 1))
    motion = align(REFERENCE, moving, mode, axis=Vec3(0, 0, 1))
    assert motion.angle == 0.0
    assert moved(motion, moving.frame.origin).z == pytest.approx(10.0)


def test_sur_un_axe_decalages_x_et_y_ignores() -> None:
    moving = face(Vec3(2, 3, 40), Vec3(0, 0, 1))
    plain = align(REFERENCE, moving, axis=Vec3(0, 0, 1), offset=Vec3(0, 0, 4))
    with_xy = align(REFERENCE, moving, axis=Vec3(0, 0, 1), offset=Vec3(50, -70, 4))
    assert with_xy.shift == plain.shift
    assert moved(with_xy, moving.frame.origin) == Vec3(2.0, 3.0, 14.0)


def test_sur_un_axe_deja_aligne_ne_bouge_pas() -> None:
    moving = face(Vec3(2, 3, 10), Vec3(0, 0, 1))
    motion = align(REFERENCE, moving, axis=unit_of(1, 1, 1))
    assert norm(motion.shift) == pytest.approx(0.0, abs=1e-12)


def test_sur_un_axe_tres_grandes_cotes() -> None:
    moving = face(Vec3(1e9, -1e9, 1e9), Vec3(0, 0, 1))
    motion = align(REFERENCE, moving, axis=unit_of(1, 1, 1))
    assert moved(motion, moving.frame.origin).z == pytest.approx(10.0, abs=1e-3)


def test_sans_axe_inchange_par_le_parametre() -> None:
    moving = face(Vec3(1, 2, 3), unit_of(2, -1, 1))
    assert align(REFERENCE, moving, axis=None) == align(REFERENCE, moving)
