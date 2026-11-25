# SPDX-License-Identifier: LGPL-2.1-or-later
"""Noms automatiques des copies d'une répétition, « Barreau (2) » (ADR 0067), sans FreeCAD."""

from __future__ import annotations

import pytest

from freecad.menuiserie.core.repeat import copy_name, is_copy_name


@pytest.mark.parametrize(
    ("source", "rank", "expected"),
    [
        ("Barreau", 0, "Barreau (1)"),
        ("Barreau", 1, "Barreau (2)"),
        ("Barreau", 99, "Barreau (100)"),
        ("Côté gauche", 2, "Côté gauche (3)"),
        ("Montant (2)", 1, "Montant (2) (2)"),  # source déjà numérotée : le suffixe s'ajoute
    ],
)
def test_nom_automatique(source: str, rank: int, expected: str) -> None:
    assert copy_name(source, rank) == expected


@pytest.mark.parametrize("rank", [0, 1, 7])
def test_le_nom_actuel_et_l_ancien_sont_reconnus(rank: int) -> None:
    assert is_copy_name(copy_name("Barreau", rank), "Barreau", rank)
    assert is_copy_name(f"Barreau {rank + 1}", "Barreau", rank)


@pytest.mark.parametrize(
    "label",
    [
        "Barreau (3)",  # le rang d'une autre copie
        "Barreau 3",
        "barreau (2)",  # la casse compte
        "Barreau (2) ",
        " Barreau (2)",
        "Barreau (2)(2)",
        "Barreau",
        "Autre (2)",
        "",
    ],
)
def test_un_autre_nom_n_est_pas_automatique(label: str) -> None:
    assert not is_copy_name(label, "Barreau", 1)


def test_un_nom_change_a_la_main_n_est_jamais_renomme() -> None:
    assert not is_copy_name("Barreau du fond", "Barreau", 1)
    assert not is_copy_name("Barreau (2) du fond", "Barreau", 1)
