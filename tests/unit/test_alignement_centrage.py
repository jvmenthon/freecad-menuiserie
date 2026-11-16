# SPDX-License-Identifier: LGPL-2.1-or-later
"""Alignement de deux faces, centres alignés sur les axes X, Y, Z cochés (ADR 0054)."""

from __future__ import annotations

import math

import pytest

from freecad.menuiserie.core.align import AlignError, Alignment, AlignMode, align, face_center
from freecad.menuiserie.core.geometry import Vec3
from freecad.menuiserie.core.snap import FaceTarget, Frame

_X, _Y, _Z = Vec3(1.0, 0.0, 0.0), Vec3(0.0, 1.0, 0.0), Vec3(0.0, 0.0, 1.0)


def _top(origin: Vec3, size: tuple[float, float]) -> FaceTarget:
    """Face du dessus (normale +Z), coin ``origin``, ``size`` le long de X et Y."""
    return FaceTarget("Face1", Frame(origin, _X, _Y, _Z), size, True)


def _moved(motion: Alignment, point: Vec3) -> Vec3:
    rel = point - motion.pivot
    turned = Vec3.of(
        [sum(r * rel.component(j) for j, r in enumerate(row)) for row in motion.rotation]
    )
    return turned + motion.pivot + motion.shift


def _close(a: Vec3, b: Vec3) -> bool:
    return all(math.isclose(p, q, abs_tol=1e-9) for p, q in zip(_xyz(a), _xyz(b), strict=True))


def _xyz(v: Vec3) -> tuple[float, float, float]:
    return (v.x, v.y, v.z)


def test_centre_de_la_face_au_milieu_de_son_rectangle() -> None:
    assert face_center(_top(Vec3(10, 20, 5), (100.0, 40.0))) == Vec3(60.0, 40.0, 5.0)


def test_sans_axe_coche_le_mouvement_ne_change_pas() -> None:
    fixed, moving = _top(Vec3(0, 0, 10), (100, 40)), _top(Vec3(300, 70, 50), (20, 20))
    assert align(fixed, moving) == align(fixed, moving, centered=())


def test_un_axe_coche_centre_sur_cet_axe_seulement() -> None:
    fixed, moving = _top(Vec3(0, 0, 10), (100, 40)), _top(Vec3(300, 70, 50), (20, 20))
    centre = _moved(align(fixed, moving, centered=(_X,)), face_center(moving))
    assert _close(centre, Vec3(50.0, 80.0, 10.0))  # X centré, Y inchangé, dans le plan


def test_trois_axes_d_un_coup_confondent_les_centres() -> None:
    fixed, moving = _top(Vec3(0, 0, 10), (100, 40)), _top(Vec3(300, 70, 50), (20, 20))
    motion = align(fixed, moving, AlignMode.FLUSH, centered=(_X, _Y, _Z))
    assert _close(_moved(motion, face_center(moving)), face_center(fixed))


def test_centrage_apres_rotation() -> None:
    fixed = _top(Vec3(0, 0, 0), (100, 40))
    side = FaceTarget("Face2", Frame(Vec3(200, 0, 30), _Y, _Z, _X), (40, 20), True)
    motion = align(fixed, side, AlignMode.FLUSH, centered=(_X, _Y, _Z))
    assert motion.angle == pytest.approx(90.0)
    assert _close(_moved(motion, face_center(side)), face_center(fixed))


def test_centrage_avec_un_axe_et_l_ecart_normal() -> None:
    fixed, moving = _top(Vec3(0, 0, 10), (100, 40)), _top(Vec3(300, 70, 50), (20, 20))
    motion = align(fixed, moving, axis=_Z, centered=(_X, _Y))
    assert motion.angle == 0.0
    assert _close(_moved(motion, face_center(moving)), face_center(fixed))


def test_axe_de_centrage_non_unitaire_est_normalise() -> None:
    fixed, moving = _top(Vec3(0, 0, 10), (100, 40)), _top(Vec3(300, 70, 50), (20, 20))
    assert align(fixed, moving, centered=(Vec3(5, 0, 0),)) == align(fixed, moving, centered=(_X,))


