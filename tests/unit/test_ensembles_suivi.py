# SPDX-License-Identifier: LGPL-2.1-or-later
"""Étendues, options par défaut et règles de suivi des membres (J4a, critères F2 à F7)."""

from __future__ import annotations

import math
from dataclasses import replace

import pytest

from freecad.menuiserie.core.furniture import (
    Anchor,
    Edge,
    FollowRule,
    FurnitureAxis,
    FurnitureBox,
    FurnitureError,
    InteriorMode,
    Member,
    NoticeKind,
    default_fixed,
    edge_distances,
    fixed_by_default,
    follow_rules,
    member_spans,
)
from freecad.menuiserie.core.geometry import Vec3
from tests.unit.aides_assemblages import block
from tests.unit.aides_ensembles import BOX, FIXED_BACK, desk, piece, placed, with_options

W, D, H = FurnitureAxis.WIDTH, FurnitureAxis.DEPTH, FurnitureAxis.HEIGHT
L, R, F, B, BO, T = Edge.LEFT, Edge.RIGHT, Edge.FRONT, Edge.BACK, Edge.BOTTOM, Edge.TOP
START, END, RATIO = Anchor.START, Anchor.END, Anchor.RATIO

# --- F2 : étendues et distances -----------------------------------------------------------

SPANS = {
    "P": {W: (0, 1200, "Length"), D: (0, 600, "Width"), H: (720, 750, "Thickness")},
    "JG": {W: (0, 22, "Thickness"), D: (0, 560, "Width"), H: (0, 720, "Length")},
    "JD": {W: (1178, 1200, "Thickness"), D: (0, 560, "Width"), H: (0, 720, "Length")},
    "V": {W: (22, 1178, "Length"), D: (441, 459, "Thickness"), H: (320, 720, "Width")},
}


@pytest.mark.parametrize("key", SPANS)
def test_etendues_du_bureau(key: str) -> None:
    spans = member_spans(piece(key))
    for axis, (lo, hi, local) in SPANS[key].items():
        span = spans[axis]
        assert math.isclose(span.lo, lo, abs_tol=1e-9)
        assert math.isclose(span.hi, hi, abs_tol=1e-9)
        assert span.local == local


def test_sens_des_axes_locaux() -> None:
    joue = member_spans(piece("JG"))
    assert joue[W].reversed  # épaisseur selon -X : origine locale à x = 22
    assert math.isclose(joue[W].origin, 22.0)
    assert not joue[H].reversed
    assert not joue[W].stretchable
    assert joue[H].stretchable


def test_distances_de_la_joue_gauche() -> None:
    distances = edge_distances(piece("JG"), BOX)
    expected = {L: 0, R: 1178, F: 0, B: 40, BO: 0, T: 30}
    assert list(distances) == list(Edge)
    for edge, value in expected.items():
        assert math.isclose(distances[edge], value, abs_tol=1e-9)


def test_etendues_d_un_sous_ensemble() -> None:
    member = Member("C", box=FurnitureBox(600, 400, 720), origin=Vec3(10, 160, 0))
    spans = member_spans(member)
    assert spans[W] == (10, 610, "Width", False)
    assert spans[D] == (160, 560, "Depth", False)
    assert spans[H] == (0, 720, "Height", False)
    assert edge_distances(member, BOX)[B] == 40


def test_membre_pas_d_equerre() -> None:
    turned = Member("V", block=block((1156.0, 400.0, 18.0), (22, 459, 320), 45.0), label="Voile")
    with pytest.raises(FurnitureError) as caught:
        member_spans(turned)
    assert str(caught.value) == (
        "« Voile » n'est pas d'équerre avec l'ensemble : il ne suit pas ses cotes."
    )
    _, notices = follow_rules(BOX, [replace(turned, fixed=frozenset())])
    assert [n.kind for n in notices] == [NoticeKind.NOT_SQUARE]
    assert notices[0].params["member"] == "Voile"
    assert default_fixed(BOX, [turned, piece("P")])["V"] == frozenset()


# --- F3, F4 : options par défaut ----------------------------------------------------------

DEFAULTS = {
    "P": {L, R, F, B, T},
    "JG": {L, F, BO, T},
    "JD": {R, F, BO, T},
    "V": {L, R, T},
}


def test_options_par_defaut_du_bureau() -> None:
    assert default_fixed(BOX, desk()) == DEFAULTS


