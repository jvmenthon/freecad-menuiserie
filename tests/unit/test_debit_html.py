# SPDX-License-Identifier: LGPL-2.1-or-later
"""Export HTML de la liste de débit (J2e, critère P1)."""

from __future__ import annotations

import base64
import re
from dataclasses import replace
from html.parser import HTMLParser

import pytest

from freecad.menuiserie.core.cutlist import (
    CutEntry,
    CutList,
    Hardware,
    HardwareKind,
    box_faces,
    build_cut_list,
    thumbnail_svg,
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
    titles = ("Totaux par matériau et épaisseur", "Total général", "Fournitures", "Tourillon")
    for expected in titles:
        assert expected in text
    assert "<h2>Avertissements</h2>" in text
    assert "<li>1 pièce(s) sans repère, regroupées par cotes.</li>" in text


def test_sans_avertissement_ni_fourniture() -> None:
    text = to_html(build_cut_list([entry()]), title="T")
    assert "Avertissements" not in text
    assert "Fournitures" not in text


def test_liste_vide() -> None:
    text = to_html(build_cut_list([]))
    assert "<table " in text
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


# --- Miniatures (demande de jv du 2026-10-22, critères A2 et A4) -------------------------------


def sourced(mark: str, source: str, size: tuple[float, float, float]) -> CutEntry:
    return replace(entry(mark, size), source=source)


def two_lines() -> CutList:
    return build_cut_list(
        [sourced("M1", "Part", (800, 100, 22)), sourced("M2", "Part2", (500, 90, 18))]
    )


def svg_of(width: float) -> str:
    return thumbnail_svg(box_faces(width, 50, 20))


def test_sans_miniatures_le_document_est_inchange() -> None:
    cut_list = two_lines()
    reference = to_html(cut_list, title="T")
    assert to_html(cut_list, title="T", thumbnails=None) == reference
    assert to_html(cut_list, title="T", thumbnails={}) == reference
    assert "Miniature" not in reference
    assert "<img" not in reference


def test_colonne_miniature_en_tete_de_chaque_ligne() -> None:
    thumbs = {"Part": svg_of(800), "Part2": svg_of(500)}
    text = to_html(two_lines(), title="T", thumbnails=thumbs)
    cells = parse(text).cells
    assert cells[:3] == ["Miniature", "Repère", "Qté"]
    assert text.count("<img ") == 2
    assert text.count('class="thumb"') == 2
    first_row = text.split("<tbody>")[1].split("</tr>")[0]
    assert first_row.startswith('<tr><td class="thumb"><img ')
    assert 'width="120" height="80"' in first_row


def test_miniature_en_data_uri_et_aucune_url_externe() -> None:
    text = to_html(two_lines(), title="T", thumbnails={"Part": svg_of(800)})
    sources = [value for name, value in parse(text).attributes if name == "src"]
    assert len(sources) == 1
    assert sources[0] is not None
    assert sources[0].startswith("data:image/svg+xml;base64,")
    assert base64.b64decode(sources[0].split(",", 1)[1]).decode() == svg_of(800)
    assert not re.search(r"(?i)(https?:|file:|ftp:|@import|url\()", text)
    assert "<script" not in text


def test_ligne_sans_miniature_a_une_cellule_vide() -> None:
    text = to_html(two_lines(), title="T", thumbnails={"Part": svg_of(800)})
    assert text.count("<img ") == 1
    assert text.count('<td class="thumb"></td>') == 1


def test_les_autres_tableaux_n_ont_pas_de_colonne_miniature() -> None:
    cut_list = build_cut_list(
        [sourced("M1", "a", (800, 100, 22))], [Hardware(HardwareKind.DOWEL, 8.0, 35.0, 6)]
    )
    text = to_html(cut_list, title="T", thumbnails={"a": svg_of(800)})
    assert text.count("Miniature") == 1
    assert text.count("<img ") == 1


def test_une_miniature_qui_n_est_pas_un_svg_est_refusee() -> None:
    with pytest.raises(ValueError, match="SVG"):
        to_html(two_lines(), thumbnails={"Part": "<img src=x onerror=y>"})


def test_une_ligne_sur_deux_teintee_et_total_general_mis_en_avant() -> None:
    text = to_html(sample())
    lines, totals = (part.split("</tbody>")[0] for part in text.split("<tbody>")[1:3])
    assert lines.startswith("<tr><td>")  # la première ligne n'est pas teintée
    assert lines.count('<tr class="alt">') == lines.count("<tr") // 2
    assert totals.count('<tr class="total">') == 1
    assert totals.rsplit("<tr", 1)[1].startswith(' class="total"><td>Total')


def test_en_tete_des_nombres_aligne_a_droite() -> None:
    text = to_html(sample())
    assert "<th>Repère</th>" in text
    assert '<th class="num">Qté</th>' in text


def test_tableaux_sans_espacement_entre_cellules() -> None:
    text = to_html(sample())
    assert text.count('<table width="100%" cellspacing="0"') == 1  # seul le tableau des lignes
    assert text.count('cellspacing="0"') == text.count("<table ")
