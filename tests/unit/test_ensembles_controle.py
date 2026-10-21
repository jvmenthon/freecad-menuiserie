# SPDX-License-Identifier: LGPL-2.1-or-later
"""Aperçu, refus d'un redimensionnement et sous-ensembles (J4a, critères F10, F11)."""

from __future__ import annotations

import math
from dataclasses import replace

import pytest

from freecad.menuiserie.core.furniture import (
    Edge,
    FurnitureAxis,
    FurnitureBox,
    FurnitureError,
    InteriorMode,
    Member,
    Notice,
    NoticeKind,
    check_membership,
    check_resize,
    follow_rules,
    member_spans,
    predict,
)
from freecad.menuiserie.core.geometry import Vec3
from tests.unit.aides_assemblages import block
from tests.unit.aides_ensembles import BOX, FIXED_BACK, desk, placed, with_options

W, D, H = FurnitureAxis.WIDTH, FurnitureAxis.DEPTH, FurnitureAxis.HEIGHT
DEEPER = FurnitureBox(1200, 800, 750)
TALLER = FurnitureBox(1200, 600, 800)


def predicted(
    new: FurnitureBox,
    extra: dict[str, frozenset[Edge]] | None = None,
    **modes: InteriorMode,
) -> dict[str, Member]:
    members = with_options(desk(**modes), extra)
    rules, _ = follow_rules(BOX, members)
    return dict(predict(BOX, new, members, rules))


def span(member: Member, axis: FurnitureAxis) -> tuple[float, float]:
    found = member_spans(member)[axis]
    return round(found.lo, 9), round(found.hi, 9)


def size(member: Member) -> tuple[float, float, float]:
    assert member.block is not None
    dims = member.block.dimensions
    return dims.length, dims.width, dims.thickness


# --- F10 : aperçu -------------------------------------------------------------------------


def test_profondeur_800_avec_l_arriere_des_joues_fixe() -> None:
    result = predicted(DEEPER, FIXED_BACK)
    assert size(result["P"]) == (1200, 800, 30)
    assert size(result["JG"]) == (720, 760, 22)
    assert size(result["JD"]) == (720, 760, 22)
    assert span(result["V"], D) == (441, 459)  # Stay : immobile


def test_profondeur_800_voile_en_proportion() -> None:
    result = predicted(DEEPER, FIXED_BACK, V=InteriorMode.PROPORTIONAL)
    assert span(result["V"], D) == (591, 609)


def test_profondeur_800_options_par_defaut() -> None:
    result = predicted(DEEPER)
    assert size(result["P"]) == (1200, 800, 30)
    assert size(result["JG"]) == (720, 560, 22)


def test_hauteur_800() -> None:
    result = predicted(TALLER, FIXED_BACK)
    plateau = result["P"]
    assert plateau.block is not None
    assert math.isclose(plateau.block.placement.translation.z, 770)
    assert size(plateau) == (1200, 600, 30)  # la hauteur ne traverse pas sa longueur
    assert size(result["V"]) == (1156, 450, 18)
    assert size(result["JG"]) == (770, 560, 22)


def test_largeur_1400_deplace_la_joue_droite() -> None:
    result = predicted(FurnitureBox(1400, 600, 750))
    assert span(result["JD"], W) == (1378, 1400)
    assert size(result["V"])[0] == 1356


def test_propriete_pilotee_gardee_par_l_apercu() -> None:
    members = with_options(desk(V=InteriorMode.PROPORTIONAL))
    members = [
        replace(m, driven=frozenset({"Placement.Base.y"})) if m.key == "V" else m for m in members
    ]
    rules, _ = follow_rules(BOX, members)
    assert span(predict(BOX, DEEPER, members, rules)["V"], D) == (441, 459)
    notices = check_resize(BOX, DEEPER, members, rules, [])
    assert [(n.kind, n.params["property"]) for n in notices] == [
        (NoticeKind.USER_FORMULA, "Placement.Base.y")
    ]
    assert check_resize(BOX, TALLER, members, rules, []) == ()


def test_cote_pilotee_gardee_par_l_apercu() -> None:
    members = with_options(desk(), FIXED_BACK)
    members = [replace(m, driven=frozenset({"Width"})) if m.key == "JG" else m for m in members]
    rules, _ = follow_rules(BOX, members)
    assert size(predict(BOX, DEEPER, members, rules)["JG"]) == (720, 560, 22)


# --- F10 : refus --------------------------------------------------------------------------


def resize(
    new: FurnitureBox,
    members: list[Member],
    joined: list[tuple[str, str]] | None = None,
) -> tuple[Notice, ...]:
    rules, _ = follow_rules(BOX, members)
    return check_resize(BOX, new, members, rules, joined or [])


def test_joue_trop_petite() -> None:
    with pytest.raises(FurnitureError) as caught:
        resize(FurnitureBox(1200, 30, 750), with_options(desk(), FIXED_BACK))
    assert (
        str(caught.value)
        == "« Joue gauche » deviendrait trop petite : Width = \N{MINUS SIGN}10 mm."
    )


def test_voile_trop_petit() -> None:
    with pytest.raises(FurnitureError) as caught:
        resize(FurnitureBox(1200, 600, 350.05), with_options(desk()))
    assert caught.value.params == {"member": "Voile", "property": "Width", "value": "0,05"}


