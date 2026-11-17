# SPDX-License-Identifier: LGPL-2.1-or-later
"""Alignement de deux faces, disposition dans le plan (ADR 0054) : grand côté parallèle à un
axe choisi, puis début, centre ou fin le long des axes choisis."""

from __future__ import annotations

import math

import pytest

from freecad.menuiserie.core.align import (
    NO_LAYOUT,
    AlignError,
    Alignment,
    AlignMode,
    Anchor,
    Layout,
    align,
    crosses_faces,
    face_center,
)
from freecad.menuiserie.core.geometry import Vec3
from freecad.menuiserie.core.snap import FaceTarget, Frame

_X, _Y, _Z = Vec3(1.0, 0.0, 0.0), Vec3(0.0, 1.0, 0.0), Vec3(0.0, 0.0, 1.0)
_IDENTITY = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))


def _top(origin: Vec3, size: tuple[float, float]) -> FaceTarget:
    """Face du dessus (normale +Z), coin ``origin``, ``size`` le long de X et Y."""
    return FaceTarget("Face1", Frame(origin, _X, _Y, _Z), size, True)


def _turned_in_plane(origin: Vec3, degrees: float, size: tuple[float, float]) -> FaceTarget:
    """Face du dessus tournée de ``degrees`` autour de Z."""
    c, s = math.cos(math.radians(degrees)), math.sin(math.radians(degrees))
    return FaceTarget("Face6", Frame(origin, Vec3(c, s, 0), Vec3(-s, c, 0), _Z), size, True)


def _short_x_face(origin: Vec3, degrees: float) -> FaceTarget:
    """Planche de 600 sur 100 dont l'axe ``x`` est sur le petit côté (le grand côté est ``y``)."""
    c, s = math.cos(math.radians(degrees)), math.sin(math.radians(degrees))
    return FaceTarget("Face6", Frame(origin, Vec3(-s, c, 0), Vec3(-c, -s, 0), _Z), (100, 600), True)


def _moved(motion: Alignment, point: Vec3) -> Vec3:
    rel = point - motion.pivot
    turned = Vec3.of(
        [sum(r * rel.component(j) for j, r in enumerate(row)) for row in motion.rotation]
    )
    return turned + motion.pivot + motion.shift


def _direction(motion: Alignment, vector: Vec3) -> Vec3:
    return _moved(motion, vector) - _moved(motion, Vec3(0.0, 0.0, 0.0))


def _xyz(v: Vec3) -> tuple[float, float, float]:
    return (v.x, v.y, v.z)


def _close(a: Vec3, b: Vec3) -> bool:
    return all(math.isclose(p, q, abs_tol=1e-9) for p, q in zip(_xyz(a), _xyz(b), strict=True))


def _span(motion: Alignment, face: FaceTarget, axis: Vec3) -> tuple[float, float]:
    """Étendue (min, max) le long de ``axis`` du rectangle de ``face`` déplacé par ``motion``."""
    f = face.frame
    w, h = f.x.scaled(face.extent[0]), f.y.scaled(face.extent[1])
    corners = (f.origin, f.origin + w, f.origin + h, f.origin + w + h)
    values = [
        sum(a * b for a, b in zip(_xyz(_moved(motion, c)), _xyz(axis), strict=True))
        for c in corners
    ]
    return min(values), max(values)


def _signed_distance(plane: FaceTarget, point: Vec3) -> float:
    rel = point - plane.frame.origin
    n = plane.frame.z
    return rel.x * n.x + rel.y * n.y + rel.z * n.z


def _fixed_and_small() -> tuple[FaceTarget, FaceTarget]:
    return _top(Vec3(0, 0, 10), (100, 40)), _top(Vec3(300, 70, 50), (20, 20))


def _anchors(*pairs: tuple[Vec3, Anchor]) -> Layout:
    return Layout(anchors=pairs)


# --- Sans disposition -----------------------------------------------------------------------


def test_centre_de_la_face_au_milieu_de_son_rectangle() -> None:
    assert face_center(_top(Vec3(10, 20, 5), (100.0, 40.0))) == Vec3(60.0, 40.0, 5.0)


def test_sans_disposition_le_mouvement_ne_change_pas() -> None:
    fixed, moving = _fixed_and_small()
    assert align(fixed, moving) == align(fixed, moving, layout=NO_LAYOUT)