@pytest.mark.parametrize(
    "axis", [Vec3(0, 0, 0), Vec3(math.nan, 0, 0), Vec3(math.inf, 0, 0)], ids=["nul", "nan", "inf"]
)
def test_axe_de_centrage_invalide_refuse(axis: Vec3) -> None:
    fixed, moving = _top(Vec3(0, 0, 10), (100, 40)), _top(Vec3(300, 70, 50), (20, 20))
    with pytest.raises(AlignError, match="fini et non nul"):
        align(fixed, moving, centered=(axis,))


def _signed_distance(plane: FaceTarget, point: Vec3) -> float:
    rel = point - plane.frame.origin
    n = plane.frame.z
    return rel.x * n.x + rel.y * n.y + rel.z * n.z


def test_decalage_normal_conserve_avec_centrage_sur_la_normale() -> None:
    """Centrer sur Z garde le décalage le long de la normale."""
    fixed, moving = _top(Vec3(0, 0, 10), (100, 40)), _top(Vec3(300, 70, 50), (20, 20))
    motion = align(fixed, moving, offset=Vec3(0, 0, 5), centered=(_Z,))
    assert _moved(motion, face_center(moving)).z == pytest.approx(15.0)


def test_decalage_dans_le_plan_conserve_avec_centrage() -> None:
    """Centrer sur X garde le décalage de 7 mm sur X."""
    fixed, moving = _top(Vec3(0, 0, 10), (100, 40)), _top(Vec3(300, 70, 50), (20, 20))
    motion = align(fixed, moving, offset=Vec3(7, 0, 0), centered=(_X,))
    assert _moved(motion, face_center(moving)).x == pytest.approx(57.0)


@pytest.mark.parametrize("axis", [_X, _Z], ids=["X", "Z"])
def test_face_inclinee_reste_dans_son_plan_apres_centrage_partiel(axis: Vec3) -> None:
    """Un centrage sur un axe oblique à la face ne la sort pas du plan de référence."""
    s = math.sqrt(0.5)
    fixed = FaceTarget(
        "F", Frame(Vec3(0, 0, 0), _X, Vec3(0, s, s), Vec3(0, -s, s)), (100, 40), True
    )
    moving = _top(Vec3(300, 70, 50), (20, 20))
    motion = align(fixed, moving, centered=(axis,))
    assert _signed_distance(fixed, _moved(motion, face_center(moving))) == pytest.approx(
        0.0, abs=1e-9
    )


def test_axes_de_centrage_non_perpendiculaires_refuses() -> None:
    fixed, moving = _top(Vec3(0, 0, 10), (100, 40)), _top(Vec3(300, 70, 50), (20, 20))
    with pytest.raises(AlignError, match="perpendiculaires entre eux"):
        align(fixed, moving, centered=(_X, Vec3(1, 1, 0)))


def _turned_in_plane(origin: Vec3, degrees: float, size: tuple[float, float]) -> FaceTarget:
    """Face du dessus tournée de ``degrees`` autour de Z."""
    c, s = math.cos(math.radians(degrees)), math.sin(math.radians(degrees))
    return FaceTarget("Face6", Frame(origin, Vec3(c, s, 0), Vec3(-s, c, 0), _Z), size, True)


def _direction(motion: Alignment, vector: Vec3) -> Vec3:
    return _moved(motion, vector) - _moved(motion, Vec3(0.0, 0.0, 0.0))


@pytest.mark.parametrize("degrees", [30.0, -50.0, 100.0, 170.0])
def test_centrage_rend_les_planches_paralleles(degrees: float) -> None:
    fixed = _top(Vec3(0, 0, 20), (600, 100))
    moving = _turned_in_plane(Vec3(200, -150, 20), degrees, (600, 100))
    motion = align(fixed, moving, AlignMode.FLUSH, centered=(_X, _Y, _Z))
    edge = _direction(motion, moving.frame.x)
    assert abs(edge.x * edge.y) == pytest.approx(0.0, abs=1e-9)  # parallèle à X ou à Y
    assert edge.z == pytest.approx(0.0, abs=1e-9)
    assert _close(_moved(motion, face_center(moving)), face_center(fixed))


