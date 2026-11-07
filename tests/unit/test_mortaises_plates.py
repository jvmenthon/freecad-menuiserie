# SPDX-License-Identifier: LGPL-2.1-or-later
"""Faux tenons et biscuits (issue #159, ADR 0033) : mortaises plates dans les deux pièces."""

from __future__ import annotations

from typing import Any

import pytest

from freecad.menuiserie.core.geometry import JointError, PlacedBlock, Prism
from freecad.menuiserie.core.joints import JointKind, strategy_for
from freecad.menuiserie.core.joints.slots import SlotParams, half_stadium, rounded_rectangle
from tests.unit.aides_assemblages import block

TENON = strategy_for(JointKind.LOOSE_TENON)
BISCUIT = strategy_for(JointKind.BISCUIT)


def boards(length: float = 300.0, thickness: float = 22.0) -> tuple[PlacedBlock, PlacedBlock]:
    """Deux lames chant contre chant (contact en y = 100)."""
    size = (length, 100.0, thickness)
    return block(size), block(size, (0.0, 100.0, 0.0))


def prisms(solids: tuple[object, ...]) -> list[Prism]:
    assert all(isinstance(solid, Prism) for solid in solids)
    return [solid for solid in solids if isinstance(solid, Prism)]


def extent(prism: Prism, axis: int) -> tuple[float, float]:
    """Étendue du prisme selon ``axis`` (sommets et extrusion)."""
    values = [p.component(axis) for p in prism.points]
    values += [v + prism.extrusion.component(axis) for v in values]
    return min(values), max(values)


def test_faux_tenon_automatique() -> None:
    host, guest = boards()
    values = TENON.resolve(host, guest, SlotParams())
    assert (values.thickness, values.along, values.total_depth) == (6.0, 20.0, 40.0)
    assert values.count >= 2
    plan = TENON.plan(host, guest, SlotParams())
    assert len(prisms(plan.host_cuts)) == len(prisms(plan.guest_cuts)) == len(plan.inserts)
    assert len(plan.inserts) == values.count


def test_mortaises_de_part_et_d_autre_du_contact() -> None:
    host, guest = boards()
    plan = TENON.plan(
        host, guest, SlotParams(custom_size=True, thickness=6, along=20, total_depth=40, count=1)
    )
    (hole,), (guest_hole,), (insert,) = (
        prisms(p) for p in (plan.host_cuts, plan.guest_cuts, plan.inserts)
    )
    assert extent(hole, 1) == pytest.approx((79.0, 100.0))
    assert extent(guest_hole, 1) == pytest.approx((0.0, 21.0))  # repère de l'invitée
    assert extent(insert, 1) == pytest.approx((80.0, 120.0))
    assert extent(insert, 2) == pytest.approx((8.0, 14.0))
    assert extent(insert, 0) == pytest.approx((140.0, 160.0))
    assert insert.points  # section en stade : bouts arrondis, plus de quatre sommets
    assert len(insert.points) > 8


def test_taille_de_la_liste_festool() -> None:
    host, guest = boards()
    values = TENON.resolve(host, guest, SlotParams(size="5x30"))
    assert (values.thickness, values.along, values.total_depth) == (5.0, 19.0, 30.0)
    assert (values.size, values.custom_size, values.custom_allowed) == ("5x30", False, True)
    # la taille de la liste l'emporte sur les cotes tant que la case n'est pas cochée
    other = TENON.resolve(
        host, guest, SlotParams(size="4x20", thickness=6, along=20, total_depth=40)
    )
    assert other.total_depth == 20.0


def test_taille_inconnue_refusee() -> None:
    host, guest = boards()
    with pytest.raises(JointError, match="inconnue"):
        TENON.plan(host, guest, SlotParams(size="0"))
    with pytest.raises(JointError, match="inconnue"):
        BISCUIT.plan(host, guest, SlotParams(size="8x50"))
    with pytest.raises(JointError, match="invalide"):
        SlotParams(size="9x99")


def test_biscuit_sans_taille_personnalisee() -> None:
    host, guest = boards()
    values = BISCUIT.resolve(host, guest, SlotParams(custom_size=True, thickness=3, size="10"))
    assert (values.thickness, values.along, values.total_depth) == (4.0, 53.0, 19.0)
    assert (values.custom_size, values.custom_allowed) == (False, False)


def test_biscuit_en_forme_de_lamelle() -> None:
    host, guest = boards()
    plan = BISCUIT.plan(host, guest, SlotParams(size="20", count=1))
    (slot,), (guest_slot,), (insert,) = (
        prisms(p) for p in (plan.host_cuts, plan.guest_cuts, plan.inserts)
    )
    assert extent(insert, 0) == pytest.approx((122.0, 178.0))  # 56 le long du joint
    assert extent(insert, 1) == pytest.approx((88.5, 111.5))  # 23 à travers le joint
    assert extent(insert, 2) == pytest.approx((9.0, 13.0))  # fente de 4 mm
    assert extent(slot, 1) == pytest.approx((87.5, 100.0))  # demi-lamelle plus le jeu de fond
    assert extent(guest_slot, 1) == pytest.approx((0.0, 12.5))
    assert extent(slot, 0) == pytest.approx((122.0, 178.0))


