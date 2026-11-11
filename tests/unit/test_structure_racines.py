# SPDX-License-Identifier: LGPL-2.1-or-later
"""Racines du panneau « Structure » avec un cycle de sous-ensembles (S1 de la revue)."""

from __future__ import annotations

from collections.abc import Callable

from freecad.menuiserie.core.structure_roots import with_cycle_entries


def subs_of(graph: dict[str, list[str]]) -> Callable[[str], list[str]]:
    def subs(key: str) -> list[str]:
        return graph.get(key, [])

    return subs


def test_sans_cycle_les_racines_sont_inchangees() -> None:
    graph = {"A": ["B"], "B": []}
    assert with_cycle_entries(["A"], ["A", "B"], subs_of(graph)) == ["A"]


def test_cycle_sans_racine_entre_par_le_premier_ensemble() -> None:
    graph = {"A": ["B"], "B": ["A"]}  # chacun membre de l'autre : aucune racine
    assert with_cycle_entries([], ["A", "B"], subs_of(graph)) == ["A"]


def test_cycle_a_cote_d_une_racine_normale() -> None:
    graph = {"R": [], "A": ["B"], "B": ["A"]}
    assert with_cycle_entries(["R"], ["R", "A", "B"], subs_of(graph)) == ["R", "A"]


def test_deux_cycles_independants() -> None:
    graph = {"A": ["B"], "B": ["A"], "C": ["D"], "D": ["C"]}
    assert with_cycle_entries([], ["A", "B", "C", "D"], subs_of(graph)) == ["A", "C"]


def test_noeud_d_un_cycle_atteint_depuis_une_racine_n_est_pas_ajoute() -> None:
    graph = {"R": ["A"], "A": ["B"], "B": ["A"]}
    assert with_cycle_entries(["R"], ["R", "A", "B"], subs_of(graph)) == ["R"]
