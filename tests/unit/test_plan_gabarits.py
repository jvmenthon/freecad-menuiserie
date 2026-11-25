# SPDX-License-Identifier: LGPL-2.1-or-later
"""Gabarits de page de l'atelier : fichiers livrés, cases du cartouche, place réservée."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from freecad.menuiserie.core.drawing import (
    PAGE_FORMATS,
    TEMPLATE_FILES,
    Orientation,
    TitleFields,
    page_size,
    pick_template,
    template_file_name,
    template_svg,
    title_block_texts,
)
from freecad.menuiserie.core.drawing._layout import MARGIN_MM, TITLE_BLOCK_MM
from freecad.menuiserie.core.drawing._sheet import BLOCK_ROWS_MM, BLOCK_WIDTH_MM, FRAME_MM
from freecad.menuiserie.core.i18n import TemplatedError

ROOT = Path(__file__).resolve().parents[2]
FOLDER = ROOT / "freecad" / "menuiserie" / "resources" / "templates"
EDITABLE = "{http://www.freecad.org/wiki/index.php?title=Svg_Namespace}editable"


def _editables(svg: str) -> dict[str, str]:
    root = ET.fromstring(svg.encode("utf-8"))  # noqa: S314 (texte produit par l'atelier)
    return {
        text.attrib[EDITABLE]: "".join(text.itertext())
        for text in root.iter("{http://www.w3.org/2000/svg}text")
        if EDITABLE in text.attrib
    }


@pytest.mark.parametrize("name", TEMPLATE_FILES)
def test_fichier_livre_a_jour(name: str) -> None:
    fmt, orientation = name.removesuffix(".svg").split("_")[1:]
    expected = template_svg(fmt, Orientation(orientation))
    path = FOLDER / name
    assert path.is_file(), "lancer python tools/generer_gabarits.py"
    assert path.read_text(encoding="utf-8") == expected, "lancer python tools/generer_gabarits.py"


def test_un_gabarit_par_format_et_par_sens() -> None:
    assert len(TEMPLATE_FILES) == 2 * len(PAGE_FORMATS)
    assert template_file_name(" a3 ", Orientation.LANDSCAPE) == "Menuiserie_A3_Landscape.svg"
    # Le nom suffit au choix par mots du chemin.
    chosen = pick_template(
        [str(FOLDER / name) for name in TEMPLATE_FILES], "A2", Orientation.PORTRAIT
    )
    assert chosen is not None and chosen.endswith("Menuiserie_A2_Portrait.svg")


def test_dimensions_de_la_feuille() -> None:
    root = ET.fromstring(template_svg("A4", Orientation.PORTRAIT).encode("utf-8"))  # noqa: S314 (texte produit par l'atelier)
    assert root.attrib["width"] == "210mm"
    assert root.attrib["height"] == "297mm"
    assert root.attrib["viewBox"] == "0 0 210 297"


def test_toutes_les_cases_sont_remplies() -> None:
    cases = _editables(template_svg("A3", Orientation.LANDSCAPE))
    fields = TitleFields(
        title="Bureau",
        material="Chêne",
        kind="Plan de l'ouvrage",
        scale="1 : 10",
        date="2026-11-13",
        author="jv",
        client="M. Martin",
        quote="D-42",
    )
    written = title_block_texts(cases, fields)
    assert set(written) == set(cases)
    assert written["client"] == "M. Martin"
    assert written["material"] == "Chêne"
    assert written["drawing_title"] == "Bureau"  # client à sa case, pas après le titre


def test_cartouche_dans_la_place_reservee() -> None:
    # La mise en page réserve la largeur et la hauteur du cartouche plus le cadre.
    assert TITLE_BLOCK_MM[0] >= FRAME_MM + BLOCK_WIDTH_MM
    assert FRAME_MM + sum(BLOCK_ROWS_MM) <= TITLE_BLOCK_MM[1]
    assert FRAME_MM <= MARGIN_MM
    assert page_size("A4", Orientation.PORTRAIT).width >= BLOCK_WIDTH_MM + 2 * FRAME_MM


def test_libelles_en_francais_et_echappes() -> None:
    svg = template_svg("A3", Orientation.LANDSCAPE)
    for label in ("Ouvrage", "Client", "N° de devis", "Matériau", "Échelle", "Auteur"):
        assert f">{label}<" in svg
    ET.fromstring(svg.encode("utf-8"))  # noqa: S314 (XML bien formé)


def test_format_inconnu() -> None:
    with pytest.raises(TemplatedError):
        template_svg("B5", Orientation.LANDSCAPE)