def test_sans_parallele_la_planche_garde_son_angle_meme_alignee() -> None:
    """Demande de jv (2026-11-16) : aligner ne rend plus parallèle de lui-même."""
    fixed = _top(Vec3(0, 0, 20), (600, 100))
    moving = _turned_in_plane(Vec3(200, -150, 20), 30.0, (600, 100))
    motion = align(fixed, moving, layout=_anchors((_X, Anchor.CENTER), (_Y, Anchor.CENTER)))
    assert _close(_direction(motion, moving.frame.x), moving.frame.x)


# --- Début, centre, fin ----------------------------------------------------------------------


def test_centre_sur_un_axe_seulement() -> None:
    fixed, moving = _fixed_and_small()
    motion = align(fixed, moving, layout=_anchors((_X, Anchor.CENTER)))
    assert _close(_moved(motion, face_center(moving)), Vec3(50.0, 80.0, 10.0))


def test_centres_sur_les_deux_axes_du_plan_se_confondent() -> None:
    fixed, moving = _fixed_and_small()
    layout = _anchors((_X, Anchor.CENTER), (_Y, Anchor.CENTER))
    motion = align(fixed, moving, AlignMode.FLUSH, layout=layout)
    assert _close(_moved(motion, face_center(moving)), face_center(fixed))


@pytest.mark.parametrize(
    ("anchor", "expected"),
    [(Anchor.START, (0.0, 20.0)), (Anchor.CENTER, (40.0, 60.0)), (Anchor.END, (80.0, 100.0))],
    ids=["debut", "centre", "fin"],
)
def test_debut_centre_fin_sur_x(anchor: Anchor, expected: tuple[float, float]) -> None:
    fixed, moving = _fixed_and_small()
    motion = align(fixed, moving, layout=_anchors((_X, anchor)))
    assert _span(motion, moving, _X) == pytest.approx(expected)
    assert _span(motion, moving, _Y) == pytest.approx((70.0, 90.0))  # Y inchangé


def test_fin_sur_y_et_debut_sur_x() -> None:
    fixed, moving = _fixed_and_small()
    motion = align(fixed, moving, layout=_anchors((_X, Anchor.START), (_Y, Anchor.END)))
    assert _span(motion, moving, _X) == pytest.approx((0.0, 20.0))
    assert _span(motion, moving, _Y) == pytest.approx((20.0, 40.0))


def test_debut_suit_le_sens_de_l_axe_pas_le_repere_de_la_face() -> None:
    """Le repère d'une face part du coin le plus proche du clic : « début » reste le côté moins
    de l'axe quel que soit ce coin."""
    fixed = FaceTarget(
        "F", Frame(Vec3(100, 40, 10), Vec3(-1, 0, 0), Vec3(0, -1, 0), _Z), (100, 40), True
    )
    moving = _top(Vec3(300, 70, 50), (20, 20))
    motion = align(fixed, moving, layout=_anchors((_X, Anchor.START)))
    assert _span(motion, moving, _X) == pytest.approx((0.0, 20.0))


def test_alignement_apres_rotation_hors_du_plan() -> None:
    fixed = _top(Vec3(0, 0, 0), (100, 40))
    side = FaceTarget("Face2", Frame(Vec3(200, 0, 30), _Y, _Z, _X), (40, 20), True)
    layout = _anchors((_X, Anchor.END), (_Y, Anchor.START))
    motion = align(fixed, side, AlignMode.FLUSH, layout=layout)
    assert motion.angle == pytest.approx(90.0)
    assert _span(motion, side, _X)[1] == pytest.approx(100.0)
    assert _span(motion, side, _Y)[0] == pytest.approx(0.0)


def test_alignement_avec_un_axe_de_deplacement_et_l_ecart_normal() -> None:
    fixed, moving = _fixed_and_small()
    layout = _anchors((_X, Anchor.CENTER), (_Y, Anchor.CENTER))
    motion = align(fixed, moving, axis=_Z, layout=layout)
    assert motion.rotation == _IDENTITY
    assert _close(_moved(motion, face_center(moving)), face_center(fixed))


def test_axe_non_unitaire_est_normalise() -> None:
    fixed, moving = _fixed_and_small()
    scaled = align(fixed, moving, layout=_anchors((Vec3(5, 0, 0), Anchor.END)))
    assert scaled == align(fixed, moving, layout=_anchors((_X, Anchor.END)))


