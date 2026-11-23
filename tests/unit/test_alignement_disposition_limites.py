# SPDX-License-Identifier: LGPL-2.1-or-later
"""Alignement de deux faces, cas limites de la disposition (ADR 0066) : plan oblique aux axes,
axes obliques d'un Std Part tourné, repère de référence parti d'un autre coin, équerre."""

from __future__ import annotations

import math

import pytest

from freecad.menuiserie.core.align import (
    AlignError,
    Alignment,
    AlignMode,
    Anchor,
    Layout,
    align,
    crosses_faces,
)
from freecad.menuiserie.core.geometry import Vec3
from freecad.menuiserie.core.snap import FaceTarget, Frame
from freecad.menuiserie.core.vectors import cross, dot, unit

_X, _Y, _Z = Vec3(1.0, 0.0, 0.0), Vec3(0.0, 1.0, 0.0), Vec3(0.0, 0.0, 1.0)


def _moved(motion: Alignment, point: Vec3) -> Vec3:
    rel = point - motion.pivot
    turned = Vec3.of(
        [sum(r * rel.component(j) for j, r in enumerate(row)) for row in motion.rotation]
    )
    return turned + motion.pivot + motion.shift


def _corners(face: FaceTarget) -> list[Vec3]:
    f = face.frame
    w, h = f.x.scaled(face.extent[0]), f.y.scaled(face.extent[1])
    return [f.origin, f.origin + w, f.origin + h, f.origin + w + h]


def _span(face: FaceTarget, axis: Vec3, motion: Alignment | None = None) -> tuple[float, float]:
    points = [c if motion is None else _moved(motion, c) for c in _corners(face)]
    values = [dot(p, axis) for p in points]
    return min(values), max(values)


def _plane(normal: Vec3, origin: Vec3, size: tuple[float, float]) -> FaceTarget:
    """Face de normale ``normal`` dont le repère part de ``origin``."""
    n = unit(normal)
    seed = _X if abs(n.x) < 0.9 else _Y
    x = unit(cross(seed, n))
    return FaceTarget("F", Frame(origin, x, cross(n, x), n), size, True)


def _top(origin: Vec3, size: tuple[float, float], angle: float = 0.0) -> FaceTarget:
    c, s = math.cos(math.radians(angle)), math.sin(math.radians(angle))
    return FaceTarget("F", Frame(origin, Vec3(c, s, 0), Vec3(-s, c, 0), _Z), size, True)


@pytest.mark.parametrize("anchor", list(Anchor))
def test_plan_de_reference_incline_les_deux_axes_d_ancrage_sont_exacts(anchor: Anchor) -> None:
    """Normale (1,1,1) : X et Y se projettent dans le plan sans y être perpendiculaires ; le bord
    ou le centre demandé doit pourtant être exact sur chacun des deux axes."""
    fixed = _plane(Vec3(1, 1, 1), Vec3(0, 0, 0), (100, 60))
    moving = _plane(Vec3(1, 1, 1), Vec3(40, 7, -3), (20, 10))
    motion = align(fixed, moving, layout=Layout(anchors=((_X, anchor), (_Y, anchor))))
    for axis in (_X, _Y):
        want = _span(fixed, axis)
        got = _span(moving, axis, motion)
        expected = {
            Anchor.START: (want[0], got[0]),
            Anchor.END: (want[1], got[1]),
            Anchor.CENTER: ((want[0] + want[1]) / 2, (got[0] + got[1]) / 2),
        }[anchor]
        assert expected[0] == pytest.approx(expected[1], abs=1e-6)


def test_axes_d_ancrage_confondus_dans_le_plan_refuses_ou_coherents() -> None:
    """Normale (0,1,1)/V2 : Y et Z se projettent sur la même droite du plan ; les deux ancrages
    ne peuvent pas être tenus ensemble avec deux valeurs différentes (refus attendu)."""
    s = math.sqrt(0.5)
    fixed = _plane(Vec3(0, s, s), Vec3(0, 0, 0), (100, 60))
    moving = _plane(Vec3(0, s, s), Vec3(40, 7, -3), (20, 10))
    layout = Layout(anchors=((_Y, Anchor.START), (_Z, Anchor.START)))
    with pytest.raises(AlignError):
        align(fixed, moving, layout=layout)


