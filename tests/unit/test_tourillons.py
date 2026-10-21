# SPDX-License-Identifier: LGPL-2.1-or-later
"""Tourillons (J3c, critères T1 et T2)."""

from __future__ import annotations

import pytest

from freecad.menuiserie.core.geometry import Axis, Cylinder, JointError, PlacedBlock, Vec3
from freecad.menuiserie.core.joints import JointKind, strategy_for
from freecad.menuiserie.core.joints.dowels import (
    MAX_DOWEL_COUNT,
    DowelParams,
    auto_count,
    auto_diameter,
    auto_length,
)
from tests.unit.aides_assemblages import block, rail, stile

DOWELS = strategy_for(JointKind.DOWELS)


def boards(length: float = 300.0, thickness: float = 18.0) -> tuple[PlacedBlock, PlacedBlock]:
    """Deux lames de ``length`` x 100 x ``thickness`` chant contre chant (contact en y = 100)."""
    size = (length, 100.0, thickness)
    return block(size), block(size, (0.0, 100.0, 0.0))


def cylinders(solids: tuple[object, ...]) -> list[Cylinder]:
    assert all(isinstance(solid, Cylinder) for solid in solids)
    return [solid for solid in solids if isinstance(solid, Cylinder)]


def refused(host: PlacedBlock, guest: PlacedBlock, params: DowelParams, text: str) -> None:
    with pytest.raises(JointError, match=text):
        DOWELS.plan(host, guest, params)


# --- T1 : valeurs automatiques ------------------------------------------------------------


@pytest.mark.parametrize(
    ("thickness", "diameter"), [(22, 10), (18, 8), (16, 8), (12, 6), (30, 12), (100, 12)]
)
def test_diametre_automatique(thickness: float, diameter: float) -> None:
    assert auto_diameter(thickness) == diameter


def test_pieces_trop_minces() -> None:
    with pytest.raises(JointError, match="trop minces pour des tourillons"):
        auto_diameter(10)
    refused(*boards(thickness=10.0), DowelParams(), "trop minces")


@pytest.mark.parametrize(
    ("diameter", "length"), [(6, 30), (8, 35), (10, 40), (12, 50), (7, 30), (5, 30), (14, 50)]
)
def test_longueur_selon_le_diametre(diameter: float, length: float) -> None:
    assert auto_length(diameter) == length


@pytest.mark.parametrize(
    ("width", "edge", "diameter", "count"),
    [
        (60, 20, 10, 2),
        (300, 16, 8, 4),
        (30, 20, 10, 1),
        (40, 20, 10, 1),
        (45, 20, 10, 1),
        (50, 20, 10, 1),
        (50.02, 20, 10, 2),
        (296, 20, 10, 3),
        (300, 10, 200, 2),
        (300, 10, 300, 1),
    ],
)
def test_nombre_automatique(width: float, edge: float, diameter: float, count: int) -> None:
    assert auto_count(width, edge, diameter) == count


@pytest.mark.parametrize("width", [40.0, 45.0, 50.0, 50.02, 60.0, 61.0, 100.0, 300.0, 600.0])
def test_nombre_automatique_jamais_refuse(width: float) -> None:
    """Traverse de ``width`` x 22, tous paramètres automatiques : jamais de refus d'entraxe."""
    values = DOWELS.resolve(stile(), rail(width=width), DowelParams())
    assert values.count == auto_count(width, 20, 10)


def test_contact_de_20_m_plafonne_au_nombre_maximal() -> None:
    """Contact de 20 m : 50 tourillons au plus (l'entraxe dépasse alors 128 mm)."""
    assert auto_count(20_000.0, 20, 10) == MAX_DOWEL_COUNT
    long_stile = block((20_000.0, 60.0, 22.0))
    values = DOWELS.resolve(long_stile, rail(width=20_000.0), DowelParams())
    assert values.count == len(values.positions) == MAX_DOWEL_COUNT
    plan = DOWELS.plan(long_stile, rail(width=20_000.0), DowelParams())
    assert len(plan.inserts) == MAX_DOWEL_COUNT


def test_traverse_de_45_un_tourillon_au_milieu() -> None:
    values = DOWELS.resolve(stile(), rail(width=45.0), DowelParams())
    assert (values.count, values.positions) == (1, (22.5,))


@pytest.mark.parametrize(
    ("thickness", "offset", "diameter"),
    [(22, 0, 10), (22, 1, 10), (22, 6, 8), (22, -7, 6), (30, 2, 12)],
)
def test_diametre_automatique_avec_decalage(
    thickness: float, offset: float, diameter: float
) -> None:
    assert auto_diameter(thickness, offset) == diameter


