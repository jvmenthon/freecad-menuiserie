# SPDX-License-Identifier: LGPL-2.1-or-later
"""Pièces en biais dans un ensemble : suivi par translation (AB-d, D1 à D4, ADR 0024)."""

from __future__ import annotations

from dataclasses import replace

import pytest

from freecad.menuiserie.core.furniture import (
    Follow,
    FurnitureBox,
    FurnitureError,
    Member,
    bindings_for,
    check_resize,
    default_fixed,
    follow_rules,
    follow_summary,
    predict,
    with_default_options,
)
from freecad.menuiserie.core.geometry import Vec3
from tests.unit.aides_biais import stile_block, tilted_rail
from tests.unit.aides_ensembles import placed

TURN_Z_45 = [[0.7071068, -0.7071068, 0.0], [0.7071068, 0.7071068, 0.0], [0.0, 0.0, 1.0]]
BOX = FurnitureBox(600.0, 400.0, 700.0)
WIDER = FurnitureBox(800.0, 400.0, 700.0)


def slanted(key: str, x: float, y: float = 50.0) -> Member:
    return Member(
        key,
        block=placed((200.0, 100.0, 18.0), (x, y, 0.0), TURN_Z_45),
        fixed=frozenset(),
        label=key,
    )


def origin_of(member: Member) -> Vec3:
    assert member.block is not None
    return member.block.placement.translation


def test_cote_proche_du_bord_gauche_ne_bouge_pas() -> None:
    left = slanted("G", 150.0)
    rules, _ = follow_rules(BOX, [left])
    assert predict(WIDER, [left], rules)["G"] == left


def test_cote_proche_du_bord_droit_suit_la_largeur() -> None:
    right = slanted("D", 450.0)
    rules, _ = follow_rules(BOX, [right])
    moved = predict(WIDER, [right], rules)["D"]
    assert origin_of(moved).x == pytest.approx(origin_of(right).x + 200.0)
    assert origin_of(moved).y == origin_of(right).y
    assert moved.block is not None and right.block is not None
    assert moved.block.dimensions == right.block.dimensions  # cotes constantes
    assert moved.block.placement.rotation == right.block.placement.rotation


def test_aucune_rangee_et_aucune_epaisseur_bloquee() -> None:
    """D2 : le membre en biais est seul dans sa rangée et ne gêne pas les autres."""
    rules, _ = follow_rules(BOX, [slanted("D", 450.0)])
    assert all(rule.row.keys == () and not rule.row.blocked for rule in rules["D"])
    free = replace(slanted("D", 450.0), fixed=None)
    assert default_fixed(BOX, [free])["D"] == frozenset()


def test_colonne_suit() -> None:
    member = slanted("D", 450.0)
    rules, _ = follow_rules(BOX, [member])
    assert follow_summary(member, rules["D"]) == (Follow.OBLIQUE,)


def test_liaison_de_position_ecrite() -> None:
    member = slanted("D", 450.0)
    rules, _ = follow_rules(BOX, [member])
    bindings, _ = bindings_for("Caisson", [member], rules)
    assert [b.prop for b in bindings] == ["Placement.Base.x"]


def test_assemblage_defait_est_refuse_par_joint_perdu() -> None:
    """D3 : la traverse en biais suit le bord éloigné, le montant reste : le contact est perdu."""
    stile = Member("M", block=stile_block(), label="Montant", locked=True)
    rail = Member("T", block=tilted_rail(20.0), label="Traverse")
    box, wider = FurnitureBox(600.0, 340.0, 200.0), FurnitureBox(600.0, 440.0, 200.0)
    members = list(with_default_options(box, [stile, rail]))
    rules, _ = follow_rules(box, members)
    assert check_resize(box, box, members, rules, [("M", "T")]) == ()
    with pytest.raises(FurnitureError, match="Montant"):
        check_resize(box, wider, members, rules, [("M", "T")])