def test_centrage_tourne_du_plus_petit_quart() -> None:
    fixed = _top(Vec3(0, 0, 20), (600, 100))
    moving = _turned_in_plane(Vec3(200, -150, 20), 30.0, (600, 100))
    edge = _direction(align(fixed, moving, centered=(_X,)), moving.frame.x)
    assert _close(edge, _X)  # 30° → 0°, pas 90°


def test_sans_centrage_la_planche_garde_son_angle_dans_le_plan() -> None:
    fixed = _top(Vec3(0, 0, 20), (600, 100))
    moving = _turned_in_plane(Vec3(200, -150, 20), 30.0, (600, 100))
    edge = _direction(align(fixed, moving), moving.frame.x)
    assert _close(edge, moving.frame.x)


def test_sur_un_axe_le_centrage_ne_tourne_pas() -> None:
    fixed = _top(Vec3(0, 0, 20), (600, 100))
    moving = _turned_in_plane(Vec3(200, -150, 50), 30.0, (600, 100))
    motion = align(fixed, moving, axis=_Z, centered=(_X, _Y))
    assert motion.rotation == ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))


def test_centrage_tournant_garde_le_pivot_deplace_et_le_plan() -> None:
    """Le tour dans le plan se fait autour du pivot déplacé : il reste dans le plan, décalé."""
    fixed = _top(Vec3(0, 0, 20), (600, 100))
    moving = _turned_in_plane(Vec3(200, -150, 50), 30.0, (600, 100))
    plain = align(fixed, moving, AlignMode.FLUSH, offset=Vec3(0, 0, 5))
    motion = align(fixed, moving, AlignMode.FLUSH, offset=Vec3(0, 0, 5), centered=(_X,))
    assert motion.pivot == plain.pivot
    assert _signed_distance(fixed, _moved(motion, moving.frame.origin)) == pytest.approx(5.0)
    assert _moved(motion, face_center(moving)).z == pytest.approx(25.0)


def test_decalage_dans_le_plan_ajoute_apres_le_tour() -> None:
    fixed = _top(Vec3(0, 0, 20), (600, 100))
    moving = _turned_in_plane(Vec3(200, -150, 20), 30.0, (600, 100))
    base = _moved(align(fixed, moving, centered=(_X,)), face_center(moving))
    shifted = _moved(
        align(fixed, moving, offset=Vec3(7, 3, 0), centered=(_X,)), face_center(moving)
    )
    assert _close(shifted - base, Vec3(7, 3, 0))


@pytest.mark.parametrize("degrees", [45.0, -45.0, 135.0, 225.0])
def test_egalite_a_45_degres_est_deterministe_et_parallele(degrees: float) -> None:
    fixed = _top(Vec3(0, 0, 20), (600, 100))
    moving = _turned_in_plane(Vec3(200, -150, 20), degrees, (600, 100))
    first = align(fixed, moving, AlignMode.FLUSH, centered=(_X,))
    assert first == align(fixed, moving, AlignMode.FLUSH, centered=(_X,))
    edge = _direction(first, moving.frame.x)
    assert abs(edge.x * edge.y) == pytest.approx(0.0, abs=1e-9)


def test_d_equerre_la_normale_mobile_devient_parallele_a_une_arete() -> None:
    fixed = _top(Vec3(0, 0, 20), (600, 100))
    side = FaceTarget("F", Frame(Vec3(200, -150, 30), _Y, _Z, _X), (40, 20), True)
    motion = align(fixed, side, AlignMode.PERPENDICULAR, centered=(_X,))
    normal = _direction(motion, side.frame.z)
    assert normal.z == pytest.approx(0.0, abs=1e-9)
    assert abs(normal.x * normal.y) == pytest.approx(0.0, abs=1e-9)


