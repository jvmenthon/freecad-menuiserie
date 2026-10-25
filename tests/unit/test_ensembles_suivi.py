# SPDX-License-Identifier: LGPL-2.1-or-later
"""Étendues, options par défaut, rangées et règles de suivi des membres (J4a, critères F2 à F7 ;
ADR 0019, critères E1 à E5)."""

from __future__ import annotations

import math
from dataclasses import replace

import pytest

from freecad.menuiserie.core.furniture import (
    Edge,
    FollowRule,
    FurnitureAxis,
    FurnitureBox,
    FurnitureError,
    InteriorMode,
    Linear,
    Member,
    NoticeKind,
    default_fixed,
    edge_distances,
    fixed_by_default,
    follow_rules,
    member_spans,
    predict,
    with_default_options,
)
from freecad.menuiserie.core.geometry import Vec3
from tests.unit.aides_assemblages import block
from tests.unit.aides_ensembles import (
    BOX,
    FREE_BACK,
    TURN_Y_MINUS_90,
    desk,
    evaluate,
    piece,
    placed,
    row_of,
    with_options,
)

W, D, H = FurnitureAxis.WIDTH, FurnitureAxis.DEPTH, FurnitureAxis.HEIGHT
L, R, F, B, BO, T = Edge.LEFT, Edge.RIGHT, Edge.FRONT, Edge.BACK, Edge.BOTTOM, Edge.TOP

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

# Q7 (jv) : toute distance est fixe ; sur l'épaisseur, seule la face la plus proche de son bord.
DEFAULTS = {
    "P": {L, R, F, B, T},
    "JG": {L, F, B, BO, T},
    "JD": {R, F, B, BO, T},
    "V": {L, R, B, BO, T},
}


def test_options_par_defaut_du_bureau() -> None:
    assert default_fixed(BOX, desk()) == DEFAULTS


def test_options_independantes_de_l_ordre() -> None:
    assert default_fixed(BOX, list(reversed(desk()))) == DEFAULTS


@pytest.mark.parametrize("distance", [0.0, 0.01, 1.0, 40.0, -5.0])
def test_regle_q7_toute_distance_fixe(distance: float) -> None:
    assert fixed_by_default(distance) is True


def test_retrait_de_1_mm_fixe() -> None:
    shelf = Member("E", block=placed((1198.0, 600.0, 18.0), (1.0, 0.0, 300.0)))
    assert default_fixed(BOX, [shelf])["E"] == {L, R, F, B, BO}


def test_epaisseur_une_seule_face_fixe_par_defaut() -> None:
    full = Member("S", block=placed((1200.0, 600.0, 750.0), (0.0, 0.0, 0.0)))
    assert default_fixed(BOX, [full])["S"] == {L, R, F, B, BO}  # égalité : le bas
    members = with_options([full])
    assert follow_rules(BOX, members)[1] == ()  # rangée bloquée : ni absorbant ni avertissement


def test_options_donnees_gardees() -> None:
    given = piece("JG", fixed=frozenset({B}))
    result = default_fixed(BOX, [given, piece("P"), piece("V")])
    assert "JG" not in result
    assert result["V"] == DEFAULTS["V"]


# --- F5 à F7, E1 à E5 : rangées et règles de suivi -------------------------------------------


def rule_of(
    key: str,
    axis: FurnitureAxis,
    unfixed: dict[str, frozenset[Edge]] | None = None,
    **modes: InteriorMode,
) -> FollowRule:
    members = with_options(desk(**modes), unfixed)
    rules, _ = follow_rules(BOX, members)
    return next(rule for rule in rules[key] if rule.axis is axis)


def test_distance_fixe_suit_son_bord() -> None:
    """Bureau (options par défaut) : l'arrière de JG suit le fond, sa largeur la profondeur ; sa
    face intérieure suit l'épaisseur de la joue (ADR 0019)."""
    assert rule_of("JG", D).size == Linear(1.0, -40.0)
    assert rule_of("JG", H).size == Linear(1.0, 0.0, (("P", -1.0),))
    assert rule_of("JG", H).position.constant  # la joue part du sol
    assert rule_of("JG", W).position == Linear(0.0, 0.0, (("JG", 1.0),))
    assert rule_of("JG", W).size is None
    assert rule_of("JD", W).position == Linear(1.0, 0.0)


