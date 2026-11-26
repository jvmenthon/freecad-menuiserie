# SPDX-License-Identifier: LGPL-2.1-or-later
"""Lignes de l'aperçu d'un import et sélection, ``kit/config.import_model`` (ADR 0069), sans Qt."""

from __future__ import annotations

import pytest

from freecad.menuiserie.kit.config.exchange import Change
from freecad.menuiserie.kit.config.import_model import (
    IMPORT_TEXTS,
    MAX_NAMES_SHOWN,
    ImportOffer,
    ImportRow,
    build_rows,
    changes_header,
    chosen,
    chosen_values,
    ignored_text,
)
from tests.unit.aides_config import sample_catalog

CHANGES = [
    Change("Jeu", 2.0, 1.5),
    Change("JeuRememberLast", False, True),
    Change("Debouchant", False, True),
    Change("Profil", "Round", "Chamfer"),
]


def test_lignes_de_l_apercu_dans_l_ordre_des_changements() -> None:
    rows = build_rows(sample_catalog(), CHANGES)
    assert [row.key for row in rows] == ["Jeu", "JeuRememberLast", "Debouchant", "Profil"]
    jeu = rows[0]
    assert (jeu.group, jeu.label, jeu.current, jeu.imported) == (
        "Assemblages",
        "Jeu",
        "2 mm",
        "1.5 mm",
    )
    assert jeu.value == 1.5


def test_case_dernier_utilise_est_une_ligne_a_part() -> None:
    row = build_rows(sample_catalog(), CHANGES)[1]
    assert row.label == "Jeu (Dernier utilisé)"
    assert (row.current, row.imported, row.value) == ("non", "oui", True)


def test_lignes_traduites_et_choix_nommes() -> None:
    def english(text: str) -> str:
        return {"Jeu": "Clearance", "Assemblages": "Joints", "oui": "yes"}.get(text, text)

    choices = {"Profil": [("Chamfer", "Chanfrein"), ("Round", "Arrondi")]}
    rows = build_rows(sample_catalog(), CHANGES, english, choices)
    assert (rows[0].group, rows[0].label) == ("Joints", "Clearance")
    assert rows[2].imported == "yes"
    assert (rows[3].current, rows[3].imported) == ("Arrondi", "Chanfrein")


@pytest.mark.parametrize(
    ("count", "text"),
    [
        (0, "Fichier : a.json · 0 réglage changé"),
        (1, "Fichier : a.json · 1 réglage changé"),
        (5, "Fichier : a.json · 5 réglages changés"),
    ],
)
def test_en_tete_de_l_apercu(count: int, text: str) -> None:
    assert changes_header("a.json", count) == text


def test_bandeau_des_elements_ignores() -> None:
    assert ignored_text([]) == ""
    assert ignored_text(["Palette"]) == "1 réglage inconnu ignoré : « Palette »."
    assert ignored_text(["A", "B"]) == "2 réglages inconnus ignorés : « A », « B »."


def test_bandeau_limite_les_noms_cites() -> None:
    names = [f"K{index}" for index in range(MAX_NAMES_SHOWN + 3)]
    text = ignored_text(names)
    assert text.startswith(f"{len(names)} réglages inconnus ignorés : « K0 »")
    assert text.endswith(", ….")
    assert f"K{MAX_NAMES_SHOWN}" not in text


def test_selection_des_lignes_cochees() -> None:
    rows = build_rows(sample_catalog(), CHANGES)
    assert [row.key for row in chosen(rows, {"Profil", "Jeu"})] == ["Jeu", "Profil"]
    assert chosen(rows, set()) == []
    assert chosen_values(rows, ["Jeu", "JeuRememberLast"]) == {"Jeu": 1.5, "JeuRememberLast": True}


def test_offre_vide_par_defaut() -> None:
    assert ImportOffer() == ImportOffer((), ())
    assert ImportRow("k", "g", "l", "a", "b", 1).value == 1


def test_textes_distincts_et_non_vides() -> None:
    assert len(set(IMPORT_TEXTS)) == len(IMPORT_TEXTS)
    assert all(text.strip() for text in IMPORT_TEXTS)
