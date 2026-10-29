# SPDX-License-Identifier: LGPL-2.1-or-later
"""Repère d'une forme dessinée : critères A1 (Axes), A2, A3, A4 de PD-a."""

from __future__ import annotations

import math

import pytest

from freecad.menuiserie.core.geometry import Vec3
from freecad.menuiserie.core.shaped import (
    Axes,
    ShapeSample,
    measure_points,
    ordered,
    principal_axes,
    turned_axes,
)
from freecad.menuiserie.core.snap import Turn
from tests.unit.aides_forme import (
    X,
    Y,
    Z,
    about_axis,
    about_z,
    box_sample,
    close,
    cross,
    cylinder_sample,
    parallel,
    unit_vector,
)


def ordered_axes_of(sample: ShapeSample) -> Axes:
    axes = principal_axes(sample)
    return ordered(axes, measure_points(axes, sample.points).extents)


def sorted_extents(axes: Axes, sample: ShapeSample) -> list[float]:
    return sorted(measure_points(axes, sample.points).extents)


# --- A1 : Axes ---------------------------------------------------------------------------


def test_axes_identite() -> None:
    axes = Axes.identity()
    assert axes.vectors() == (X, Y, Z)
    assert axes.coordinates(Vec3(1, 2, 3)) == Vec3(1, 2, 3)


def test_axes_renormalises_dans_la_tolerance() -> None:
    axes = Axes(Vec3(1 + 1e-8, 0, 0), Vec3(1e-8, 1, 0), Z)
    assert close(axes.x, X, 1e-12)
    assert close(axes.y, Y, 1e-7)


@pytest.mark.parametrize(
    ("axes", "field"),
    [
        ((Vec3(2, 0, 0), Y, Z), "x"),
        ((X, Vec3(0, math.nan, 0), Z), "y"),
        ((X, Vec3(0, 0, 0), Z), "y"),
        ((X, Vec3(0.6, 0.8, 0), Z), "y"),
        ((X, Y, Vec3(0, 0, -1)), "z"),
        ((X, Z, Y), "z"),
    ],
)
def test_axes_invalides_citent_le_champ(axes: tuple[Vec3, Vec3, Vec3], field: str) -> None:
    with pytest.raises(ValueError, match=f"^{field} "):
        Axes(*axes)


# --- A2 : axes principaux ----------------------------------------------------------------


def test_plateau_tourne_retrouve_son_repere() -> None:
    sample = box_sample(800, 400, 22, about_z(30))
    assert sorted_extents(principal_axes(sample), sample) == pytest.approx([22, 400, 800])


def test_les_axes_de_la_source_gagnent_a_volume_egal() -> None:
    assert principal_axes(box_sample(800, 400, 22)) == Axes.identity()


def test_source_donnee_prioritaire_a_egalite() -> None:
    source = Axes(Y, Vec3(-1, 0, 0), Z)
    assert principal_axes(box_sample(800, 400, 22), source) == source


def test_egalite_a_un_pour_mille_pres_garde_la_source() -> None:
    # Boîte tournée de 0,01 degré : le volume gagné (< 0,1 %) ne justifie pas de quitter la source.
    assert principal_axes(box_sample(800, 400, 22, about_z(0.01))) == Axes.identity()


def test_volume_nettement_plus_petit_l_emporte() -> None:
    sample = box_sample(800, 400, 22, about_z(5))
    assert principal_axes(sample) != Axes.identity()


@pytest.mark.parametrize("seed", range(6))
def test_determinisme_selon_l_ordre_des_faces(seed: int) -> None:
    reference = principal_axes(box_sample(800, 400, 22, about_z(30)))
    assert principal_axes(box_sample(800, 400, 22, about_z(30), shuffle_seed=seed)) == reference


def test_boite_inclinee_dans_deux_plans() -> None:
    sample = box_sample(600, 300, 40, about_axis(unit_vector(1, 2, 3), 37))
    assert sorted_extents(principal_axes(sample), sample) == pytest.approx([40, 300, 600])


def test_sans_face_ni_arete_les_axes_de_la_source_restent() -> None:
    sample = ShapeSample((Vec3(0, 0, 0), Vec3(5, 3, 1)))
    assert principal_axes(sample) == Axes.identity()


def test_famille_sans_arete_projette_les_axes_de_la_source() -> None:
    # Faces planes seules (normale à 45° dans XY) : l'axe X de la source, projeté dans leur plan,
    # donne le deuxième axe du candidat.
    normal = unit_vector(1, 1, 0)
    side = unit_vector(1, -1, 0)
    points = tuple(
        Vec3(side.x * a + normal.x * b, side.y * a + normal.y * b, c)
        for a in (0, 100)
        for b in (0, 3)
        for c in (0, 40)
    )
    axes = principal_axes(ShapeSample(points, ((normal, 4000.0),)))
    assert parallel(axes.z, normal)
    assert sorted_extents(axes, ShapeSample(points)) == pytest.approx([3, 40, 100])


