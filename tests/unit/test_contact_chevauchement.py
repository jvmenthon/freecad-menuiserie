# SPDX-License-Identifier: LGPL-2.1-or-later
"""Assemblages au contact entre pièces qui se chevauchent (ADR 0016, demande de jv).

Tenon, languette, tourillons et queue d'aronde : une invitée dessinée hors tout, qui entre dans
l'hôte, est raccourcie jusqu'au contact. Le plan est celui des pièces au contact, ramené au
repère de l'invitée, plus la partie retirée.
"""

from __future__ import annotations

import dataclasses
from typing import Any

import pytest

from freecad.menuiserie.core.geometry import (
    Box,
    JointError,
    RigidTransform,
    Solid,
    Vec3,
    moved,
)
from freecad.menuiserie.core.joints import JointKind, JointPlan, strategy_for
from freecad.menuiserie.core.joints.dovetail import DovetailParams
from freecad.menuiserie.core.joints.dowels import DowelParams
from freecad.menuiserie.core.joints.mortise_tenon import MortiseTenonParams
from freecad.menuiserie.core.joints.tongue_groove import TongueGrooveParams
from tests.unit.aides_assemblages import (
    block,
    dovetail_corner,
    placed,
    rail,
    rotation_y,
    stile,
)

TENON = strategy_for(JointKind.MORTISE_TENON)


def box(low: tuple[float, float, float], high: tuple[float, float, float]) -> Box:
    return Box(Vec3(*low), Vec3(*high))


def rounded(solids: tuple[Solid, ...]) -> list[Any]:
    """Solides comparables malgré le bruit des rotations (cotes arrondies au µm)."""
    return [_round(solid) for solid in solids]


def _round(value: Any) -> Any:
    if isinstance(value, float):
        return round(value, 6) + 0.0  # + 0.0 : -0.0 devient 0.0
    if isinstance(value, tuple):
        return tuple(_round(item) for item in value)
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return (type(value).__name__, *(_round(v) for v in dataclasses.astuple(value)))
    return value


def shifted(solids: tuple[Solid, ...], shift: Vec3) -> tuple[Solid, ...]:
    back = RigidTransform(RigidTransform.identity().rotation, shift)
    return tuple(moved(solid, back) for solid in solids)


# Hôte, invitée au contact, invitée dessinée hors tout, retour au repère de l'invitée, partie
# retirée, paramètres.
CASES = {
    # Traverse 280 + 60 dessinée jusqu'au chant extérieur du montant.
    "tenon": (
        JointKind.MORTISE_TENON,
        stile(),
        rail(),
        block((340.0, 60.0, 22.0), (60.0, 0.0, 0.0), 90.0),
        Vec3(60.0, 0.0, 0.0),
        box((0, 0, 0), (60, 60, 22)),
        MortiseTenonParams(),
    ),
    "tourillons": (
        JointKind.DOWELS,
        stile(),
        rail(),
        block((340.0, 60.0, 22.0), (60.0, 0.0, 0.0), 90.0),
        Vec3(60.0, 0.0, 0.0),
        box((0, 0, 0), (60, 60, 22)),
        DowelParams(),
    ),
    # Lame qui entre de 10 mm dans le chant de l'autre.
    "languette": (
        JointKind.TONGUE_GROOVE,
        block((1000.0, 100.0, 22.0)),
        block((1000.0, 100.0, 22.0), (0.0, 100.0, 0.0)),
        block((1000.0, 110.0, 22.0), (0.0, 90.0, 0.0)),
        Vec3(0.0, 10.0, 0.0),
        box((0, 0, 0), (1000, 10, 22)),
        TongueGrooveParams(),
    ),
    # Angle de caisson : les deux planches dessinées hors tout, qui se chevauchent au coin.
    "queue d'aronde": (
        JointKind.DOVETAIL,
        *dovetail_corner(),
        placed((418.0, 150.0, 18.0), rotation_y(-90.0), (18.0, 0.0, 0.0)),
        Vec3(18.0, 0.0, 0.0),
        box((0, 0, 0), (18, 150, 18)),
        DovetailParams(),
    ),
}


@pytest.mark.parametrize("case", CASES.values(), ids=CASES.keys())
def test_invitee_hors_tout_raccourcie_jusqu_au_contact(case: tuple[Any, ...]) -> None:
    kind, host, contact_guest, overlapping_guest, shift, trim, params = case
    strategy = strategy_for(kind)
    reference: JointPlan = strategy.plan(host, contact_guest, params)
    plan: JointPlan = strategy.plan(host, overlapping_guest, params)
    assert rounded(plan.host_cuts) == rounded(reference.host_cuts)
    assert rounded(plan.inserts) == rounded(reference.inserts)
    assert rounded(plan.guest_cuts) == rounded(shifted(reference.guest_cuts, shift))
    assert rounded(plan.guest_additions) == rounded(shifted(reference.guest_additions, shift))
    assert rounded(plan.guest_trims) == rounded((trim,))
    assert reference.guest_trims == ()
    assert strategy.resolve(host, overlapping_guest, params) == strategy.resolve(
        host, contact_guest, params
    )


def test_tenon_traverse_entree_de_5_mm() -> None:
    """Traverse avancée de 5 mm dans le montant : raccourcie de 5 mm, tenon de 40 mm depuis
    la face du montant."""
    plan = TENON.plan(stile(), rail(y=55.0), MortiseTenonParams())
    assert rounded(plan.guest_trims) == rounded((box((0, 0, 0), (5, 60, 22)),))
    assert rounded(plan.guest_additions) == rounded((box((-35, 10, 7.5), (5, 50, 14.5)),))
    assert rounded(plan.host_cuts) == rounded((box((10, 18, 7.5), (50, 60, 14.5)),))


def test_raccourcie_par_la_face_qui_perd_le_moins() -> None:
    """Traverse qui entre de 60 mm par son bout : elle est raccourcie par le bout, pas par un
    chant (qui la couperait sur toute sa longueur)."""
    host = stile()
    guest = block((340.0, 60.0, 22.0), (60.0, 0.0, 0.0), 90.0)
    plan = TENON.plan(host, guest, MortiseTenonParams())
    (trim,) = plan.guest_trims
    assert isinstance(trim, Box)
    assert (trim.size(0), trim.size(1), trim.size(2)) == pytest.approx((60, 60, 22))


def test_refus_invitee_entierement_dans_l_hote() -> None:
    inside = block((10.0, 10.0, 10.0), (5.0, 5.0, 5.0))
    with pytest.raises(JointError, match="se chevauchent"):
        TENON.plan(stile(), inside, MortiseTenonParams())


def test_refus_traverse_qui_traverse_le_montant() -> None:
    """Traverse qui dépasse des deux chants du montant : aucune face ne la ramène au contact
    sans la couper en deux."""
    through = block((400.0, 60.0, 22.0), (60.0, -50.0, 0.0), 90.0)
    with pytest.raises(JointError, match="se chevauchent"):
        TENON.plan(stile(), through, MortiseTenonParams())
