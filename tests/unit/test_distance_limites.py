# SPDX-License-Identifier: LGPL-2.1-or-later
"""Cas limites de ``core/distance`` (DI-a) : symétrie, seuil de distance nulle, parallélisme."""

from __future__ import annotations

import math

import pytest

from freecad.menuiserie.core.distance import DistanceError, Gap, ensemble_axis, measure, moved_by
from freecad.menuiserie.core.geometry import Vec3
from freecad.menuiserie.core.snap import EdgeTarget, FaceTarget, Frame, Target, VertexTarget
from tests.unit.test_distance import PAIRS, WORLD, X, Y, Z, close, edge, face, vertex


@pytest.mark.parametrize(("label", "fixed", "moving", "value", "direction"), PAIRS)
def test_echanger_les_roles_garde_la_valeur(
    label: str, fixed: Target, moving: Target, value: float, direction: Vec3
) -> None:
    gap = measure(moving, fixed)
    assert gap.value == pytest.approx(value), label
    assert close(gap.direction, Vec3(-direction.x, -direction.y, -direction.z)), label


def test_seuil_de_distance_nulle() -> None:
    assert measure(face(0), vertex(0, 0, 5e-10)).value == 0.0
    assert measure(face(0), vertex(0, 0, 2e-9)).value == pytest.approx(2e-9)


def test_grande_distance() -> None:
    gap = measure(face(0), vertex(0, 0, 1e9))
    assert gap.value == pytest.approx(1e9)
    assert moved_by(gap, 0.0).z == pytest.approx(-1e9)


def test_valeur_egale_a_la_distance_ne_bouge_pas() -> None:
    for fixed, moving in ((face(0), vertex(0, 0, 7)), (vertex(), vertex(3, 4, 12))):
        gap = measure(fixed, moving)
        shift = moved_by(gap, gap.value)
        assert math.hypot(shift.x, shift.y, shift.z) < 1e-9


def test_valeur_nulle_amene_au_contact() -> None:
    assert close(moved_by(measure(face(0), vertex(0, 0, 7)), 0.0), Vec3(0, 0, -7))


def test_message_de_valeur_invalide() -> None:
    with pytest.raises(DistanceError) as error:
        moved_by(Gap(1.0, Z), -2.0)
    assert "-2" in str(error.value)


def test_arete_perpendiculaire_au_plan_refusee() -> None:
    along_normal = EdgeTarget("Axe", Vec3(0, 0, 5), Vec3(0, 0, 50), X, Y)
    with pytest.raises(DistanceError):
        measure(face(0), along_normal)


def test_aretes_gauches_refusees_et_antiparalleles_acceptees() -> None:
    skew = EdgeTarget("Gauche", Vec3(0, 0, 0), Vec3(0, 100, 0), Z, X)
    with pytest.raises(DistanceError):
        measure(edge(0, 0), skew)
    reversed_edge = EdgeTarget("Inverse", Vec3(100, 30, 0), Vec3(0, 30, 0), Z, Vec3(0, -1, 0))
    assert measure(edge(0, 0), reversed_edge).value == pytest.approx(30.0)


def test_faces_dans_un_repere_tourne() -> None:
    c = s = math.sqrt(0.5)
    normal = Vec3(c, 0, s)
    oblique = FaceTarget(
        "Oblique", Frame(Vec3(10 * c, 0, 10 * s), Vec3(s, 0, -c), Y, normal), (10.0, 10.0), True
    )
    other = FaceTarget(
        "Autre", Frame(Vec3(20 * c, 0, 20 * s), Vec3(s, 0, -c), Y, normal), (1.0, 1.0), True
    )
    with pytest.raises(DistanceError):
        measure(face(0), oblique)
    assert measure(oblique, other).value == pytest.approx(10.0)


def test_gap_refuse_valeur_non_finie_et_direction_non_unitaire() -> None:
    for value in (math.nan, math.inf):
        with pytest.raises(ValueError, match=r"Gap\.value"):
            Gap(value, Z)
    with pytest.raises(ValueError, match=r"Gap\.direction"):
        Gap(1.0, Vec3(0, 0, 1.01))


def test_ensemble_axis_tolerance_angulaire() -> None:
    assert ensemble_axis(Gap(1.0, Vec3(1e-7, 0, 1)), WORLD) is not None
    assert ensemble_axis(Gap(1.0, Vec3(1e-3, 0, 1)), WORLD) is None


def test_sommet_sommet_axe_infini_refuse_et_axe_oblique_projete() -> None:
    with pytest.raises(DistanceError):
        measure(vertex(), vertex(1, 1, 1), axis=Vec3(math.inf, 0, 0))
    gap = measure(vertex(), vertex(3, 4, 12), axis=Vec3(1, 1, 0))
    assert gap.value == pytest.approx(7 / math.sqrt(2))


def test_cible_non_finie_refusee_a_la_construction() -> None:
    with pytest.raises(ValueError, match="finies"):
        VertexTarget("v", Vec3(0, 0, math.nan), WORLD)
