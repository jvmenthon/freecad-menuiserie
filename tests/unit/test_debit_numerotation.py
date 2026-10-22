# SPDX-License-Identifier: LGPL-2.1-or-later
"""Numérotation automatique des repères, logique pure (J2e, critère N1)."""

from __future__ import annotations

from freecad.menuiserie.core.cutlist import CutEntry, assign_marks, group_key
from tests.unit.aides_debit import entry


def named(entries: list[CutEntry], prefix: str = "M", used: tuple[str, ...] = ()) -> list[str]:
    """Repères attribués, dans l'ordre des entrées sans repère (un par entrée)."""
    plan = assign_marks(entries, prefix, used)
    return [plan[group_key(item)] for item in entries if group_key(item) in plan]


def sized(length: float, mark: str = "", furniture: str = "") -> CutEntry:
    return entry(mark, (length, 100.0, 22.0), furniture=furniture)


def test_un_repere_par_groupe_et_pieces_identiques_partagent_le_leur() -> None:
    entries = [sized(500), sized(800), sized(500), sized(800), sized(300)]
    plan = assign_marks(entries)
    assert len(plan) == 3
    assert plan[group_key(entries[0])] == plan[group_key(entries[2])]
    assert sorted(plan.values()) == ["M1", "M2", "M3"]


def test_cotes_decroissantes() -> None:
    entries = [sized(300), sized(800), sized(500)]
    assert named(entries) == ["M3", "M1", "M2"]


def test_ensemble_puis_cotes_decroissantes() -> None:
    entries = [
        sized(900, furniture="Caisson 10"),
        sized(100, furniture="Caisson 2"),
        sized(700, furniture="Caisson 2"),
        sized(950),
    ]
    plan = assign_marks(entries)
    by_length = {item.record.finished.length: plan[group_key(item)] for item in entries}
    assert by_length == {700.0: "M1", 100.0: "M2", 900.0: "M3", 950.0: "M4"}


def test_les_reperes_m_n_existants_sont_sautes() -> None:
    entries = [sized(100, "M1"), sized(200, "M3"), sized(300), sized(400), sized(500)]
    assert named(entries) == ["M5", "M4", "M2"]  # cotes décroissantes : 500, 400, 300


def test_les_pieces_deja_reperees_ne_changent_pas() -> None:
    entries = [sized(100, "A"), sized(200, "M1"), sized(300)]
    plan = assign_marks(entries)
    assert list(plan.values()) == ["M2"]
    assert group_key(entries[0]) not in plan
    assert group_key(entries[1]) not in plan


def test_seuls_les_reperes_de_la_forme_prefixe_chiffres_comptent() -> None:
    entries = [sized(100, "M1a"), sized(110, "m2"), sized(120, "M"), sized(130, "M-3"), sized(300)]
    assert named(entries) == ["M1"]


def test_reperes_exterieurs_a_ignorer() -> None:
    assert named([sized(300)], used=("M1", "M2", "Z")) == ["M3"]


def test_prefixe_personnalise() -> None:
    entries = [sized(100, "P1"), sized(200, "M1"), sized(300), sized(400)]
    assert named(entries, "P") == ["P3", "P2"]
    assert named([sized(300)], "A.") == ["A.1"]


def test_aucune_entree_ou_tout_repere() -> None:
    assert assign_marks([]) == {}
    assert assign_marks([sized(100, "M1")]) == {}


def test_ne_modifie_rien_et_est_deterministe() -> None:
    entries = [sized(100), sized(200)]
    first = dict(assign_marks(entries))
    assert first == dict(assign_marks(reversed(entries)))
    assert [item.record.mark for item in entries] == ["", ""]


def test_ordre_sans_ensemble_apres_les_ensembles() -> None:
    entries = [sized(900), sized(100, furniture="B")]
    plan = assign_marks(entries)
    assert plan[group_key(entries[1])] == "M1"
    assert plan[group_key(entries[0])] == "M2"


def test_groupe_sur_plusieurs_ensembles_ordonne_par_le_premier() -> None:
    entries = [
        sized(300, furniture="B"),
        sized(300, furniture="A"),
        sized(500, furniture="A2"),
    ]
    plan = assign_marks(entries)
    assert len(plan) == 2
    assert plan[group_key(entries[0])] == "M1"
    assert plan[group_key(entries[2])] == "M2"