def test_distance_non_fixe_reste_en_place() -> None:
    """E5 : arrière décoché (Stay), l'écart arrière absorbe et la joue garde ses 560 mm."""
    rule = rule_of("JG", D, FREE_BACK)
    assert rule.size is not None
    assert rule.size.constant
    assert rule.size.at(800.0) == 560.0
    assert rule.row.blocked is False


def test_mode_stay_sur_les_deux_ecarts() -> None:
    """E5 : voile sans distance fixe devant ni derrière, mode Stay : il ne bouge pas (la cote de
    l'ensemble n'intervient pas) ; son origine locale est sa face arrière, donc 441 mm + son
    épaisseur."""
    rule = rule_of("V", D, {"V": frozenset({B})})
    assert rule.position == Linear(0.0, 441.0, (("V", 1.0),))
    assert rule.position.at(800.0, {"V": 18.0}) == 459.0
    assert rule.size is None


def test_mode_proportion() -> None:
    """E5 : les deux écarts gardent leur proportion ; Depth 800 → V à 441 x 782 / 582."""
    free = {"V": frozenset({B})}
    rule = rule_of("V", D, free, V=InteriorMode.PROPORTIONAL)
    assert rule.position.proportional
    voile = rule.position.at(800.0, {"V": 18.0}) - 18.0  # origine locale = face arrière
    assert voile == pytest.approx(441 * 782 / 582)
    assert voile == pytest.approx(592.546, abs=1e-3)
    height = rule_of("V", H, free, V=InteriorMode.PROPORTIONAL)
    assert height.size == Linear(1.0, -320.0, (("P", -1.0),))  # le bas fixe garde 320 mm


def test_plateau_suit_le_haut_par_son_epaisseur() -> None:
    rule = rule_of("P", H)
    assert rule.position == Linear(1.0, 0.0, (("P", -1.0),))
    assert rule.size is None


def test_options_requises() -> None:
    with pytest.raises(ValueError, match="default_fixed"):
        follow_rules(BOX, desk())


@pytest.mark.parametrize(
    ("key", "axis", "keys"),
    [
        ("JG", W, ["JG", "JD", "V"]),  # le voile et la joue d'en face sont en vis-à-vis
        ("JG", H, ["P", "JG"]),  # le plateau pose sur la joue
        ("JG", D, ["JG"]),  # le voile ne recouvre pas la joue en X
        ("V", H, ["P", "V"]),
        ("V", D, ["V"]),
        ("P", W, ["P"]),
        ("P", H, ["P", "JG", "JD", "V"]),
    ],
)
def test_rangee_des_vis_a_vis(key: str, axis: FurnitureAxis, keys: list[str]) -> None:
    """Un membre ne se règle que sur les pièces qui le recouvrent sur les deux autres axes."""
    row = row_of(with_options(desk()), key, axis)
    assert sorted(row.keys) == sorted(keys)
    assert row.locked == ()
    assert not row.blocked


def test_rangee_non_transitive() -> None:
    """Le voile n'est pas dans la rangée du plateau sur X, ni la joue dans celle du voile sur Z."""
    members = with_options(desk())
    assert row_of(members, "P", D).keys == ("P",)
    assert "JG" not in row_of(members, "V", H).keys


# E3 : épaisseur d'une joue


def test_epaisseur_de_joue_E3() -> None:
    """JG épaisse de 25 : elle grandit vers l'intérieur, le voile se raccourcit, JD et
    l'ensemble ne bougent pas."""
    members = with_options(desk())
    rules, _ = follow_rules(BOX, members)
    after = predict(BOX, members, rules, {"JG": 25.0})
    assert span_of(after["JG"], W) == (0.0, 25.0)
    assert span_of(after["V"], W) == (25.0, 1178.0)
    assert size_of(after["V"])[0] == 1153.0
    assert span_of(after["JD"], W) == (1178.0, 1200.0)
    assert span_of(after["P"], W) == (0.0, 1200.0)
    assert evaluate(rules, "V", W, 1200.0, {"JG": 25.0})[1] == 1153.0