def _short_x_face(origin: Vec3, degrees: float) -> FaceTarget:
    """Planche de 600 sur 100 dont l'axe ``x`` est sur le petit côté (le grand côté est ``y``)."""
    c, s = math.cos(math.radians(degrees)), math.sin(math.radians(degrees))
    return FaceTarget("Face6", Frame(origin, Vec3(-s, c, 0), Vec3(-c, -s, 0), _Z), (100, 600), True)


@pytest.mark.parametrize("degrees", [10.0, 80.0, 100.0, -60.0, 170.0])
def test_grand_cote_suit_le_grand_cote_de_la_reference(degrees: float) -> None:
    """Essai de jv : deux planches croisées doivent finir parallèles, pas en T."""
    fixed = _top(Vec3(0, 0, 20), (600, 100))
    for moving in (
        _turned_in_plane(Vec3(200, -150, 20), degrees, (600, 100)),
        _short_x_face(Vec3(200, -150, 20), degrees),
    ):
        motion = align(fixed, moving, centered=(_X, _Y, _Z))
        long_side = moving.frame.x if moving.extent[0] > moving.extent[1] else moving.frame.y
        edge = _direction(motion, long_side)
        assert abs(edge.x) == pytest.approx(1.0, abs=1e-9)  # le long de X, comme la référence
        assert _close(_moved(motion, face_center(moving)), face_center(fixed))


@pytest.mark.parametrize("degrees", [10.0, 80.0, 100.0, -60.0, 170.0])
def test_reference_dont_x_est_le_petit_cote_donne_le_meme_resultat(degrees: float) -> None:
    """Le repère de la référence peut avoir ``x`` sur le petit côté : la pièce suit le grand."""
    fixed = _short_x_face(Vec3(0, 0, 20), 0.0)  # grand côté de la référence le long de X
    moving = _turned_in_plane(Vec3(200, -150, 20), degrees, (600, 100))
    motion = align(fixed, moving, centered=(_X, _Y, _Z))
    edge = _direction(motion, moving.frame.x)
    assert abs(edge.x) == pytest.approx(1.0, abs=1e-9)
    assert _close(_moved(motion, face_center(moving)), face_center(fixed))


@pytest.mark.parametrize("degrees", [10.0, 50.0, 100.0, -60.0])
def test_face_mobile_carree_tourne_d_un_quart_de_tour_au_plus(degrees: float) -> None:
    fixed = _top(Vec3(0, 0, 20), (600, 100))
    moving = _turned_in_plane(Vec3(200, -150, 20), degrees, (80, 80))
    motion = align(fixed, moving, centered=(_X,))
    edge = _direction(motion, moving.frame.x)
    assert abs(edge.x * edge.y) == pytest.approx(0.0, abs=1e-9)
    assert motion.angle <= 45.0 + 1e-6


def test_d_equerre_la_normale_suit_le_grand_cote_d_une_reference_a_x_court() -> None:
    fixed = _short_x_face(Vec3(0, 0, 20), 0.0)
    side = FaceTarget("F", Frame(Vec3(200, -150, 30), _Y, _Z, _X), (40, 20), True)
    motion = align(fixed, side, AlignMode.PERPENDICULAR, centered=(_X,))
    normal = _direction(motion, side.frame.z)
    assert abs(normal.x) == pytest.approx(1.0, abs=1e-9)


@pytest.mark.parametrize("size", [(1e-12, 1e-12), (1e-9, 2e-9)])
def test_etendues_minuscules_ne_plantent_pas(size: tuple[float, float]) -> None:
    fixed = _top(Vec3(0, 0, 20), size)
    moving = _turned_in_plane(Vec3(200, -150, 20), 30.0, size)
    motion = align(fixed, moving, centered=(_X, _Y, _Z))
    assert _close(_moved(motion, face_center(moving)), face_center(fixed))