@pytest.mark.parametrize(
    "axis", [Vec3(0, 0, 0), Vec3(math.nan, 0, 0), Vec3(math.inf, 0, 0)], ids=["nul", "nan", "inf"]
)
def test_axe_invalide_refuse(axis: Vec3) -> None:
    fixed, moving = _fixed_and_small()
    with pytest.raises(AlignError, match="fini et non nul"):
        align(fixed, moving, layout=_anchors((axis, Anchor.CENTER)))
    with pytest.raises(AlignError, match="fini et non nul"):
        align(fixed, moving, layout=Layout(parallel=axis))


def test_decalages_ajoutes_apres_l_alignement() -> None:
    fixed, moving = _fixed_and_small()
    motion = align(fixed, moving, offset=Vec3(7, 0, 5), layout=_anchors((_X, Anchor.START)))
    assert _span(motion, moving, _X) == pytest.approx((7.0, 27.0))
    assert _moved(motion, face_center(moving)).z == pytest.approx(15.0)


@pytest.mark.parametrize("axis", [_X, Vec3(0, 1, 0)], ids=["X", "Y"])
def test_face_inclinee_reste_dans_son_plan(axis: Vec3) -> None:
    """Un alignement sur un axe oblique à la face ne la sort pas du plan de référence."""
    s = math.sqrt(0.5)
    fixed = FaceTarget(
        "F", Frame(Vec3(0, 0, 0), _X, Vec3(0, s, s), Vec3(0, -s, s)), (100, 40), True
    )
    moving = _top(Vec3(300, 70, 50), (20, 20))
    motion = align(fixed, moving, layout=_anchors((axis, Anchor.CENTER)))
    assert _signed_distance(fixed, _moved(motion, face_center(moving))) == pytest.approx(
        0.0, abs=1e-9
    )


def test_axes_non_perpendiculaires_refuses() -> None:
    fixed, moving = _fixed_and_small()
    with pytest.raises(AlignError, match="perpendiculaires entre eux"):
        align(fixed, moving, layout=_anchors((_X, Anchor.START), (Vec3(1, 1, 0), Anchor.END)))


# --- Doute D9 : un axe qui suit la normale --------------------------------------------------


def test_axe_qui_suit_la_normale_est_reconnu() -> None:
    fixed, _moving = _fixed_and_small()
    assert crosses_faces(_Z, fixed)
    assert crosses_faces(Vec3(0.01, 0, 1), fixed)  # presque
    assert not crosses_faces(_X, fixed)
    assert not crosses_faces(Vec3(1, 0, 1), fixed)  # oblique : utilisable


@pytest.mark.parametrize(
    "layout",
    [Layout(anchors=((_Z, Anchor.CENTER),)), Layout(parallel=_Z)],
    ids=["alignement", "parallele"],
)
def test_axe_de_la_normale_refuse_avec_un_message(layout: Layout) -> None:
    fixed, moving = _fixed_and_small()
    with pytest.raises(AlignError, match="traverse les faces"):
        align(fixed, moving, layout=layout)


# --- Rendre parallèle -------------------------------------------------------------------------


@pytest.mark.parametrize("degrees", [10.0, 80.0, 100.0, -60.0, 170.0])
@pytest.mark.parametrize("axis", [_X, _Y], ids=["X", "Y"])
def test_grand_cote_parallele_a_l_axe_choisi(degrees: float, axis: Vec3) -> None:
    fixed = _top(Vec3(0, 0, 20), (600, 100))
    for moving in (
        _turned_in_plane(Vec3(200, -150, 20), degrees, (600, 100)),
        _short_x_face(Vec3(200, -150, 20), degrees),
    ):
        motion = align(fixed, moving, layout=Layout(parallel=axis))
        long_side = moving.frame.x if moving.extent[0] > moving.extent[1] else moving.frame.y
        edge = _direction(motion, long_side)
        assert abs(edge.x * axis.x + edge.y * axis.y) == pytest.approx(1.0, abs=1e-9)
        assert edge.z == pytest.approx(0.0, abs=1e-9)


def test_parallele_tourne_du_plus_petit_angle() -> None:
    fixed = _top(Vec3(0, 0, 20), (600, 100))
    moving = _turned_in_plane(Vec3(200, -150, 20), 30.0, (600, 100))
    assert _close(_direction(align(fixed, moving, layout=Layout(parallel=_X)), moving.frame.x), _X)
    # Vers Y : 30° → 90° (60°), pas -90°.
    assert _close(_direction(align(fixed, moving, layout=Layout(parallel=_Y)), moving.frame.x), _Y)


