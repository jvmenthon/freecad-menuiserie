# SPDX-License-Identifier: LGPL-2.1-or-later
"""Pièce en bois dans un ensemble : cotes dessinées, toujours fixes (spec piece-en-bois, PD-f,
critère F1 ; ADR 0020, décision 8). Le voile du bureau de référence joue la pièce en bois."""

from __future__ import annotations

from dataclasses import replace

import pytest

from freecad.menuiserie.core.furniture import (
    BlockedRowError,
    FurnitureAxis,
    FurnitureBox,
    Member,
    NoticeKind,
    bindings_for,
    check_resize,
    follow_rules,
    follow_summary,
    member_spans,
    predict,
)
from tests.unit.aides_ensembles import BOX, LABELS, desk, placed, with_options

DEPTH = FurnitureAxis.DEPTH
DEEPER = FurnitureBox(1200, 800, 750)
WIDER = FurnitureBox(1300, 600, 750)
DRAWN_TEXT = "« Voile » : cote dessinée : modifiez le dessin"


def drawn_desk(key: str = "V") -> list[Member]:
    """Bureau aux options par défaut dont la pièce ``key`` a des cotes dessinées."""
    return [replace(m, drawn=m.key == key) for m in with_options(desk())]


def test_des_cotes_dessinees_sont_toujours_fixes() -> None:
    [voile] = [m for m in drawn_desk() if m.key == "V"]
    assert voile.drawn and voile.locked
    assert replace(voile, locked=False).locked  # rien ne la déverrouille
    assert Member("S", block=placed((100.0, 50.0, 18.0), (0.0, 0.0, 0.0)), drawn=True).locked


def test_drawn_est_un_booleen() -> None:
    block = placed((100.0, 50.0, 18.0), (0.0, 0.0, 0.0))
    with pytest.raises(ValueError, match=r"Member\.drawn"):
        Member("S", block=block, drawn=1)  # type: ignore[arg-type]


def test_la_regle_qui_etirerait_la_piece_avertit() -> None:
    _rules, notices = follow_rules(BOX, drawn_desk())
    [warning] = [n for n in notices if n.kind is NoticeKind.DRAWN_SIZE]
    assert warning.message.startswith(DRAWN_TEXT)
    assert warning.params == {"member": LABELS["V"]}


def test_pas_d_avertissement_pour_une_piece_de_bois() -> None:
    _rules, notices = follow_rules(BOX, with_options(desk()))
    assert not [n for n in notices if n.kind is NoticeKind.DRAWN_SIZE]


def test_pas_d_avertissement_si_rien_ne_l_etirerait() -> None:
    """Seule dans sa rangée, sans distance fixe : la pièce reste en place, même libre."""
    shelf = Member(
        "S",
        block=placed((300.0, 200.0, 20.0), (100.0, 100.0, 100.0)),
        fixed=frozenset(),
        drawn=True,
    )
    _rules, notices = follow_rules(BOX, [shelf])
    assert not notices


def test_la_piece_se_deplace_au_lieu_de_s_etirer() -> None:
    members = drawn_desk()
    rules, _ = follow_rules(BOX, members)
    voile = predict(DEEPER, members, rules)["V"]
    assert voile.block is not None
    dims = voile.block.dimensions
    assert (dims.length, dims.width, dims.thickness) == (1156.0, 400.0, 18.0)
    span = member_spans(voile)[DEPTH]
    assert (round(span.lo, 6), round(span.hi, 6)) == (641.0, 659.0)  # suit le fond


def test_aucune_liaison_de_cote_seulement_la_position() -> None:
    members = drawn_desk()
    rules, _ = follow_rules(BOX, members)
    found, _ = bindings_for("Bureau", members, rules)
    props = {b.prop for b in found if b.key == "V"}
    assert props
    assert props <= {"Placement.Base.x", "Placement.Base.y", "Placement.Base.z"}


def test_rangee_bloquee_par_la_piece_dessinee() -> None:
    members = drawn_desk()
    rules, _ = follow_rules(BOX, members)
    with pytest.raises(BlockedRowError) as caught:
        check_resize(BOX, WIDER, members, rules, [])
    assert caught.value.locked == ("V",)
    assert "cotes fixes : « Voile »" in str(caught.value)


def test_colonne_suit_montre_les_cotes_fixes() -> None:
    members = drawn_desk()
    rules, _ = follow_rules(BOX, members)
    [voile] = [m for m in members if m.key == "V"]
    assert follow_summary(voile, rules["V"])[0].value == "Locked"
