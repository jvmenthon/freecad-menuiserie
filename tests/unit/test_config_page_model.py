# SPDX-License-Identifier: LGPL-2.1-or-later
"""Logique de la page de préférences ``kit/config.page_model`` (ADR 0069), sans Qt."""

from __future__ import annotations

import pytest

from freecad.menuiserie.kit.config.catalog import Catalog, Kind, Setting
from freecad.menuiserie.kit.config.page_model import (
    PAGE_TEXTS,
    count_modified,
    format_value,
    group_summary,
    is_shown,
    matches,
    normalize,
    shown_keys,
)
from tests.unit.aides_config import length_setting

EXPERT = Setting("Expert", Kind.INT, 1, "Réglage fin", "Pour les experts.", "Avancé", advanced=True)


def _catalog() -> Catalog:
    return Catalog([length_setting(), EXPERT])


def test_normalisation_sans_accent_ni_majuscule() -> None:
    assert normalize("Épaisseur Ça") == "epaisseur ca"


@pytest.mark.parametrize(
    ("query", "found"),
    [("", True), ("jeu", True), ("JEU usinage", True), ("usinage jeu", True), ("tenon", False)],
)
def test_recherche_sur_libelle_et_infobulle(query: str, found: bool) -> None:
    assert matches(length_setting(), query) is found  # « usinage » est dans l'infobulle


def test_recherche_sur_le_texte_traduit() -> None:
    def english(text: str) -> str:
        return {"Jeu": "Clearance", "Jeu d'usinage.": "Machining play."}.get(text, text)

    assert matches(length_setting(), "clearance play", english)
    assert not matches(length_setting(), "usinage", english)  # seul le texte traduit compte


def test_les_reglages_avances_sont_caches_sauf_demande() -> None:
    catalog = _catalog()
    assert shown_keys(catalog, "", advanced=False) == ["Jeu"]
    assert shown_keys(catalog, "", advanced=True) == ["Jeu", "Expert"]
    assert not is_shown(EXPERT, "experts", advanced=False)
    assert is_shown(EXPERT, "experts", advanced=True)
    assert shown_keys(catalog, "inconnu", advanced=True) == []


def test_comptes_des_reglages_modifies() -> None:
    catalog = _catalog()
    assert count_modified(catalog, {"Jeu": 2.0, "Expert": 1}, ["Jeu", "Expert"]) == 0
    assert count_modified(catalog, {"Jeu": 3.0, "Expert": 2}, ["Jeu", "Expert"]) == 2
    assert count_modified(catalog, {"Jeu": 3.0, "Expert": 2}, ["Jeu"]) == 1


@pytest.mark.parametrize(
    ("total", "modified", "text"),
    [
        (0, 0, "(0 réglage)"),
        (1, 0, "(1 réglage)"),
        (2, 0, "(2 réglages)"),
        (10, 1, "(10 réglages, 1 modifié)"),
        (10, 2, "(10 réglages, 2 modifiés)"),
    ],
)
def test_resume_d_un_groupe_replie(total: int, modified: int, text: str) -> None:
    assert group_summary(total, modified) == text


def test_valeurs_affichees() -> None:
    jeu = length_setting()
    assert format_value(jeu, 2.0) == "2 mm"
    assert format_value(jeu, 2.5) == "2.5 mm"
    flag = Setting("Cle", Kind.BOOL, False, "L", "T", "G")
    assert format_value(flag, True) == "oui"
    assert format_value(flag, False) == "non"
    text = Setting("Mat", Kind.TEXT, "", "L", "T", "G")
    assert format_value(text, "") == "vide"
    assert format_value(text, "", choices=[("", "Premier de la liste")]) == "Premier de la liste"
    assert format_value(text, "chene", choices=[("chene", "Chêne")]) == "Chêne"


def test_textes_de_la_page_distincts_et_non_vides() -> None:
    assert len(set(PAGE_TEXTS)) == len(PAGE_TEXTS)
    assert all(text.strip() for text in PAGE_TEXTS)
