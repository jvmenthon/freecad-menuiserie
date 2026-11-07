# SPDX-License-Identifier: LGPL-2.1-or-later
"""Queue d'aronde entre pièces en biais (ADR 0034, lot S-c, critères Q1 et Q2)."""

from __future__ import annotations

import pytest

from freecad.menuiserie.core._polyhedron import Polyhedron
from freecad.menuiserie.core.geometry import JointError, PlacedBlock
from freecad.menuiserie.core.joints import JointKind, JointPlan, strategy_for
from freecad.menuiserie.core.joints.dovetail import DovetailParams
from tests.unit.aides_assemblages import block, placed, rotation_y
from tests.unit.aides_biais import product, rotation_x

DOVETAIL = strategy_for(JointKind.DOVETAIL)
SIZE = (400.0, 150.0, 18.0)


def corner(degrees: float) -> tuple[PlacedBlock, PlacedBlock]:
    """Planche à plat et planche debout qui penche de ``degrees`` autour de son épaisseur."""
    guest = placed(SIZE, product(rotation_x(degrees), rotation_y(-90.0)), (18.0, 0.0, 18.0))
    return block(SIZE), guest


def volumes(plan: JointPlan, count: int) -> list[float]:
    solids = [s for s in plan.guest_additions if isinstance(s, Polyhedron)]
    return [s.volume() for s in solids[-count:]]


@pytest.mark.parametrize("degrees", [10.0, 30.0])
def test_les_queues_en_biais_ont_un_logement_chacune(degrees: float) -> None:
    host, guest = corner(degrees)
    values = DOVETAIL.resolve(host, guest, DovetailParams())
    plan = DOVETAIL.plan(host, guest, DovetailParams())
    assert len(plan.host_cuts) == values.tail_count
    assert all(v > 0 for v in volumes(plan, values.tail_count))
    assert plan.guest_bevels


def test_les_queues_en_biais_rejoignent_le_cas_d_equerre_quand_le_biais_tend_vers_zero() -> None:
    host, guest = corner(0.05)
    values = DOVETAIL.resolve(host, guest, DovetailParams())
    plan = DOVETAIL.plan(host, guest, DovetailParams())
    trapezoid = (values.tail_width + values.tail_base) / 2 * 18.0 * 18.0  # L = e = 18 mm
    for volume in volumes(plan, values.tail_count):
        assert volume == pytest.approx(trapezoid, rel=0.02)


def test_griffes_sur_l_hote_en_biais() -> None:
    host, guest = corner(10.0)
    values = DOVETAIL.resolve(host, guest, DovetailParams(tails_on_host=True))
    plan = DOVETAIL.plan(host, guest, DovetailParams(tails_on_host=True))
    assert len(plan.host_cuts) == values.tail_count + 1
    assert all(v > 0 for v in volumes(plan, values.tail_count + 1))


def test_queue_d_aronde_en_biais_refuse_une_inclinaison_hors_de_l_epaisseur() -> None:
    guest = placed(SIZE, rotation_y(-60.0), (18.0, 0.0, 18.0))
    with pytest.raises(JointError):
        DOVETAIL.plan(block(SIZE), guest, DovetailParams())
