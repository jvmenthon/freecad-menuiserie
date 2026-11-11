# SPDX-License-Identifier: LGPL-2.1-or-later
"""Critère de l'assemblage vers l'extérieur : les deux pièces gardent le même Std Part."""

from __future__ import annotations

import pytest

from freecad.menuiserie.core.assembly_scope import destination, keeps_assembly


@pytest.mark.parametrize(
    ("moved", "other", "expected"),
    [
        (["A"], ["A"], True),  # même ensemble
        (["S", "A"], ["S", "A"], True),  # même sous-ensemble
        (["S", "A"], ["A"], False),  # sous-ensemble de l'ensemble de l'autre : Q serait emportée
        (["A"], ["S", "A"], False),  # ensemble parent de celui de l'autre : idem
        (["B"], ["A"], False),  # ensembles différents
        (["B"], [], False),  # l'autre est hors ensemble
        ([], ["A"], False),  # la pièce sort, l'autre reste
        ([], [], True),  # toutes deux hors ensemble
    ],
)
def test_assemblage_garde_ou_non_le_meme_std_part(
    moved: list[str], other: list[str], expected: bool
) -> None:
    assert keeps_assembly(moved, other) is expected


@pytest.mark.parametrize(
    ("wanted", "others", "expected"),
    [
        (["S", "A"], [["A"]], ("A",)),  # sous-ensemble de l'ensemble de l'autre : dans cet ensemble
        (["A"], [["S", "A"]], ("S", "A")),  # ensemble parent : dans le sous-ensemble de l'autre
        (["S", "A"], [["S", "A"]], ("S", "A")),  # déjà ensemble : inchangé
        (["B"], [["A"]], None),  # branches différentes : aucun rangement cohérent
        ([], [["A"]], None),  # sortir alors que l'autre reste
        (["B"], [[]], ()),  # l'autre est hors ensemble : hors ensemble
        (["S", "A"], [["A"], ["B"]], None),  # deux exigences qui se contredisent
        (["S", "A"], [["A"], ["A"]], ("A",)),
    ],
)
def test_destination(
    wanted: list[str], others: list[list[str]], expected: tuple[str, ...] | None
) -> None:
    assert destination(wanted, others) == expected


def test_destination_ignore_les_pieces_libres_a_la_demande() -> None:
    assert destination(["A"], [[]], ignore_free=True) == ("A",)
