# SPDX-License-Identifier: LGPL-2.1-or-later
"""Nom de la pièce = repère, règles pures de ``core/naming.py`` (critères L1 et L2 de J6b)."""

from __future__ import annotations

import pytest

from freecad.menuiserie.core.naming import DUPLICATE_SUFFIX, label_for_mark, mark_from_label

DEFAULT = "Pièce de bois"


# --- L1 : label_for_mark ------------------------------------------------------------------


def test_repere_libre_devient_le_libelle() -> None:
    assert label_for_mark("M1", DEFAULT, set()) == "M1"
    assert label_for_mark("M1", DEFAULT, {"M2", DEFAULT}) == "M1"


def test_repere_pris_recoit_le_premier_suffixe_libre() -> None:
    assert label_for_mark("M1", DEFAULT, {"M1"}) == "M1 (2)"
    assert label_for_mark("M1", DEFAULT, {"M1", "M1 (2)"}) == "M1 (3)"
    # le premier libre, même s'il y a un trou
    assert label_for_mark("M1", DEFAULT, {"M1", "M1 (2)", "M1 (4)"}) == "M1 (3)"
    assert label_for_mark("M1", DEFAULT, {"M1 (2)"}) == "M1"


@pytest.mark.parametrize("mark", ["", " ", "   ", "\t"])
def test_repere_vide_donne_le_libelle_par_defaut(mark: str) -> None:
    assert label_for_mark(mark, DEFAULT, set()) == DEFAULT
    assert label_for_mark(mark, DEFAULT, {DEFAULT}) == f"{DEFAULT} (2)"
    assert label_for_mark(mark, DEFAULT, {DEFAULT, f"{DEFAULT} (2)"}) == f"{DEFAULT} (3)"


def test_texte_du_repere_garde_tel_quel() -> None:
    assert label_for_mark("  M1 ", DEFAULT, set()) == "  M1 "
    assert label_for_mark("  M1 ", DEFAULT, {"  M1 "}) == "  M1  (2)"
    assert label_for_mark("Joue « é »", DEFAULT, set()) == "Joue « é »"


def test_collection_taken_non_modifiee() -> None:
    taken = {"M1"}
    label_for_mark("M1", DEFAULT, taken)
    assert taken == {"M1"}


def test_suffixe_de_doublon_documente() -> None:
    assert DUPLICATE_SUFFIX.format(n=2) == " (2)"


# --- L2 : mark_from_label -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("label", "mark"),
    [
        ("M1", "M1"),
        ("M1 (2)", "M1"),
        ("M1 (3)", "M1"),
        ("M1 (12)", "M1"),
        ("Joue gauche (2)", "Joue gauche"),
        ("M1 (1)", "M1 (1)"),  # n ≥ 2 seulement
        ("M1 (02)", "M1 (02)"),
        ("M1 (2) (3)", "M1 (2)"),  # un seul suffixe est retiré
        ("M1(2)", "M1(2)"),
        ("(2)", "(2)"),
        ("M1 (2) ", "M1 (2) "),
    ],
)
def test_suffixe_final_retire(label: str, mark: str) -> None:
    assert mark_from_label(label, DEFAULT) == mark


@pytest.mark.parametrize(
    "label", [DEFAULT, f"{DEFAULT} (2)", f"{DEFAULT} (7)", "", "  ", " (2)", "\t"]
)
def test_libelle_par_defaut_ou_vide_donne_repere_vide(label: str) -> None:
    assert mark_from_label(label, DEFAULT) == ""


TAKEN_SAMPLES: tuple[set[str], ...] = (
    set(),
    {"M1", "M1 (2)", DEFAULT, f"{DEFAULT} (2)", "Joue gauche", "E2"},
)


@pytest.mark.parametrize("mark", ["M1", "Joue gauche", "  M1 ", "E2 « é »", "A"])
@pytest.mark.parametrize("taken", TAKEN_SAMPLES, ids=["vide", "plein"])
def test_aller_retour_repere_non_vide(mark: str, taken: set[str]) -> None:
    label = label_for_mark(mark, DEFAULT, taken)
    assert mark_from_label(label, DEFAULT) == mark


@pytest.mark.parametrize("mark", ["", "  "])
@pytest.mark.parametrize("taken", TAKEN_SAMPLES, ids=["vide", "plein"])
def test_aller_retour_repere_vide(mark: str, taken: set[str]) -> None:
    label = label_for_mark(mark, DEFAULT, taken)
    assert mark_from_label(label, DEFAULT) == ""


def test_repere_egal_au_libelle_par_defaut_redevient_vide() -> None:
    """Limite documentée : « Pièce de bois » saisi comme repère se lit comme « pas de repère »."""
    label = label_for_mark(DEFAULT, DEFAULT, set())
    assert mark_from_label(label, DEFAULT) == ""


def test_repere_qui_finit_par_un_suffixe_perd_ce_suffixe() -> None:
    """Limite documentée : « A (2) » saisi dans l'arborescence devient « A »."""
    label = label_for_mark("A (2)", DEFAULT, set())
    assert label == "A (2)"
    assert mark_from_label(label, DEFAULT) == "A"


def test_renommer_un_doublon_en_son_repere_garde_le_libelle() -> None:
    """L5 : saisir « M1 » pour la pièce « M1 (2) » (« M1 » étant prise) redonne « M1 (2) »."""
    typed = "M1"
    mark = mark_from_label(typed, DEFAULT)
    assert mark == "M1"
    assert label_for_mark(mark, DEFAULT, {"M1"}) == "M1 (2)"