def test_options_independantes_de_l_ordre() -> None:
    assert default_fixed(BOX, list(reversed(desk()))) == DEFAULTS


@pytest.mark.parametrize(("distance", "fixed"), [(0.0, True), (0.01, True), (1.0, False)])
def test_regle_q7_bord(distance: float, fixed: bool) -> None:
    assert fixed_by_default(distance) is fixed
    assert fixed_by_default(40.0) is False


def test_retrait_de_1_mm_non_fixe() -> None:
    shelf = Member("E", block=placed((1198.0, 600.0, 18.0), (1.0, 0.0, 300.0)))
    assert default_fixed(BOX, [shelf])["E"] == {F, B}


def test_options_donnees_gardees() -> None:
    given = piece("JG", fixed=frozenset({B}))
    result = default_fixed(BOX, [given, piece("P"), piece("V")])
    assert "JG" not in result
    # V touche JG, dont l'épaisseur (axe X) ne suit aucun bord : V reste non fixe à gauche.
    assert result["V"] == {T}


def test_contact_avec_le_bord_oppose_reste_non_fixe() -> None:
    # Cale posée sur le plateau : son dessous touche le dessus de P, qui suit le haut.
    cale = Member("K", block=placed((100.0, 100.0, 20.0), (500.0, 200.0, 750.0)))
    box = FurnitureBox(1200, 600, 770)
    plateau = piece("P", fixed=frozenset({T}))
    assert default_fixed(box, [plateau, cale])["K"] == {T}


def test_contact_par_une_face_etiree() -> None:
    # Deux planches bout à bout en X : seule la planche contre le bord le suit.
    first = Member("A", block=placed((600.0, 600.0, 30.0), (0.0, 0.0, 0.0)))
    second = Member("B", block=placed((600.0, 600.0, 30.0), (600.0, 0.0, 0.0)))
    box = FurnitureBox(1300, 600, 30)
    result = default_fixed(box, [first, second])
    assert R not in result["B"]
    assert L not in result["B"]


# --- F5, F6, F7 : règles de suivi ---------------------------------------------------------


def rules_of(
    key: str, extra: dict[str, frozenset[Edge]] | None = None, **modes: InteriorMode
) -> dict[FurnitureAxis, FollowRule]:
    members = with_options(desk(**modes), extra)
    rules, _ = follow_rules(BOX, members)
    return {rule.axis: rule for rule in rules[key]}


def test_distance_fixe_suit_son_bord() -> None:
    joue = rules_of("JG", FIXED_BACK)
    assert joue[D] == FollowRule(D, START, END, "Width")
    assert joue[H] == FollowRule(H, START, END, "Length")
    assert joue[W] == FollowRule(W, START, START, None)
    assert rules_of("JD", FIXED_BACK)[W] == FollowRule(W, END, END, None)


def test_distance_non_fixe_reste_en_place() -> None:
    assert rules_of("JG")[D] == FollowRule(D, START, START, "Width")


def test_mode_proportion() -> None:
    voile = rules_of("V", V=InteriorMode.PROPORTIONAL)
    assert voile[D] == FollowRule(D, RATIO, RATIO, None)  # milieu à 450 / 600
    assert voile[H] == FollowRule(H, RATIO, END, "Width")  # le haut fixe garde son bord
    assert voile[W] == FollowRule(W, START, END, "Length")


def test_plateau_suit_le_haut_par_son_epaisseur() -> None:
    assert rules_of("P")[H] == FollowRule(H, END, END, None)


def test_options_requises() -> None:
    with pytest.raises(ValueError, match="default_fixed"):
        follow_rules(BOX, desk())


@pytest.mark.parametrize(
    ("z", "thickness", "anchor"),
    [(0.0, 750.0, START), (0.0, 30.0, START), (700.0, 30.0, END), (10.0, 735.0, END)],
    ids=["aussi épaisse", "bas plus proche", "haut plus proche", "haut plus proche (5 / 10)"],
)
def test_epaisseur_deux_faces_fixes(z: float, thickness: float, anchor: Anchor) -> None:
    board = Member(
        "S", block=placed((1200.0, 600.0, thickness), (0.0, 0.0, z)), fixed=frozenset({BO, T})
    )
    rules, notices = follow_rules(BOX, [board])
    assert rules["S"][2] == FollowRule(H, anchor, anchor, None)
    assert [n.kind for n in notices] == [NoticeKind.THICKNESS_KEPT]
