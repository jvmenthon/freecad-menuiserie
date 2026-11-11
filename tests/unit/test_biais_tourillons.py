# SPDX-License-Identifier: LGPL-2.1-or-later
"""Tourillons entre pièces en biais (ADR 0034, lot S-c, critères D1 et D2)."""

from __future__ import annotations

import math

import pytest

from freecad.menuiserie.core._polyhedron import SlantedCylinder
from freecad.menuiserie.core.geometry import JointError
from freecad.menuiserie.core.joints import JointKind, strategy_for
from freecad.menuiserie.core.joints.dowels import DowelParams
from tests.unit.aides_biais import leaning_rail, stile_block, tilted_rail

DOWELS = strategy_for(JointKind.DOWELS)


@pytest.mark.parametrize("degrees", [5.0, 10.0, 30.0])
def test_les_tourillons_en_biais_suivent_l_axe_de_l_invitee(degrees: float) -> None:
    host, guest = stile_block(), tilted_rail(degrees)
    values = DOWELS.resolve(host, guest, DowelParams())
    plan = DOWELS.plan(host, guest, DowelParams())
    assert len(plan.inserts) == len(plan.host_cuts) == len(plan.guest_cuts) == values.count
    for dowel, hole in zip(plan.inserts, plan.host_cuts, strict=True):
        assert isinstance(dowel, SlantedCylinder) and isinstance(hole, SlantedCylinder)
        assert dowel.radius == pytest.approx(values.diameter / 2)
        assert dowel.height == pytest.approx(values.dowel_length)
        assert hole.height == pytest.approx(values.host_depth + values.hole_clearance)
        # Le perçage et le tourillon sont coaxiaux.
        assert sum(
            a * b
            for a, b in zip(
                (dowel.direction.x, dowel.direction.y, dowel.direction.z),
                (hole.direction.x, hole.direction.y, hole.direction.z),
                strict=True,
            )
        ) == pytest.approx(1.0)


def test_les_tourillons_en_biais_ont_le_meme_nombre_qu_en_equerre() -> None:
    host = stile_block()
    straight = DOWELS.resolve(host, tilted_rail(0.0), DowelParams())
    slanted = DOWELS.resolve(host, tilted_rail(10.0), DowelParams())
    assert slanted.count == straight.count
    assert slanted.diameter == straight.diameter


def test_les_tourillons_en_biais_marquent_le_bout_coupe() -> None:
    plan = DOWELS.plan(stile_block(), tilted_rail(10.0), DowelParams())
    assert len(plan.guest_bevels) == 1
    assert math.isclose(plan.guest_bevels[0].saw_angles()[0], 10.0, abs_tol=0.1)


def test_les_tourillons_en_biais_acceptent_une_inclinaison_dans_l_epaisseur() -> None:
    host = stile_block(thickness=80.0)
    plan = DOWELS.plan(host, leaning_rail(10.0), DowelParams())
    assert plan.inserts


def test_un_tourillon_ne_sort_pas_de_la_face_de_l_hote() -> None:
    host = stile_block()
    guest = tilted_rail(30.0, centre_x=5.0)  # bout près du bord de l'hôte
    with pytest.raises(JointError):
        DOWELS.plan(host, guest, DowelParams())