def test_parallele_ignore_les_cotes_de_la_reference() -> None:
    """La référence a son grand côté le long de X ; « // Y » met quand même la pièce le long de Y
    (deux planches en T, au choix de l'utilisateur)."""
    fixed = _top(Vec3(0, 0, 20), (600, 100))
    moving = _turned_in_plane(Vec3(200, -150, 20), 10.0, (600, 100))
    edge = _direction(align(fixed, moving, layout=Layout(parallel=_Y)), moving.frame.x)
    assert abs(edge.y) == pytest.approx(1.0, abs=1e-9)


def test_parallele_puis_centres_confondus() -> None:
    fixed = _top(Vec3(0, 0, 20), (600, 100))
    moving = _turned_in_plane(Vec3(200, -150, 50), 30.0, (600, 100))
    layout = Layout(_X, ((_X, Anchor.CENTER), (_Y, Anchor.CENTER)))
    motion = align(fixed, moving, AlignMode.FLUSH, layout=layout)
    assert _close(_direction(motion, moving.frame.x), _X)
    assert _close(_moved(motion, face_center(moving)), face_center(fixed))


@pytest.mark.parametrize("degrees", [45.0, -45.0, 135.0, 225.0])
def test_egalite_a_45_degres_est_deterministe_et_parallele(degrees: float) -> None:
    fixed = _top(Vec3(0, 0, 20), (600, 100))
    moving = _turned_in_plane(Vec3(200, -150, 20), degrees, (600, 100))
    first = align(fixed, moving, AlignMode.FLUSH, layout=Layout(parallel=_X))
    assert first == align(fixed, moving, AlignMode.FLUSH, layout=Layout(parallel=_X))
    edge = _direction(first, moving.frame.x)
    assert abs(edge.x) == pytest.approx(1.0, abs=1e-9)


@pytest.mark.parametrize("degrees", [10.0, 50.0, 100.0, -60.0])
def test_face_mobile_carree_tourne_d_un_quart_de_tour_au_plus(degrees: float) -> None:
    fixed = _top(Vec3(0, 0, 20), (600, 100))
    moving = _turned_in_plane(Vec3(200, -150, 20), degrees, (80, 80))
    motion = align(fixed, moving, layout=Layout(parallel=_X))
    edge = _direction(motion, moving.frame.x)
    assert abs(edge.x * edge.y) == pytest.approx(0.0, abs=1e-9)
    assert motion.angle <= 45.0 + 1e-6


@pytest.mark.parametrize("axis", [_X, _Y], ids=["X", "Y"])
def test_d_equerre_la_normale_mobile_devient_parallele_a_l_axe(axis: Vec3) -> None:
    fixed = _top(Vec3(0, 0, 20), (600, 100))
    side = FaceTarget("F", Frame(Vec3(200, -150, 30), _Y, _Z, _X), (40, 20), True)
    motion = align(fixed, side, AlignMode.PERPENDICULAR, layout=Layout(parallel=axis))
    normal = _direction(motion, side.frame.z)
    assert abs(normal.x * axis.x + normal.y * axis.y) == pytest.approx(1.0, abs=1e-9)


def test_parallele_refuse_sur_un_axe_de_deplacement() -> None:
    fixed, moving = _fixed_and_small()
    with pytest.raises(AlignError, match="rendue parallèle"):
        align(fixed, moving, axis=_Z, layout=Layout(parallel=_X))


def test_parallele_garde_le_pivot_deplace_et_le_plan() -> None:
    """Le tour dans le plan se fait autour du pivot déplacé : il reste dans le plan, décalé."""
    fixed = _top(Vec3(0, 0, 20), (600, 100))
    moving = _turned_in_plane(Vec3(200, -150, 50), 30.0, (600, 100))
    plain = align(fixed, moving, AlignMode.FLUSH, offset=Vec3(0, 0, 5))
    motion = align(fixed, moving, AlignMode.FLUSH, offset=Vec3(0, 0, 5), layout=Layout(parallel=_X))
    assert motion.pivot == plain.pivot
    assert _signed_distance(fixed, _moved(motion, moving.frame.origin)) == pytest.approx(5.0)


@pytest.mark.parametrize("size", [(1e-12, 1e-12), (1e-9, 2e-9)])
def test_etendues_minuscules_ne_plantent_pas(size: tuple[float, float]) -> None:
    fixed = _top(Vec3(0, 0, 20), size)
    moving = _turned_in_plane(Vec3(200, -150, 20), 30.0, size)
    layout = Layout(_X, ((_X, Anchor.CENTER), (_Y, Anchor.CENTER)))
    motion = align(fixed, moving, layout=layout)
    assert _close(_moved(motion, face_center(moving)), face_center(fixed))
