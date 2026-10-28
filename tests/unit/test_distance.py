# SPDX-License-Identifier: LGPL-2.1-or-later
"""Distance entre deux éléments (DI-a, critères D1 à D5) : géométrie pure, sans FreeCAD."""

from __future__ import annotations

import itertools
import math

import pytest

from freecad.menuiserie.core.distance import (
    DistanceError,
    FrameAxis,
    Gap,
    ensemble_axis,
    measure,
    moved_by,
)
from freecad.menuiserie.core.geometry import Vec3
from freecad.menuiserie.core.snap import EdgeTarget, FaceTarget, Frame, Target, VertexTarget

X, Y, Z = Vec3(1, 0, 0), Vec3(0, 1, 0), Vec3(0, 0, 1)
NEG_X, NEG_Y, NEG_Z = Vec3(-1, 0, 0), Vec3(0, -1, 0), Vec3(0, 0, -1)
WORLD = Frame(Vec3(0, 0, 0), X, Y, Z)
NOT_PARALLEL = "Les éléments ne sont pas parallèles : la distance n'est pas définie."


def face(height: float, up: bool = True, planar: bool = True) -> FaceTarget:
    """Face horizontale à la cote ``height``, normale sortante +Z (``up``) ou -Z."""
    frame = Frame(Vec3(0, 0, height), X, Y, Z) if up else Frame(Vec3(0, 0, height), X, NEG_Y, NEG_Z)
    return FaceTarget("Face", frame, (100.0, 50.0), planar)


def edge(y: float, z: float, support: Vec3 = Z) -> EdgeTarget:
    """Arête parallèle à X, passant par (·, y, z), appuyée sur une face de normale ``support``."""
    inward = Vec3(0, -1, 0) if support == Z else Vec3(0, 0, -1)
    return EdgeTarget("Arête", Vec3(0, y, z), Vec3(100, y, z), support, inward)


def vertex(x: float = 0.0, y: float = 0.0, z: float = 0.0) -> VertexTarget:
    return VertexTarget("Sommet", Vec3(x, y, z), WORLD)


def close(vector: Vec3, expected: Vec3) -> bool:
    return math.dist((vector.x, vector.y, vector.z), (expected.x, expected.y, expected.z)) < 1e-9


# D1 : neuf paires ------------------------------------------------------------------------------

# (étiquette, référence, mobile, valeur, sens) ; mobile au-dessus (+Z) ou à côté (+Y).
PAIRS: list[tuple[str, Target, Target, float, Vec3]] = [
    ("face-face", face(0), face(30, up=False), 30.0, Z),
    ("face-arête", face(0), edge(0, 12), 12.0, Z),
    ("face-sommet", face(0), vertex(5, 5, 7), 7.0, Z),
    ("arête-face", edge(0, 0), face(18, up=False), 18.0, Z),
    ("arête-arête", edge(0, 0), edge(40, 0, support=Y), 40.0, Y),
    ("arête-sommet", edge(0, 0), vertex(10, 0, 25), 25.0, Z),
    ("sommet-face", vertex(), face(9, up=False), 9.0, Z),
    ("sommet-arête", vertex(), edge(3, 4), 5.0, Vec3(0, 0.6, 0.8)),
    ("sommet-sommet", vertex(), vertex(3, 4, 12), 13.0, Vec3(3 / 13, 4 / 13, 12 / 13)),
]


@pytest.mark.parametrize(("label", "fixed", "moving", "value", "direction"), PAIRS)
def test_d1_neuf_paires(
    label: str, fixed: Target, moving: Target, value: float, direction: Vec3
) -> None:
    gap = measure(fixed, moving)
    assert gap.value == pytest.approx(value), label
    assert close(gap.direction, direction), label


def test_d1_couvre_toutes_les_paires_de_types() -> None:
    types = {(type(fixed), type(moving)) for _, fixed, moving, _, _ in PAIRS}
    kinds = (FaceTarget, EdgeTarget, VertexTarget)
    assert types == set(itertools.product(kinds, kinds))


def test_d1_sens_oppose_quand_la_mobile_est_dessous() -> None:
    gap = measure(face(0), vertex(0, 0, -6))
    assert gap.value == pytest.approx(6.0)
    assert close(gap.direction, NEG_Z)


def test_d1_arete_parallele_au_plan_mesure_avec_un_point() -> None:
    assert measure(face(10), edge(20, 25)).value == pytest.approx(15.0)


# D2 : refus -------------------------------------------------------------------------------------


def side_face() -> FaceTarget:
    return FaceTarget("Côté", Frame(Vec3(0, 0, 0), Y, Z, X), (10.0, 10.0), True)


def oblique_edge() -> EdgeTarget:
    half = math.sqrt(0.5)
    inward = Vec3(half, 0, -half)
    return EdgeTarget("Oblique", Vec3(0, 0, 0), Vec3(100, 0, 100), Vec3(0, 1, 0), inward)


