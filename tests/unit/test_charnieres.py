# SPDX-License-Identifier: LGPL-2.1-or-later
"""Charnières à cuvette : cuvettes dans la porte, avant-trous de platine dans le côté (ADR 0055)."""

from __future__ import annotations

import math

import pytest

from freecad.menuiserie.core.geometry import Cylinder, JointError, PlacedBlock
from freecad.menuiserie.core.joints import JointKind, strategy_for
from freecad.menuiserie.core.joints.hinges import HingeParams, auto_count
from tests.unit.aides_assemblages import block, placed

HINGE = strategy_for(JointKind.HINGE)
QUARTER_TURN_X = [[1.0, 0.0, 0.0], [0.0, 0.0, -1.0], [0.0, 1.0, 0.0]]  # local Z vers -Y, Y vers Z


def side(height: float = 720.0) -> PlacedBlock:
    """Côté de caisson : hauteur le long de X, profondeur 500 le long de Y, épaisseur 19 (Z)."""
    return block((height, 500.0, 19.0))


def door(
    height: float = 720.0, width: float = 400.0, thickness: float = 16.0, gap: float = 0.0
) -> PlacedBlock:
    """Porte de recouvrement devant le chant avant (y = 500) : largeur le long de Z, de l'extérieur
    du côté (z = 0) vers l'intérieur du caisson."""
    return placed((height, width, thickness), QUARTER_TURN_X, (0.0, 500.0 + gap + thickness, 0.0))


def inset_door() -> PlacedBlock:
    """Porte insérée : contre la face intérieure du côté (2 mm de jeu), au ras du chant avant."""
    return placed((720.0, 400.0, 16.0), QUARTER_TURN_X, (0.0, 500.0, 21.0))


def cylinders(solids: tuple[object, ...]) -> list[Cylinder]:
    assert all(isinstance(solid, Cylinder) for solid in solids)
    return [solid for solid in solids if isinstance(solid, Cylinder)]


def test_nombre_automatique_selon_la_hauteur() -> None:
    assert [auto_count(h) for h in (300.0, 900.0, 900.1, 1600.0, 1600.1, 2400.0)] == [
        2,
        2,
        3,
        3,
        4,
        4,
    ]
    for height, count in ((720.0, 2), (1200.0, 3), (2000.0, 4)):
        values = HINGE.resolve(side(height), door(height), HingeParams())
        assert values.count == count == len(values.positions)


def test_positions_a_100_mm_des_angles_et_reparties() -> None:
    values = HINGE.resolve(side(1200.0), door(1200.0), HingeParams())
    assert values.positions == (100.0, 600.0, 1100.0)
    assert values.height == 1200.0 and values.cup_diameter == 35.0
    moved = HINGE.resolve(side(), door(), HingeParams(end_distance=150.0, count=3))
    assert moved.positions == (150.0, 360.0, 570.0)


def test_cuvettes_dans_la_porte_et_vis_de_platine_dans_le_cote() -> None:
    plan = HINGE.plan(side(), door(), HingeParams())
    pilots, cups = cylinders(plan.host_cuts), cylinders(plan.guest_cuts)
    assert len(pilots) == 4 and len(cups) == 2
    assert [p.base.x for p in pilots] == [84.0, 116.0, 604.0, 636.0]  # entraxe 32 mm
    for pilot in pilots:  # à 37 mm du chant avant, dans la face intérieure, vers l'extérieur
        assert pilot.base.y == 463.0 and pilot.base.z == 19.0 and pilot.axis.value == "-Z"
        assert pilot.radius == 1.5 and pilot.height == 10.0
    assert all(cup.radius == 17.5 and cup.height == 13.0 for cup in cups)
    inserts = cylinders(plan.inserts)
    assert [c.base.x for c in inserts] == [100.0, 620.0]
    for cup in inserts:  # face intérieure de la porte (y = 500), à 5 mm du chant : z = 5 + 17,5
        assert (cup.base.y, cup.base.z, cup.axis.value) == (500.0, 22.5, "+Y")


def test_cuvette_dans_le_repere_de_la_porte() -> None:
    plan = HINGE.plan(side(), door(), HingeParams())
    first = cylinders(plan.guest_cuts)[0]
    # Repère local de la porte : X = hauteur, Y = largeur (depuis le chant articulé), Z = épaisseur
    # (tournée vers -Y du côté) : la face intérieure est en z = 16, la cuvette creuse vers z = 3.
    assert first.base.x == pytest.approx(100.0)
    assert first.base.y == pytest.approx(22.5)
    assert first.base.z == pytest.approx(16.0)
    assert first.axis.value == "-Z"
    assert math.isclose(first.height, 13.0)


def test_porte_inseree_contre_la_face_interieure() -> None:
    plan = HINGE.plan(side(), inset_door(), HingeParams())
    cups, pilots = cylinders(plan.inserts), cylinders(plan.host_cuts)
    assert len(cups) == 2 and len(pilots) == 4
    assert all(c.base.z == pytest.approx(43.5) for c in cups)  # 21 + 5 + 17,5
    assert all(c.base.y == 484.0 and c.axis.value == "+Y" for c in cups)
    assert all(p.base.y == 463.0 and p.base.z == 19.0 for p in pilots)