@pytest.mark.parametrize("degrees", [0.0, 25.0, 45.0, 90.0, 135.0, -30.0])
def test_axes_obliques_d_un_std_part_tourne_les_quatre_ancrages(degrees: float) -> None:
    """Std Part tourné autour de Z : axes X', Y' obliques, repère de référence d'un autre coin."""
    c, s = math.cos(math.radians(degrees)), math.sin(math.radians(degrees))
    ax, ay = Vec3(c, s, 0), Vec3(-s, c, 0)
    fixed = _top(Vec3(500, 300, 0), (120, 80), 200.0)  # repère tourné, parti d'un autre coin
    moving = _top(Vec3(-80, 40, 15), (30, 20), 77.0)
    for anchor in Anchor:
        motion = align(fixed, moving, layout=Layout(None, ((ax, anchor), (ay, anchor))))
        for axis in (ax, ay):
            a, b = _span(fixed, axis), _span(moving, axis, motion)
            want = {Anchor.START: (a[0], b[0]), Anchor.END: (a[1], b[1])}.get(
                anchor, ((a[0] + a[1]) / 2, (b[0] + b[1]) / 2)
            )
            assert want[0] == pytest.approx(want[1], abs=1e-6)


@pytest.mark.parametrize("degrees", [0.0, 25.0, 45.0, 120.0])
def test_parallele_sur_un_axe_oblique_du_conteneur(degrees: float) -> None:
    c, s = math.cos(math.radians(degrees)), math.sin(math.radians(degrees))
    axis = Vec3(c, s, 0)
    fixed = _top(Vec3(0, 0, 0), (50, 400), 13.0)
    moving = _top(Vec3(90, -20, 30), (500, 40), 71.0)
    motion = align(fixed, moving, layout=Layout(parallel=axis))
    long = Vec3(math.cos(math.radians(71)), math.sin(math.radians(71)), 0)
    turned = _moved(motion, long) - _moved(motion, Vec3(0, 0, 0))
    assert abs(dot(turned, axis)) == pytest.approx(1.0, abs=1e-9)


def test_parallele_sur_un_axe_oblique_au_plan_est_projete() -> None:
    """Axe (1,0,1) sur une face horizontale : le grand côté devient parallèle à X (projeté)."""
    fixed = _top(Vec3(0, 0, 0), (100, 100))
    moving = _top(Vec3(0, 0, 0), (400, 40), 33.0)
    motion = align(fixed, moving, layout=Layout(parallel=Vec3(1, 0, 1)))
    long = Vec3(math.cos(math.radians(33)), math.sin(math.radians(33)), 0)
    turned = _moved(motion, long) - _moved(motion, Vec3(0, 0, 0))
    assert abs(turned.y) < 1e-9 and abs(turned.z) < 1e-9


def test_equerre_avec_ancrage_garde_la_face_dans_le_plan_de_reference() -> None:
    fixed = _top(Vec3(0, 0, 0), (600, 100))
    moving = FaceTarget("F", Frame(Vec3(300, 50, 80), _X, _Z, Vec3(0, -1, 0)), (40, 80), True)
    layout = Layout(_X, ((_X, Anchor.END), (_Y, Anchor.CENTER)))
    motion = align(fixed, moving, AlignMode.PERPENDICULAR, layout=layout)
    assert _span(moving, _X, motion)[1] == pytest.approx(600.0)
    assert all(math.isfinite(v) for v in (motion.shift.x, motion.shift.y, motion.shift.z))


def test_axe_oblique_juste_au_dessus_de_la_pente_minimale_est_accepte() -> None:
    fixed = _top(Vec3(0, 0, 0), (100, 40))
    assert crosses_faces(Vec3(0.049, 0, 1), fixed)
    assert not crosses_faces(Vec3(0.051, 0, 1), fixed)


@pytest.mark.parametrize("bad", [Vec3(0, 0, 0), Vec3(math.nan, 0, 0), Vec3(math.inf, 0, 0)])
def test_parallele_hostile_refuse(bad: Vec3) -> None:
    fixed = _top(Vec3(0, 0, 0), (100, 40))
    moving = _top(Vec3(0, 0, 5), (50, 20))
    with pytest.raises(AlignError):
        align(fixed, moving, layout=Layout(parallel=bad))


def test_tres_grandes_cotes_restent_finis() -> None:
    fixed = _top(Vec3(0, 0, 0), (1e9, 1e8))
    moving = _top(Vec3(1e6, 1e6, 3), (1e8, 1e7), 40.0)
    motion = align(fixed, moving, layout=Layout(_X, ((_X, Anchor.END), (_Y, Anchor.START))))
    assert _span(moving, _X, motion)[1] == pytest.approx(1e9, rel=1e-9)
