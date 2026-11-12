# SPDX-License-Identifier: LGPL-2.1-or-later
"""Cartouche du plan : cases du gabarit remplies (issue #153, ADR 0053, lot P-b)."""

from __future__ import annotations

from freecad.menuiserie.core.drawing import (
    MAX_FIELD_LENGTH,
    TitleFields,
    clean_field,
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
        "drawing_title": "Bureau",
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