@pytest.mark.parametrize(
    ("fixed", "moving"),
    [
        (face(0), side_face()),
        (face(0), oblique_edge()),
        (oblique_edge(), face(0, up=False)),
        (edge(0, 0), oblique_edge()),
        (face(0), FaceTarget("Courbe", WORLD, (10.0, 10.0), False)),
        (FaceTarget("Courbe", WORLD, (10.0, 10.0), False), vertex(0, 0, 3)),
    ],
)
def test_d2_non_parallele_refuse_avec_message_traduisible(fixed: Target, moving: Target) -> None:
    with pytest.raises(DistanceError) as error:
        measure(fixed, moving)
    assert str(error.value) == NOT_PARALLEL
    assert error.value.template == NOT_PARALLEL
    assert not error.value.params


def test_d2_arete_droite_et_point_toujours_mesurables() -> None:
    assert measure(oblique_edge(), vertex(0, 3, 0)).value == pytest.approx(3.0)


# D3 : déplacement -------------------------------------------------------------------------------


def test_d3_amene_la_distance_a_la_valeur() -> None:
    gap = measure(face(0), face(30, up=False))
    assert close(moved_by(gap, 50.0), Vec3(0, 0, 20))
    assert close(moved_by(gap, 10.0), Vec3(0, 0, -20))
    assert close(moved_by(gap, 30.0), Vec3(0, 0, 0))


def test_d3_la_mobile_reste_de_son_cote() -> None:
    gap = measure(face(0), vertex(0, 0, -4))
    assert close(moved_by(gap, 10.0), Vec3(0, 0, -6))  # reste sous la référence


def test_d3_distance_nulle_la_mobile_s_ecarte_de_la_reference() -> None:
    # Au contact, la face mobile regarde la référence : on s'écarte à l'opposé de sa normale.
    for mobile, expected in ((face(0, up=False), Z), (face(0), NEG_Z)):
        gap = measure(face(0), mobile)
        assert gap.value == 0.0
        assert close(gap.direction, expected)
        assert close(moved_by(gap, 25.0), Vec3(expected.x * 25, expected.y * 25, expected.z * 25))


def test_d3_distance_nulle_arete_et_sommet() -> None:
    assert close(measure(edge(0, 0), edge(0, 0, support=Y)).direction, Vec3(0, -1, 0))
    assert close(measure(face(0), vertex(1, 1, 0)).direction, Z)
    assert close(measure(edge(0, 0), vertex(5, 0, 0)).direction, Z)
    assert close(measure(vertex(), vertex()).direction, X)


@pytest.mark.parametrize("value", [-1.0, math.nan, math.inf])
def test_d3_valeur_invalide_refusee(value: float) -> None:
    with pytest.raises(DistanceError):
        moved_by(Gap(5.0, Z), value)


def test_gap_valide_ses_champs() -> None:
    with pytest.raises(ValueError, match=r"Gap\.value"):
        Gap(-1.0, Z)
    with pytest.raises(ValueError, match=r"Gap\.direction"):
        Gap(1.0, Vec3(0, 0, 2))


# D4 : axe facultatif ----------------------------------------------------------------------------


def test_d4_sommet_sommet_projete_sur_un_axe() -> None:
    gap = measure(vertex(), vertex(3, 4, 12), axis=Y)
    assert gap.value == pytest.approx(4.0)
    assert close(gap.direction, Y)
    assert close(moved_by(gap, 10.0), Vec3(0, 6, 0))


def test_d4_sens_selon_le_signe_et_axe_non_normalise() -> None:
    gap = measure(vertex(), vertex(3, -4, 12), axis=Vec3(0, 5, 0))
    assert gap.value == pytest.approx(4.0)
    assert close(gap.direction, NEG_Y)


def test_d4_projection_nulle_garde_l_axe() -> None:
    gap = measure(vertex(), vertex(3, 0, 12), axis=Y)
    assert gap.value == 0.0
    assert close(gap.direction, Y)


def test_d4_axe_nul_refuse() -> None:
    with pytest.raises(DistanceError):
        measure(vertex(), vertex(1, 1, 1), axis=Vec3(0, 0, 0))


# D5 : axe de l'ensemble -------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("direction", "expected"),
    [
        (Z, FrameAxis.Z),
        (NEG_X, FrameAxis.X),
        (Y, FrameAxis.Y),
        (Vec3(0.6, 0.8, 0), None),
    ],
)
def test_d5_axe_de_l_ensemble(direction: Vec3, expected: FrameAxis | None) -> None:
    assert ensemble_axis(Gap(10.0, direction), WORLD) is expected


def test_d5_repere_tourne_de_l_ensemble() -> None:
    turned = Frame(Vec3(5, 5, 5), Y, NEG_X, Z)
    assert ensemble_axis(Gap(1.0, X), turned) is FrameAxis.Y
    assert ensemble_axis(Gap(1.0, Y), turned) is FrameAxis.X
