# SPDX-License-Identifier: LGPL-2.1-or-later
"""Export HTML de la liste de débit (J2e, critère P1)."""

from __future__ import annotations

import re
from html.parser import HTMLParser

import pytest

from freecad.menuiserie.core.cutlist import (
    CutList,
    Hardware,
    HardwareKind,
    build_cut_list,
    to_html,
)
from tests.unit.aides_debit import entry, plywood


class Collector(HTMLParser):
    """Balises, attributs et cellules d'un document HTML."""

    def __init__(self) -> None:
        super().__init__()
        self.tags: list[str] = []
        self.attributes: list[tuple[str, str | None]] = []
        self.cells: list[str] = []
        self._cell = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags.append(tag)
        self.attributes.extend(attrs)
        self._cell = tag in ("td", "th")

    def handle_endtag(self, tag: str) -> None:
        self._cell = False

    def handle_data(self, data: str) -> None:
        if self._cell:
            self.cells.append(data)


def parse(text: str) -> Collector:
    collector = Collector()
    collector.feed(text)
    return collector


def sample() -> CutList:
    entries = [
        entry("M10", (1200, 95.5, 22), quantity=2, furniture="Caisson"),
        entry("M2", (800, 100, 22.5)),
        entry("", (300, 50, 20)),
        plywood(),
    ]
    return build_cut_list(entries, [Hardware(HardwareKind.DOWEL, 8.0, 35.0, 6)])


def test_document_autonome_avec_titre_date_et_portee() -> None:
    text = to_html(sample(), title="Liste de débit", scope="Tout le document", date="2026-10-22")
    assert text.startswith("<!DOCTYPE html>")
    assert "<title>Liste de débit</title>" in text
    assert "<h1>Liste de débit</h1>" in text
    assert "Date : 2026-10-22" in text
    assert "Portée : Tout le document" in text
    assert "A4 landscape" in text


def test_tableau_memes_colonnes_que_la_feuille_en_format_international() -> None:
    cells = parse(to_html(sample(), title="T")).cells
    assert cells[:3] == ["Repère", "Qté", "Longueur finie (mm)"]
    assert cells[:15].count("Remarque") == 1
    assert "M2" in cells
    assert "100.5" in cells  # largeur de débit de M10 : point décimal
    assert "22.5" in cells
    assert not any("," in cell and cell.replace(",", "").isdigit() for cell in cells)
    assert "—" in cells  # pièce sans repère


def test_totaux_fournitures_et_avertissements() -> None:
    text = to_html(sample(), title="T")
    for expected in ("Totaux par matériau", "Total général", "Fournitures", "Tourillon"):
        assert expected in text
    assert "<h2>Avertissements</h2>" in text
    assert "<li>1 pièce(s) sans repère, regroupées par cotes.</li>" in text


def test_sans_avertissement_ni_fourniture() -> None:
    text = to_html(build_cut_list([entry()]), title="T")
    assert "Avertissements" not in text
    assert "Fournitures" not in text


def test_liste_vide() -> None:
    text = to_html(build_cut_list([]))
    assert "<table>" in text
    assert "Total général" not in text
    assert "<h1></h1>" in text


def test_sans_date_ni_portee() -> None:
    text = to_html(sample(), title="T")
    assert "Date :" not in text
    assert "Portée :" not in text
    assert 'class="meta"' not in text


def test_libelles_traduits() -> None:
    text = to_html(sample(), lambda s: f"<{s}>", "T", "S", "D")
    assert "&lt;Repère&gt;" in text
    assert "&lt;Date&gt; : D" in text
    assert "&lt;Portée&gt; : S" in text
    assert "&lt;Avertissements&gt;" in text
    assert "<Repère>" not in text


HOSTILE = '<script>alert("x")</script> & "q" \'s\' <img src=x onerror=y>'


def test_tout_texte_est_echappe() -> None:
    evil = build_cut_list([entry(HOSTILE, furniture=HOSTILE)])
    text = to_html(evil, lambda s: s, HOSTILE, HOSTILE, HOSTILE)
    assert "<script" not in text
    assert "<img" not in text
    assert HOSTILE not in text
    assert "&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt; &amp; &quot;q&quot;" in text
    collected = parse(text)
    assert "script" not in collected.tags
    assert "img" not in collected.tags
    assert not [name for name, _ in collected.attributes if name.startswith("on")]


def test_avertissement_echappe() -> None:
    evil = build_cut_list([entry("<b>"), entry("<b>", (1, 50, 20))])
    text = to_html(evil)
    assert "<b>" not in text
    assert "Repère &lt;b&gt; utilisé pour des pièces différentes." in text


def test_ni_script_ni_ressource_externe() -> None:
    text = to_html(sample(), title="T", scope="S", date="D")
    tags = set(parse(text).tags)
    assert tags <= {"html", "head", "meta", "title", "style", "body", "h1", "h2", "p", "table"} | {
        "thead",
        "tbody",
        "tr",
        "th",
        "td",
        "ul",
        "li",
    }
    assert not re.search(r"https?:|//|url\(|@import|<link|<script|<iframe|src=|href=", text)
    assert "javascript" not in text.lower()


@pytest.mark.parametrize("marker", ['class="num"', "<thead>", "<tbody>"])
def test_structure_du_tableau(marker: str) -> None:
    assert marker in to_html(sample(), title="T")