def span_of(member: Member, axis: FurnitureAxis) -> tuple[float, float]:
    found = member_spans(member)[axis]
    return round(found.lo, 9), round(found.hi, 9)


def size_of(member: Member) -> tuple[float, float, float]:
    assert member.block is not None
    dims = member.block.dimensions
    return dims.length, dims.width, dims.thickness


# E4 : plusieurs pièces libres dans une rangée


def shelves(*, locked: bool = False) -> tuple[list[Member], FurnitureBox]:
    """Joue 22 | étagère S1 400 | montant D 18 | étagère S2 600 | joue 22 (C = 1062)."""
    box = FurnitureBox(1062.0, 500.0, 300.0)
    blocks = {
        "JG": placed((300.0, 500.0, 22.0), (22.0, 0.0, 0.0), TURN_Y_MINUS_90),
        "S1": placed((400.0, 500.0, 18.0), (22.0, 0.0, 100.0)),
        "D": placed((300.0, 500.0, 18.0), (440.0, 0.0, 0.0), TURN_Y_MINUS_90),
        "S2": placed((600.0, 500.0, 18.0), (440.0, 0.0, 100.0)),
        "JD": placed((300.0, 500.0, 22.0), (1062.0, 0.0, 0.0), TURN_Y_MINUS_90),
    }
    members = [Member(key, block=block, label=key) for key, block in blocks.items()]
    resolved = with_default_options(box, members)
    return [replace(m, locked=locked) if m.key == "S1" else m for m in resolved], box


def test_partage_au_prorata_E4() -> None:
    members, box = shelves()
    wider = FurnitureBox(1162.0, 500.0, 300.0)
    rules, _ = follow_rules(box, members)
    after = predict(wider, members, rules)
    assert size_of(after["S1"])[0] == pytest.approx(440.0)
    assert size_of(after["S2"])[0] == pytest.approx(660.0)
    assert span_of(after["D"], W) == pytest.approx((462.0, 480.0))
    assert span_of(after["JD"], W)[1] == pytest.approx(1162.0)


def test_etagere_verrouillee_E4() -> None:
    members, box = shelves(locked=True)
    wider = FurnitureBox(1162.0, 500.0, 300.0)
    rules, _ = follow_rules(box, members)
    after = predict(wider, members, rules)
    assert size_of(after["S1"])[0] == 400.0
    assert size_of(after["S2"])[0] == pytest.approx(700.0)
    assert span_of(after["D"], W) == pytest.approx((422.0, 440.0))


# F7 : épaisseur jamais étirée, deux faces fixes


@pytest.mark.parametrize(
    ("z", "thickness", "origin", "kept"),
    [
        (0.0, 30.0, 0.0, True),  # le bas est plus proche : il est gardé
        (700.0, 30.0, 750.0, True),  # le haut est plus proche : il est gardé (800 - 20 - 30)
        (10.0, 735.0, 800.0 - 735.0 - 5.0, True),  # 5 mm du haut contre 10 mm du bas
        (100.0, 30.0, 100.0, True),
        (0.0, 750.0, 0.0, False),  # aussi épaisse que l'ensemble : rangée bloquée
    ],
    ids=["bas plus proche", "haut plus proche", "haut plus proche (5 / 10)", "milieu", "bloquée"],
)
def test_epaisseur_deux_faces_fixes(z: float, thickness: float, origin: float, kept: bool) -> None:
    board = Member(
        "S", block=placed((1200.0, 600.0, thickness), (0.0, 0.0, z)), fixed=frozenset({BO, T})
    )
    rules, notices = follow_rules(BOX, [board])
    rule = rules["S"][2]
    assert rule.size is None
    assert [n.kind for n in notices] == ([NoticeKind.THICKNESS_KEPT] if kept else [])
    assert rule.row.blocked is not kept
    assert rule.position.at(800.0, {"S": thickness}) == pytest.approx(origin)