def test_contours_arrondis() -> None:
    stadium = rounded_rectangle(20.0, 6.0, 3.0)
    assert max(u for u, _v in stadium) == pytest.approx(10.0)
    assert max(v for _u, v in stadium) == pytest.approx(3.0)
    assert len(stadium) == len(set(stadium))
    half = half_stadium(56.0, 12.5)
    assert min(v for _u, v in half) == pytest.approx(0.0)
    assert max(v for _u, v in half) == pytest.approx(12.5)
    assert {round(u, 6) for u, v in half if abs(v) < 1e-9} == {-28.0, 28.0}
    assert rounded_rectangle(6.0, 6.0, 3.0)  # cercle : bouts confondus, sans doublon


def test_biscuit_automatique_prend_la_plus_grande_lamelle_qui_tient() -> None:
    host, guest = boards()
    values = BISCUIT.resolve(host, guest, SlotParams())
    assert (values.thickness, values.along, values.total_depth) == (4.0, 56.0, 23.0)
    assert values.size == "20"
    thin = BISCUIT.resolve(*boards(thickness=10.0), SlotParams())
    assert thin.thickness == 4.0


def test_nombre_et_bords_automatiques_d_usage() -> None:
    host, guest = boards(length=600.0)
    values = TENON.resolve(host, guest, SlotParams())
    # premier et dernier centres à 50 mm des bords, écart de 150 mm au plus entre centres
    assert values.edge_distance == 50.0 and values.count == 5
    assert values.positions[0] == 50.0 and values.positions[-1] == 550.0
    gaps = [b - a for a, b in zip(values.positions, values.positions[1:], strict=False)]
    assert max(gaps) <= 150.0
    narrow = TENON.resolve(*boards(length=60.0), SlotParams())
    assert narrow.count == 1 and narrow.positions == (30.0,)  # contact trop court pour 50 mm


def test_decalage_en_epaisseur_et_une_seule_mortaise_sur_contact_etroit() -> None:
    host, guest = boards(length=30.0)
    values = TENON.resolve(host, guest, SlotParams(thickness_offset=2.0))
    assert values.count == 1 and values.positions == (15.0,)


@pytest.mark.parametrize(
    ("params", "text"),
    [
        (SlotParams(custom_size=True, thickness=20, along=20, total_depth=40), "trop minces"),
        (SlotParams(custom_size=True, thickness=6, along=20, total_depth=400), "trop profond"),
        (
            SlotParams(custom_size=True, thickness=6, along=20, total_depth=40, count=20),
            "ne tiennent pas",
        ),
        (
            SlotParams(custom_size=True, thickness=6, along=500, total_depth=40, count=1),
            "ne tiennent pas",
        ),
    ],
)
def test_refus(params: SlotParams, text: str) -> None:
    host, guest = boards()
    with pytest.raises(JointError, match=text):
        TENON.plan(host, guest, params)


def test_aucune_taille_ne_tient() -> None:
    with pytest.raises(JointError, match="Aucune taille"):
        TENON.plan(*boards(thickness=6.0), SlotParams())


def stacked() -> tuple[PlacedBlock, PlacedBlock]:
    """Deux planches face contre face (contact en z = 22)."""
    return block((600.0, 100.0, 22.0)), block((600.0, 100.0, 22.0), (0.0, 0.0, 22.0))


def test_contact_face_contre_face_accepte() -> None:
    host, guest = stacked()
    values = BISCUIT.resolve(host, guest, SlotParams())
    assert values.size == "20" and values.count >= 2
    plan = TENON.plan(host, guest, SlotParams(count=1))
    (hole,), (guest_hole,), (insert,) = (
        prisms(p) for p in (plan.host_cuts, plan.guest_cuts, plan.inserts)
    )
    # taille 5 x 30 (la plus grande qui tient dans 22 mm) : épaisseur selon y, pénétration selon z
    assert extent(insert, 2) == pytest.approx((7.0, 37.0))
    assert extent(insert, 1) == pytest.approx((47.5, 52.5))
    assert extent(insert, 0) == pytest.approx((290.5, 309.5))
    assert extent(hole, 2) == pytest.approx((6.0, 22.0)) and extent(guest_hole, 2)[0] == 0.0


def test_contact_face_contre_face_en_biais_refuse() -> None:
    host = block((600.0, 100.0, 22.0))
    guest = block((600.0, 100.0, 22.0), (0.0, 0.0, 40.0))  # écartées de 18 mm
    with pytest.raises(JointError, match="ne se touchent pas"):
        BISCUIT.plan(host, guest, SlotParams())


@pytest.mark.parametrize("field", ["thickness", "along", "total_depth", "hole_clearance"])
def test_parametres_invalides(field: str) -> None:
    for bad in (float("nan"), -1.0):
        values: dict[str, Any] = {field: bad}
        with pytest.raises(JointError, match="invalide"):
            SlotParams(**values)
