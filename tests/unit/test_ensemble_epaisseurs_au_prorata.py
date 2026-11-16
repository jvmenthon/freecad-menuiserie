# SPDX-License-Identifier: LGPL-2.1-or-later
"""Cote d'un ensemble que remplissent des pièces à plat (ADR 0062, doute D11 de jv) : une
couche ou plusieurs empilées se partagent la différence au prorata de leur épaisseur."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

import pytest

from freecad.menuiserie.core.furniture import (
    BlockedRowError,
    FurnitureAxis,
    FurnitureBox,
    FurnitureError,
    Member,
    check_resize,
    follow_rules,
    followed_thicknesses,
    member_spans,
    predict,
    with_default_options,
)
from tests.unit.aides_ensembles import placed


def flat(*layers: tuple[str, float, float], height: float) -> tuple[list[Member], FurnitureBox]:
    """Planches de 600 x 400 à plat (clé, z du dessous, épaisseur) dans un ensemble de
    hauteur ``height``."""
    boards = [
        Member(key, block=placed((600.0, 400.0, thickness), (0.0, 0.0, z)), label=key)
        for key, z, thickness in layers
    ]
    box = FurnitureBox(600, 400, height)
    return list(with_default_options(box, boards)), box


def taller(box: FurnitureBox, height: float) -> FurnitureBox:
    return FurnitureBox(box.width, box.depth, height)


def thickness(member: Member) -> float:
    assert member.block is not None
    return round(member.block.dimensions.thickness, 9)


def bottom(member: Member) -> float:
    return round(member_spans(member)[FurnitureAxis.HEIGHT].lo, 9)


def test_une_seule_couche_prend_la_hauteur() -> None:
    members, box = flat(("M", 0.0, 22.0), height=22.0)
    rules, _ = follow_rules(box, members)
    new = taller(box, 30.0)
    assert followed_thicknesses(box, new, members, rules) == {"M": 30.0}
    assert check_resize(box, new, members, rules, []) == ()
    after = predict(new, members, rules, followed_thicknesses(box, new, members, rules))
    assert (thickness(after["M"]), bottom(after["M"])) == (30.0, 0.0)


def test_planches_empilees_au_prorata() -> None:
    members, box = flat(("A", 0.0, 22.0), ("B", 22.0, 18.0), height=40.0)
    rules, _ = follow_rules(box, members)
    new = taller(box, 50.0)
    followers = followed_thicknesses(box, new, members, rules)
    assert followers == pytest.approx({"A": 27.5, "B": 22.5})
    assert check_resize(box, new, members, rules, []) == ()
    after = predict(new, members, rules, followers)
    assert [thickness(after[k]) for k in "AB"] == [27.5, 22.5]
    assert [bottom(after[k]) for k in "AB"] == [0.0, 27.5]  # toujours empilées


def test_plus_mince_aussi_au_prorata() -> None:
    members, box = flat(("A", 0.0, 22.0), ("B", 22.0, 18.0), height=40.0)
    rules, _ = follow_rules(box, members)
    followers = followed_thicknesses(box, taller(box, 20.0), members, rules)
    assert followers == pytest.approx({"A": 11.0, "B": 9.0})


def test_cote_qui_ne_change_pas_ne_touche_a_rien() -> None:
    members, box = flat(("A", 0.0, 22.0), ("B", 22.0, 18.0), height=40.0)
    rules, _ = follow_rules(box, members)
    assert followed_thicknesses(box, FurnitureBox(900, 400, 40), members, rules) == {}


def test_pieces_qui_ne_remplissent_pas_la_hauteur_ne_suivent_pas() -> None:
    """Un écart au-dessus : la rangée n'est pas bloquée, l'écart absorbe, les épaisseurs ne
    bougent pas (ADR 0019)."""
    members, box = flat(("A", 0.0, 22.0), height=100.0)
    rules, _ = follow_rules(box, members)
    assert followed_thicknesses(box, taller(box, 120.0), members, rules) == {}
    assert check_resize(box, taller(box, 120.0), members, rules, []) == ()


FIXES: dict[str, Callable[[Member], Member]] = {
    "verrouillée": lambda m: replace(m, locked=True),
    "dessinée": lambda m: replace(m, drawn=True),
    "copie liée": lambda m: replace(m, linked=True),
}


@pytest.mark.parametrize("option", sorted(FIXES))
def test_piece_fixe_bloque_toujours_la_rangee(option: str) -> None:
    members, box = flat(("A", 0.0, 22.0), ("B", 22.0, 18.0), height=40.0)
    members[1] = FIXES[option](members[1])
    rules, _ = follow_rules(box, members)
    assert followed_thicknesses(box, taller(box, 50.0), members, rules) == {}
    with pytest.raises(BlockedRowError):
        check_resize(box, taller(box, 50.0), members, rules, [])


def test_sous_ensemble_suivant_son_parent_refuse() -> None:
    """Un sous-ensemble suit son parent par expression : rien n'y change les épaisseurs, la
    rangée reste bloquée (``layers`` faux)."""
    members, box = flat(("A", 0.0, 22.0), height=22.0)
    rules, _ = follow_rules(box, members)
    with pytest.raises(BlockedRowError):
        check_resize(box, taller(box, 30.0), members, rules, [], layers=False)


def test_epaisseur_hors_bornes_refusee() -> None:
    members, box = flat(("M", 0.0, 22.0), height=22.0)
    rules, _ = follow_rules(box, members)
    with pytest.raises(FurnitureError, match="trop grande"):
        check_resize(box, taller(box, 400.0), members, rules, [])
