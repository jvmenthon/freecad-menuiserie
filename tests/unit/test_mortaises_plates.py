# SPDX-License-Identifier: LGPL-2.1-or-later
"""Faux tenons et biscuits (issue #159, ADR 0033) : mortaises plates dans les deux pièces."""

from __future__ import annotations

import pytest

from freecad.menuiserie.core.geometry import Box, JointError, PlacedBlock
from freecad.menuiserie.core.joints import JointKind, strategy_for
from freecad.menuiserie.core.joints.slots import SlotParams
from tests.unit.aides_assemblages import block

TENON = strategy_for(JointKind.LOOSE_TENON)
BISCUIT = strategy_for(JointKind.BISCUIT)


def boards(length: float = 300.0, thickness: float = 22.0) -> tuple[PlacedBlock, PlacedBlock]:
    """Deux lames chant contre chant (contact en y = 100)."""
    size = (length, 100.0, thickness)
    return block(size), block(size, (0.0, 100.0, 0.0))


def boxes(solids: tuple[object, ...]) -> list[Box]:
    assert all(isinstance(solid, Box) for solid in solids)
    return [solid for solid in solids if isinstance(solid, Box)]


def test_faux_tenon_automatique() -> None:
    host, guest = boards()
    values = TENON.resolve(host, guest, SlotParams())
    assert (values.thickness, values.along, values.total_depth) == (6.0, 20.0, 40.0)
    assert values.count >= 2
    plan = TENON.plan(host, guest, SlotParams())
    assert len(boxes(plan.host_cuts)) == len(boxes(plan.guest_cuts)) == len(plan.inserts)
    assert len(plan.inserts) == values.count


def test_mortaises_de_part_et_d_autre_du_contact() -> None:
    host, guest = boards()
    plan = TENON.plan(host, guest, SlotParams(thickness=6, along=20, total_depth=40, count=1))
    (hole,), (guest_hole,), (insert,) = (
        boxes(p) for p in (plan.host_cuts, plan.guest_cuts, plan.inserts)
    )
    assert hole.size(1) == pytest.approx(21.0) and guest_hole.size(1) == pytest.approx(21.0)
    assert insert.size(1) == pytest.approx(40.0)
    assert insert.size(2) == pytest.approx(6.0) and insert.size(0) == pytest.approx(20.0)
    assert insert.center(2) == pytest.approx(11.0)


def test_biscuit_automatique_prend_la_plus_grande_lamelle_qui_tient() -> None:
    host, guest = boards()
    values = BISCUIT.resolve(host, guest, SlotParams())
    assert (values.thickness, values.along, values.total_depth) == (4.0, 56.0, 23.0)
    thin = BISCUIT.resolve(*boards(thickness=10.0), SlotParams())
    assert thin.thickness == 4.0


def test_decalage_en_epaisseur_et_une_seule_mortaise_sur_contact_etroit() -> None:
    host, guest = boards(length=30.0)
    values = TENON.resolve(host, guest, SlotParams(thickness_offset=2.0))
    assert values.count == 1 and values.positions == (15.0,)


@pytest.mark.parametrize(
    ("params", "text"),
    [
        (SlotParams(thickness=20, along=20, total_depth=40), "trop minces"),
        (SlotParams(thickness=6, along=20, total_depth=400), "trop profond"),
        (SlotParams(thickness=6, along=20, total_depth=40, count=20), "ne tiennent pas"),
        (SlotParams(thickness=6, along=500, total_depth=40, count=1), "ne tiennent pas"),
    ],
)
def test_refus(params: SlotParams, text: str) -> None:
    host, guest = boards()
    with pytest.raises(JointError, match=text):
        TENON.plan(host, guest, params)


def test_aucune_taille_ne_tient() -> None:
    with pytest.raises(JointError, match="Aucune taille"):
        TENON.plan(*boards(thickness=6.0), SlotParams())


def test_contact_par_une_face_refuse() -> None:
    host, guest = block((300.0, 100.0, 22.0)), block((300.0, 100.0, 22.0), (0.0, 0.0, 22.0))
    with pytest.raises(JointError, match="par une face"):
        BISCUIT.plan(host, guest, SlotParams())


@pytest.mark.parametrize("field", ["thickness", "along", "total_depth", "hole_clearance"])
def test_parametres_invalides(field: str) -> None:
    with pytest.raises(JointError, match="invalide"):
        SlotParams(**{field: float("nan")})
    with pytest.raises(JointError, match="invalide"):
        SlotParams(**{field: -1.0})