def test_chant_avant_au_bas_du_repere() -> None:
    """Côté retourné : le chant avant est en y = 0, la porte devant lui (y < 0)."""
    flipped = placed((720.0, 500.0, 19.0), matrix_identity(), (0.0, 0.0, 0.0))
    front = placed((720.0, 400.0, 16.0), QUARTER_TURN_X, (0.0, 0.0, 0.0))
    plan = HINGE.plan(flipped, front, HingeParams())
    assert all(p.base.y == 37.0 for p in cylinders(plan.host_cuts))
    assert all(c.axis.value == "-Y" for c in cylinders(plan.inserts))


def matrix_identity() -> list[list[float]]:
    return [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]


def test_reglages_de_la_cuvette_et_des_vis() -> None:
    params = HingeParams(
        cup_depth=11.5, edge_distance=3.0, screw_pitch=45.0, plate_distance=32.0, count=3
    )
    plan = HINGE.plan(side(), door(), params)
    cups, pilots = cylinders(plan.inserts), cylinders(plan.host_cuts)
    assert len(cups) == 3 and len(pilots) == 6
    assert cups[0].height == 11.5 and cups[0].base.z == 20.5  # 3 + 17,5
    assert pilots[0].base.x == pytest.approx(100.0 - 22.5) and pilots[0].base.y == 468.0


def test_refus_porte_loin_du_cote() -> None:
    for far in (door(gap=6.0), block((720.0, 400.0, 16.0), (0.0, 900.0, 0.0))):
        with pytest.raises(JointError, match="articulée"):
            HINGE.plan(side(), far, HingeParams())
    with pytest.raises(JointError):
        HINGE.resolve(side(), door(gap=5.0), HingeParams(end_distance=400.0))  # vrai contact, trop
    assert HINGE.resolve(side(), door(gap=5.0), HingeParams()).count == 2  # 5 mm de jeu : accepté


def test_refus_porte_qui_n_est_pas_posee_de_chant() -> None:
    thick = placed((720.0, 50.0, 100.0), QUARTER_TURN_X, (0.0, 600.0, 0.0))
    with pytest.raises(JointError, match="de chant"):
        HINGE.plan(side(), thick, HingeParams())


def test_refus_cuvette_trop_profonde_ou_trop_large() -> None:
    HINGE.plan(side(), door(thickness=16.0), HingeParams(cup_depth=13.0))  # 3 mm de fond : accepté
    with pytest.raises(JointError, match="trop profonde"):
        HINGE.plan(side(), door(thickness=16.0), HingeParams(cup_depth=13.1))
    with pytest.raises(JointError, match="ne tient pas"):
        HINGE.plan(side(), door(width=40.0), HingeParams())
    assert HINGE.plan(side(), door(width=42.0), HingeParams()).guest_cuts  # 5 + 35 + 2 = 42


def test_refus_avant_trous_trop_profonds_ou_hors_du_cote() -> None:
    with pytest.raises(JointError, match="Avant-trou"):
        HINGE.plan(side(), door(), HingeParams(pilot_depth=16.1))
    HINGE.plan(side(), door(), HingeParams(pilot_depth=16.0))
    with pytest.raises(JointError, match="sortent du côté"):
        HINGE.plan(side(), door(), HingeParams(plate_distance=499.0))
    with pytest.raises(JointError, match="sortent du côté"):
        HINGE.plan(side(), door(), HingeParams(plate_distance=3.0))


def test_refus_charnieres_hors_de_la_porte_ou_trop_serrees() -> None:
    with pytest.raises(JointError, match="des angles"):
        HINGE.resolve(side(), door(), HingeParams(end_distance=19.0))
    HINGE.resolve(side(), door(), HingeParams(end_distance=19.5))
    with pytest.raises(JointError, match="des angles"):
        HINGE.resolve(side(150.0), door(150.0), HingeParams())  # 2 x 100 mm : plus de place
    with pytest.raises(JointError, match="se toucheraient"):
        HINGE.resolve(side(200.0), door(200.0), HingeParams())  # les deux au même point
    with pytest.raises(JointError, match="se toucheraient"):
        HINGE.resolve(side(), door(), HingeParams(count=20))


def test_valeurs_saisies_bornees() -> None:
    for name in ("cup_diameter", "cup_depth", "edge_distance", "end_distance", "screw_pitch"):
        with pytest.raises(JointError):
            HingeParams(**{name: 0.0})  # type: ignore[arg-type]
    with pytest.raises(JointError):
        HingeParams(count=1)
    assert HingeParams(count=0).count == 0 and HingeParams(count=2).count == 2
    with pytest.raises(JointError, match="trop petite"):
        HingeParams(edge_distance=1.99)
    assert HingeParams(edge_distance=2.0).edge_distance == 2.0
    with pytest.raises(JointError, match="trop petit"):
        HingeParams(screw_pitch=4.99)  # 3 mm de vis + 2 mm de matière
    assert HingeParams(screw_pitch=5.0).screw_pitch == 5.0
    with pytest.raises(ValueError):
        HingeParams(cup_diameter=float("nan"))
