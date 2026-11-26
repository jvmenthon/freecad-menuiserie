# SPDX-License-Identifier: LGPL-2.1-or-later
"""Cartouche du plan : cases du gabarit remplies (issue #153, ADR 0053, lot P-b)."""

from __future__ import annotations

from freecad.menuiserie.core.drawing import (
    MAX_FIELD_LENGTH,
    TitleFields,
    clean_field,
    placeholder_keys,
    title_block_texts,
)

FIELDS = TitleFields(
    title="Bureau",
    material="Chêne",
    scale="1 : 10",
    date="2026-11-12",
    author="jv",
    client="Mme Dupont",
    quote="D-14",
)


def test_cases_connues_remplies() -> None:
    keys = ["drawing_title", "scale", "date", "author_name", "part_material", "sheet_number"]
    assert title_block_texts(keys, FIELDS) == {
        "drawing_title": "Bureau - Mme Dupont",  # pas de case client
        "scale": "1 : 10",
        "date": "2026-11-12",
        "author_name": "jv",
        "part_material": "Chêne",
    }


def test_nom_exact_du_gabarit_et_ordre_de_preference() -> None:
    texts = title_block_texts(["Title", "DRAWING_TITLE", "Client", "Drawing_Number"], FIELDS)
    assert texts == {"DRAWING_TITLE": "Bureau", "Client": "Mme Dupont", "Drawing_Number": "D-14"}


def test_champ_facultatif_vide_vide_sa_case() -> None:
    empty = TitleFields(title="Bureau")
    assert title_block_texts(["client", "quote", "freecad"], empty) == {"client": "", "quote": ""}


def test_gabarit_sans_case_connue() -> None:
    assert not title_block_texts(["a", "b"], FIELDS)
    assert not title_block_texts([], FIELDS)


def test_texte_nettoye() -> None:
    assert clean_field("  Bureau\n de\tLéa ‮ ") == "Bureau de Léa"
    assert len(clean_field("x" * 500)) == MAX_FIELD_LENGTH
    assert title_block_texts(["title"], TitleFields(title="A\x00B\nC")) == {"title": "A B C"}


def test_client_apres_le_titre_sans_case_client() -> None:
    texts = title_block_texts(["drawing_title", "scale"], FIELDS)
    assert texts["drawing_title"] == "Bureau - Mme Dupont"
    alone = title_block_texts(["drawing_title"], TitleFields(title="Bureau"))
    assert alone == {"drawing_title": "Bureau"}


def test_cases_du_gabarit_de_freecad_1_1() -> None:
    """Gabarit ISO 7200 de TechDraw 1.1 : cases aux noms allemands, sans case matériau."""
    keys = ["Genehmiger", "Sachnummer", "author_name", "document_type", "drawing_title"]
    keys += ["fc-date", "fc-sc", "owner_1", "page_number", "projekt"]
    values = TitleFields(
        title="Bureau", material="Chêne", kind="Plan de l'ouvrage", scale="1 : 10", client="X"
    )
    texts = title_block_texts(keys, values)
    assert texts["drawing_title"] == "Bureau"
    assert texts["owner_1"] == "X"
    assert texts["document_type"] == "Plan de l'ouvrage - Chêne"
    assert texts["fc-sc"] == "1 : 10"
    assert texts["Sachnummer"] == ""


def test_exemples_du_gabarit_effaces() -> None:
    current = {"Genehmiger": "Genehmiger", "projekt": "Projekt", "page_number": "1 / 1"}
    current["fc-sc"] = "fc-sc"
    assert placeholder_keys(current, ["fc-sc"]) == ["Genehmiger", "projekt"]
