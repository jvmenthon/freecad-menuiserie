# SPDX-License-Identifier: LGPL-2.1-or-later
"""Cas limites de l'ADR 0062 : couches côte à côte, trois couches, rangée sur X, pièce tournée,
bornes d'épaisseur, rangée qui ne remplit pas la cote."""

from __future__ import annotations

import pytest

from freecad.menuiserie.core.furniture import (
    FurnitureBox,
    FurnitureError,
    Member,
    check_resize,
    follow_rules,
    followed_thicknesses,
    predict,
    with_default_options,
)
from tests.unit.aides_ensembles import TURN_X_PLUS_90, TURN_Y_MINUS_90, placed


def height_box(boards: list[Member], height: float) -> FurnitureBox:
    box = FurnitureBox(600, 400, height)
    boards[:] = list(with_default_options(box, boards))
    return box


def board(key: str, z: float, thickness: float, x: float = 0.0, length: float = 600.0) -> Member:
    return Member(key, block=placed((length, 400.0, thickness), (x, 0.0, z)), label=key)


def test_trois_couches_au_prorata() -> None:
    boards = [board("A", 0, 10), board("B", 10, 20), board("C", 30, 30)]
    box = height_box(boards, 60)
    rules, _ = follow_rules(box, boards)
    new = FurnitureBox(600, 400, 120)
    assert followed_thicknesses(box, new, boards, rules) == pytest.approx(
        {"A": 20.0, "B": 40.0, "C": 60.0}
    )
    assert check_resize(box, new, boards, rules, []) == ()


def test_pieces_cote_a_cote_dans_une_meme_couche() -> None:
    """Deux planches de 22 mm côte à côte (X) sous un dessus de 18 mm : les trois suivent."""
    boards = [
        board("G", 0, 22, 0, 300),
        board("D", 0, 22, 300, 300),
        board("T", 22, 18),
    ]
    box = height_box(boards, 40)
    rules, _ = follow_rules(box, boards)
    new = FurnitureBox(600, 400, 50)
    got = followed_thicknesses(box, new, boards, rules)
    assert got == pytest.approx({"G": 27.5, "D": 27.5, "T": 22.5})
    after = predict(new, boards, rules, got)
    assert after["T"].block is not None
    assert check_resize(box, new, boards, rules, []) == ()


def test_une_couche_plus_une_piece_non_a_plat_ne_suit_pas() -> None:
    """Un montant debout qui traverse toute la hauteur : pas une couche, comportement d'avant."""
    stile = Member(
        "M", block=placed((40.0, 400.0, 22.0), (0.0, 0.0, 0.0), TURN_Y_MINUS_90), label="M"
    )
    boards = [board("A", 0, 22), stile]
    box = height_box(boards, 22)
    rules, _ = follow_rules(box, boards)
    new = FurnitureBox(600, 400, 30)
    assert "M" not in followed_thicknesses(box, new, boards, rules)


def test_epaisseur_minimale_refusee() -> None:
    boards = [board("A", 0, 10), board("B", 10, 30)]
    box = height_box(boards, 40)
    rules, _ = follow_rules(box, boards)
    with pytest.raises(FurnitureError, match="trop petite"):
        check_resize(box, FurnitureBox(600, 400, 0.3), boards, rules, [])  # A : 0,075 mm


def test_epaisseur_juste_au_dessus_du_minimum_acceptee() -> None:
    boards = [board("A", 0, 10), board("B", 10, 30)]
    box = height_box(boards, 40)
    rules, _ = follow_rules(box, boards)
    new = FurnitureBox(600, 400, 0.4)  # A : 0,1 mm
    assert check_resize(box, new, boards, rules, []) == ()


def test_epaisseur_maximale() -> None:
    boards = [board("A", 0, 100), board("B", 100, 100)]
    box = height_box(boards, 200)
    rules, _ = follow_rules(box, boards)
    assert check_resize(box, FurnitureBox(600, 400, 600), boards, rules, []) == ()  # 300 + 300
    with pytest.raises(FurnitureError, match="trop grande"):
        check_resize(box, FurnitureBox(600, 400, 602), boards, rules, [])


def test_cote_nulle_ou_negative_refusee() -> None:
    boards = [board("A", 0, 22)]
    box = height_box(boards, 22)
    rules, _ = follow_rules(box, boards)
    for value in (0.0, -5.0):
        with pytest.raises(FurnitureError):
            check_resize(box, FurnitureBox(600, 400, value), boards, rules, [])


def test_rangee_sur_x_avec_piece_tournee() -> None:
    """Deux joues debout (épaisseur sur X, tournées de 90°) qui remplissent la largeur
    de l'ensemble : elles suivent au prorata sur X."""
    left = Member(
        "G", block=placed((720.0, 400.0, 20.0), (20.0, 0.0, 0.0), TURN_Y_MINUS_90), label="G"
    )
    right = Member(
        "D", block=placed((720.0, 400.0, 30.0), (50.0, 0.0, 0.0), TURN_Y_MINUS_90), label="D"
    )
    boards = [left, right]
    box = FurnitureBox(50, 400, 720)
    boards = list(with_default_options(box, boards))
    rules, _ = follow_rules(box, boards)
    new = FurnitureBox(100, 400, 720)
    got = followed_thicknesses(box, new, boards, rules)
    assert got == pytest.approx({"G": 40.0, "D": 60.0})
    assert check_resize(box, new, boards, rules, []) == ()


def test_le_passage_d_une_autre_cote_ne_touche_pas_aux_couches() -> None:
    boards = [board("A", 0, 22), board("B", 22, 18)]
    box = height_box(boards, 40)
    rules, _ = follow_rules(box, boards)
    assert followed_thicknesses(box, FurnitureBox(800, 500, 40), boards, rules) == {}


def test_rangee_sur_y_avec_piece_tournee() -> None:
    """Deux planches debout (épaisseur sur -Y) qui remplissent la profondeur."""
    front = Member(
        "F", block=placed((600.0, 400.0, 20.0), (0.0, 20.0, 0.0), TURN_X_PLUS_90), label="F"
    )
    back = Member(
        "R", block=placed((600.0, 400.0, 30.0), (0.0, 50.0, 0.0), TURN_X_PLUS_90), label="R"
    )
    box = FurnitureBox(600, 50, 400)
    boards = list(with_default_options(box, [front, back]))
    rules, _ = follow_rules(box, boards)
    new = FurnitureBox(600, 100, 400)
    got = followed_thicknesses(box, new, boards, rules)
    assert got == pytest.approx({"F": 40.0, "R": 60.0})