def test_trop_minces_a_cause_du_decalage() -> None:
    with pytest.raises(JointError, match="décalage de 4 mm"):
        auto_diameter(14, 4)
    refused(*boards(), DowelParams(thickness_offset=6), "trop minces")


def test_cadre_deux_tourillons_de_10() -> None:
    values = DOWELS.resolve(stile(), rail(), DowelParams())
    assert (values.diameter, values.dowel_length, values.host_depth) == (10, 40, 20)
    assert (values.count, values.edge_distance, values.positions) == (2, 20, (20, 40))
    plan = DOWELS.plan(stile(), rail(), DowelParams())
    # Repère de M1 : perçages depuis le chant y = 60, profondeur 20 + 1 de jeu.
    assert set(plan.host_cuts) == {
        Cylinder(Vec3(x, 60.0, 11.0), Axis.Y_NEG, 5.0, 21.0) for x in (20.0, 40.0)
    }
    # Repère de T1 : perçages depuis son bout x = 0.
    assert set(plan.guest_cuts) == {
        Cylinder(Vec3(0.0, y, 11.0), Axis.X_POS, 5.0, 21.0) for y in (20.0, 40.0)
    }
    assert set(plan.inserts) == {
        Cylinder(Vec3(x, 80.0, 11.0), Axis.Y_NEG, 5.0, 40.0) for x in (20.0, 40.0)
    }
    assert plan.host_additions == plan.guest_additions == ()


def test_contact_de_300_quatre_tourillons_de_8() -> None:
    values = DOWELS.resolve(*boards(), DowelParams())
    assert (values.diameter, values.dowel_length, values.count) == (8, 35, 4)
    assert values.positions == pytest.approx((16, 105.33333, 194.66667, 284))
    plan = DOWELS.plan(*boards(), DowelParams())
    assert [hole.base.z for hole in cylinders(plan.host_cuts)] == [9.0] * 4
    assert [hole.height for hole in cylinders(plan.host_cuts)] == [18.5] * 4


# --- T2 : paramètres saisis et refus ------------------------------------------------------


def test_parametres_saisis_respectes() -> None:
    params = DowelParams(
        diameter=6, dowel_length=30, host_depth=12, count=3, edge_distance=10, thickness_offset=2
    )
    values = DOWELS.resolve(*boards(), params)
    assert (values.diameter, values.dowel_length, values.host_depth) == (6, 30, 12)
    assert (values.count, values.positions, values.guest_depth) == (3, (10, 150, 290), 18)
    plan = DOWELS.plan(*boards(), params)
    assert [hole.height for hole in cylinders(plan.host_cuts)] == [13.0] * 3
    assert [hole.height for hole in cylinders(plan.guest_cuts)] == [19.0] * 3
    assert {hole.base.z for hole in cylinders(plan.guest_cuts)} == {11.0}


def test_un_seul_tourillon_au_milieu() -> None:
    values = DOWELS.resolve(*boards(length=30.0), DowelParams())
    assert values.positions == (15,)


@pytest.mark.parametrize(
    ("params", "text"),
    [
        (DowelParams(dowel_length=150, host_depth=98), "trop profond"),
        (DowelParams(dowel_length=200, host_depth=97), "trop profond"),
        (DowelParams(dowel_length=193, host_depth=96), "trop profond"),
        (DowelParams(diameter=18), "trop gros"),
        (DowelParams(diameter=10, thickness_offset=4.1), "trop gros"),
        (DowelParams(dowel_length=30, host_depth=30), "plus courte"),
        (DowelParams(count=40), "ne tiennent pas"),
        (DowelParams(count=2, edge_distance=200), "ne tiennent pas"),
        (DowelParams(edge_distance=3), "ne tiennent pas"),
    ],
)
def test_refus(params: DowelParams, text: str) -> None:
    refused(*boards(), params, text)


def test_fond_de_3_mm_accepte() -> None:
    # Hôte de 100 dans l'axe du perçage : 96 + 1 de jeu laisse 3 mm.
    values = DOWELS.resolve(*boards(), DowelParams(dowel_length=150, host_depth=96))
    assert values.host_depth == 96


def test_contact_par_la_face_refuse() -> None:
    on_face = block((100.0, 50.0, 10.0), (10.0, 5.0, 22.0))
    refused(stile(), on_face, DowelParams(), "par une face")