def test_forme_plate_est_acceptee() -> None:
    points = (Vec3(0, 0, 0), Vec3(10, 0, 0), Vec3(10, 5, 0))
    assert principal_axes(ShapeSample(points, ((Z, 25.0),), ((X, 10.0),))) == Axes.identity()


# --- A3 : mise en ordre ------------------------------------------------------------------


def test_plateau_tourne_de_30_degres_x_le_long_des_800_z_normal() -> None:
    axes = ordered_axes_of(box_sample(800, 400, 22, about_z(30)))
    assert parallel(axes.x, about_z(30)(X))
    assert parallel(axes.z, Z)
    assert close(axes.y, cross(axes.z, axes.x))


def test_pied_tourne_x_sur_l_axe_de_revolution() -> None:
    axis = unit_vector(1, 1, 1)
    rotation = about_axis(unit_vector(0, -1, 1), math.degrees(math.acos(1 / math.sqrt(3))))
    assert close(rotation(X), axis)
    assert parallel(ordered_axes_of(cylinder_sample(30, 700, rotation)).x, axis)


def test_pied_galbe_dessine_dans_le_plan_xz_z_normal_a_l_esquisse() -> None:
    # Profil galbé dans XZ (720 x 95), protrusion de 45 mm selon Y.
    profile = [(0, 0), (720, 10), (720, 95), (360, 80), (0, 95)]
    points = tuple(Vec3(x, y, z) for x, z in profile for y in (0, 45))
    faces = ((Y, 40000.0), (Vec3(0, -1, 0), 40000.0))
    axes = ordered_axes_of(ShapeSample(points, faces))
    assert parallel(axes.z, Y)
    assert parallel(axes.x, X)


def test_etendues_egales_gardent_l_ordre_d_origine() -> None:
    assert ordered(Axes.identity(), (10.0, 10.0, 10.0)) == Axes.identity()


@pytest.mark.parametrize(
    "extents", [(1, 2, 3), (3, 2, 1), (2, 3, 1), (1, 3, 2), (3, 1, 2), (2, 1, 3)]
)
def test_ordered_donne_un_repere_direct_du_plus_long_au_plus_court(
    extents: tuple[float, float, float],
) -> None:
    axes = ordered(Axes.identity(), extents)
    assert close(axes.y, cross(axes.z, axes.x))
    sample = ShapeSample((Vec3(0, 0, 0), Vec3(*extents)))
    lengths = measure_points(axes, sample.points).extents
    assert lengths[0] >= lengths[1] >= lengths[2]


@pytest.mark.parametrize("extents", [(1.0, 2.0), (1.0, 2.0, math.nan), (1.0, 2.0, -3.0)])
def test_ordered_refuse_des_etendues_invalides(extents: tuple[float, ...]) -> None:
    with pytest.raises(ValueError, match="extents"):
        ordered(Axes.identity(), extents)


# --- encombrement et coin minimal --------------------------------------------------------


def test_encombrement_et_coin_minimal() -> None:
    bounds = measure_points(Axes.identity(), [Vec3(10, 20, 30), Vec3(110, 70, 35)])
    assert bounds.extents == (100, 50, 5)
    assert bounds.minimum == Vec3(10, 20, 30)


def test_coin_minimal_dans_un_repere_tourne() -> None:
    bounds = measure_points(Axes(Y, Vec3(-1, 0, 0), Z), [Vec3(10, 20, 30), Vec3(110, 70, 35)])
    assert bounds.extents == (50, 100, 5)
    assert bounds.minimum == Vec3(20, -110, 30)


def test_encombrement_sans_point_refuse() -> None:
    with pytest.raises(ValueError, match="points"):
        measure_points(Axes.identity(), [])


# --- A4 : quarts de tour -----------------------------------------------------------------


def key(axes: Axes) -> tuple[float, ...]:
    return tuple(round(c, 6) + 0.0 for v in axes.vectors() for c in (v.x, v.y, v.z))


@pytest.mark.parametrize("turn", list(Turn))
def test_quatre_quarts_de_tour_reviennent_au_depart(turn: Turn) -> None:
    axes = Axes.identity()
    for _ in range(4):
        axes = turned_axes(axes, turn)
    assert key(axes) == key(Axes.identity())


@pytest.mark.parametrize("turn", list(Turn))
def test_un_quart_de_tour_change_le_repere(turn: Turn) -> None:
    assert key(turned_axes(Axes.identity(), turn)) != key(Axes.identity())


def test_vingt_quatre_orientations_atteintes() -> None:
    seen = {key(Axes.identity())}
    frontier = [Axes.identity()]
    while frontier:
        current = frontier.pop()
        for turn in Turn:
            following = turned_axes(current, turn)
            if key(following) not in seen:
                seen.add(key(following))
                frontier.append(following)
    assert len(seen) == 24


def test_quart_de_tour_autour_de_x_echange_largeur_et_epaisseur() -> None:
    turned = turned_axes(Axes.identity(), Turn.X)
    assert parallel(turned.x, X)
    assert parallel(turned.y, Z)
    assert parallel(turned.z, Y)