def test_piece_trop_grande() -> None:
    long = Member(
        "A", block=placed((1300.0, 600.0, 30.0), (-100.0, 0.0, 0.0)), fixed=frozenset(Edge)
    )
    with pytest.raises(FurnitureError, match="trop grande"):
        resize(FurnitureBox(20_000, 600, 750), [long])


def test_contact_d_assemblage_perdu() -> None:
    members = with_options(desk())
    members = [
        replace(m, fixed=frozenset({Edge.LEFT, Edge.TOP})) if m.key == "V" else m for m in members
    ]
    wider = FurnitureBox(1400, 600, 750)
    assert resize(wider, members, [("JG", "V")]) == ()
    with pytest.raises(FurnitureError) as caught:
        resize(wider, members, [("JG", "V"), ("JD", "V")])
    assert caught.value.params == {"host": "Joue droite", "guest": "Voile"}


def test_chevauchement_perdu() -> None:
    first = Member(
        "A", block=placed((600.0, 600.0, 30.0), (0.0, 0.0, 0.0)), fixed=frozenset({Edge.LEFT})
    )
    second = Member(
        "B",
        block=placed((600.0, 600.0, 30.0), (500.0, 0.0, 0.0)),
        fixed=frozenset({Edge.RIGHT}),
        mode=InteriorMode.PROPORTIONAL,
    )
    box = FurnitureBox(1100, 600, 30)
    rules, _ = follow_rules(box, [first, second])
    with pytest.raises(FurnitureError):
        check_resize(box, FurnitureBox(2000, 600, 30), [first, second], rules, [("A", "B")])
    assert (
        check_resize(box, FurnitureBox(1150, 600, 30), [first, second], rules, [("A", "B")]) == ()
    )


def test_paire_hors_ensemble_ignoree() -> None:
    assert resize(DEEPER, with_options(desk()), [("JG", "Autre")]) == ()


def test_piece_qui_depasse() -> None:
    notices = resize(FurnitureBox(1200, 500, 750), with_options(desk()))
    assert [(n.kind, n.params["member"]) for n in notices] == [
        (NoticeKind.OUTSIDE_BOX, "Joue gauche"),
        (NoticeKind.OUTSIDE_BOX, "Joue droite"),
    ]


# --- F11 : sous-ensemble ------------------------------------------------------------------


def caisson(**changes: object) -> Member:
    member = Member(
        "C",
        box=FurnitureBox(600, 560, 720),
        origin=Vec3(300, 0, 0),
        fixed=frozenset({Edge.FRONT, Edge.BACK, Edge.BOTTOM}),
        label="Caisson",
    )
    return replace(member, **changes)  # type: ignore[arg-type]


def test_sous_ensemble_suit_la_profondeur() -> None:
    member = caisson()
    rules, _ = follow_rules(BOX, [member])
    result = predict(BOX, DEEPER, [member], rules)["C"]
    assert result.box == FurnitureBox(600, 760, 720)
    assert result.origin == Vec3(300, 0, 0)


def test_sous_ensemble_en_proportion() -> None:
    member = caisson(fixed=frozenset(), mode=InteriorMode.PROPORTIONAL)
    rules, _ = follow_rules(BOX, [member])
    result = predict(BOX, FurnitureBox(2400, 600, 750), [member], rules)["C"]
    assert result.box is not None
    assert result.origin is not None
    assert math.isclose(result.box.width, 1200)
    assert math.isclose(result.box.depth, 560)
    assert math.isclose(result.box.height, 720)
    assert math.isclose(result.origin.x, 600)


def test_sous_ensemble_en_contact_avec_une_piece() -> None:
    assert resize(DEEPER, [caisson(), *with_options(desk())], [("C", "P")]) == ()


LABELS = {"B": "Bureau", "C": "Caisson", "T": "Tiroir"}


@pytest.mark.parametrize(
    ("furniture", "candidate", "parents"),
    [("B", "B", {}), ("C", "B", {"C": "B"}), ("T", "B", {"T": "C", "C": "B"})],
    ids=["lui-même", "parent", "ancêtre"],
)
def test_cycle_d_ensembles_refuse(furniture: str, candidate: str, parents: dict[str, str]) -> None:
    with pytest.raises(FurnitureError, match="un ensemble ne peut pas être membre"):
        check_membership(furniture, candidate, parents, LABELS)


def test_ensemble_accepte() -> None:
    check_membership("B", "C", {}, LABELS)
    check_membership("B", "T", {"T": "C"}, {})
    check_membership("A", "C", {"A": "X", "X": "A"}, {})  # boucle déjà présente : pas d'attente


def test_membre_pas_d_equerre_ignore() -> None:
    turned = Member(
        "X", block=block((100.0, 100.0, 18.0), (500.0, 200.0, 0.0), 45.0), fixed=frozenset()
    )
    members = [*with_options(desk()), turned]
    rules, notices = follow_rules(BOX, members)
    assert "X" not in predict(BOX, DEEPER, members, rules)
    assert check_resize(BOX, DEEPER, members, rules, [("X", "P")]) == ()
    assert [n.kind for n in notices] == [NoticeKind.NOT_SQUARE]
