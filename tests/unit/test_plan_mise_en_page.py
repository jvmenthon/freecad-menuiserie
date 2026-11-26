# SPDX-License-Identifier: LGPL-2.1-or-later
"""Mise en page du plan de l'ouvrage et choix du gabarit (issue #153, ADR 0053, lot P-a)."""

from __future__ import annotations

import math

import pytest

from freecad.menuiserie.core.drawing import (
    SCALES,
    Orientation,
    PageSize,
    overall_layout,
    page_size,
    pick_template,
    scale_text,
)
from freecad.menuiserie.core.i18n import TemplatedError

A3 = page_size("A3")


def test_formats_et_sens() -> None:
    assert page_size("A3") == PageSize(420.0, 297.0)
    assert page_size(" a4 ", Orientation.PORTRAIT) == PageSize(210.0, 297.0)
    with pytest.raises(TemplatedError):
        page_size("B5")


@pytest.mark.parametrize(
    ("scale", "text"), [(1.0, "1 : 1"), (0.1, "1 : 10"), (0.05, "1 : 20"), (2.0, "2 : 1")]
)
def test_echelle_ecrite(scale: float, text: str) -> None:
    assert scale_text(scale) == text


def test_bureau_sur_a3_au_dixieme() -> None:
    layout = overall_layout((1200, 600, 750), A3)
    assert layout.fits
    assert layout.scale == 0.1
    # Dessus sous la face, vue de gauche à droite de la face, perspective à droite.
    assert layout.top.x == layout.front.x
    assert layout.top.y == pytest.approx(layout.front.y - 37.5 - 30 - 30)
    assert layout.side.y == layout.front.y
    assert layout.side.x == pytest.approx(layout.front.x + 60 + 30 + 30)
    assert layout.iso.x > layout.side.x + 30


def test_bureau_centre_au_dessus_du_cartouche() -> None:
    layout = overall_layout((1200, 600, 750), A3)
    iso_width = 180 / math.sqrt(2)
    left = layout.front.x - 60
    right = layout.iso.x + iso_width / 2
    assert left - 20 == pytest.approx(A3.width - 20 - right)  # autant de place à gauche qu'à droite
    top = layout.front.y + 37.5
    bottom = layout.top.y - 30
    assert A3.height - 20 - top == pytest.approx(bottom - 65)  # autant au-dessus qu'en dessous
    assert left > 20 + 1  # plus calé dans le coin haut gauche


def test_echelle_la_plus_grande_qui_tient() -> None:
    small = overall_layout((40, 20, 30), A3)
    assert small.scale == 2.0  # agrandissement d'un petit ouvrage
    tall = overall_layout((900, 400, 2200), A3)
    assert tall.fits
    larger = SCALES[SCALES.index(tall.scale) - 1]
    assert larger > tall.scale
    assert 2200 * larger + 20 + 65 > A3.height  # l'échelle au-dessus déborde en hauteur


def test_vues_dans_la_feuille() -> None:
    for sizes in ((1200, 600, 750), (600, 600, 2000), (3000, 300, 200), (10, 10, 10)):
        for page in (A3, page_size("A4"), page_size("A4", Orientation.PORTRAIT)):
            layout = overall_layout(sizes, page)
            if not layout.fits:
                continue
            width, depth, height = (value * layout.scale for value in sizes)
            assert layout.front.x - width / 2 >= 20 - 1e-9
            assert layout.front.y + height / 2 <= page.height - 20 + 1e-9
            assert layout.top.y - depth / 2 >= 20 - 1e-9
            assert layout.iso.x <= page.width - 20
            # Rien ne déborde sur le cartouche, au coin bas droit.
            for spot, half_width, half_height in (
                (layout.top, width / 2, depth / 2),
                (layout.side, depth / 2, height / 2),
            ):
                over_block = spot.x + half_width > page.width - 190 + 1e-9
                assert not over_block or spot.y - half_height >= 65 - 1e-9


def test_ouvrage_trop_grand_signale() -> None:
    layout = overall_layout((900_000, 900_000, 900_000), page_size("A4"))
    assert not layout.fits
    assert layout.scale == SCALES[-1]


@pytest.mark.parametrize("bad", [0.0, -5.0, math.nan, math.inf, 1e9])
def test_cote_refusee(bad: float) -> None:
    with pytest.raises(TemplatedError):
        overall_layout((bad, 600, 750), A3)
    with pytest.raises(TemplatedError):
        overall_layout((1200, 600, bad), A3)


def test_gabarit_iso_prefere() -> None:
    paths = [
        "/t/A3_Landscape_blank.svg",
        "/t/A3_Landscape_ISO7200TD.svg",
        "/t/A3_Landscape_ISO7200_Pep.svg",
        "/t/A4_Landscape_ISO7200TD.svg",
        "/t/A3_Portrait_ISO7200TD.svg",
        "/t/zh_CN/landscape/A3_Landscape_CN_CLIP.svg",
    ]
    assert pick_template(paths, "A3", Orientation.LANDSCAPE) == "/t/A3_Landscape_ISO7200TD.svg"
    assert pick_template(paths, "A3", Orientation.PORTRAIT) == "/t/A3_Portrait_ISO7200TD.svg"
    assert pick_template(paths, "A4", Orientation.LANDSCAPE) == "/t/A4_Landscape_ISO7200TD.svg"


def test_gabarit_dans_un_sous_dossier_et_a_defaut() -> None:
    nested = [
        "C:\\fc\\Templates\\ISO\\A3_Landscape_ISO5457_minimal.svg",
        "/t/A3_Landscape_ASME.svg",
    ]
    assert pick_template(nested, "a3", Orientation.LANDSCAPE) == nested[0]
    assert pick_template(["/t/A3_Landscape_blank.svg"], "A3", Orientation.LANDSCAPE) is not None
    assert (
        pick_template(["/t/A3_Landscape.txt", "/t/A2_Landscape.svg"], "A3", Orientation.LANDSCAPE)
        is None
    )
    assert pick_template([], "A3", Orientation.LANDSCAPE) is None
    assert pick_template(["/t/A3_Landscape.svg"], " ", Orientation.LANDSCAPE) is None


# --- Vue éclatée : écart des pièces et perspective seule ---------------------------------------


def test_ecart_de_la_vue_eclatee() -> None:
    from freecad.menuiserie.core.drawing import exploded_offset

    assert exploded_offset((0, 0, 0), (0, 0, 0)) == (0, 0, 0)
    offset = exploded_offset((100, 50, 0), (200, 50, -100))
    assert offset == pytest.approx((60, 0, -60))


def test_perspective_seule_au_dessus_du_cartouche() -> None:
    from freecad.menuiserie.core.drawing import single_view_layout
    from freecad.menuiserie.core.drawing._layout import MARGIN_MM, TITLE_BLOCK_MM

    page = page_size("A3")
    scale, spot, fits = single_view_layout(1200, 600, 750, page)
    assert fits
    assert 0 < scale <= 1
    assert spot.y > TITLE_BLOCK_MM[1]
    assert MARGIN_MM < spot.x < page.width - MARGIN_MM


def test_perspective_seule_demesuree_signalee() -> None:
    from freecad.menuiserie.core.drawing import SCALES, single_view_layout

    scale, _, fits = single_view_layout(90_000, 90_000, 90_000, page_size("A4"))
    assert not fits
    assert scale == SCALES[-1]


# --- Cotes de détail et angles de la face (retour de jv du 2026-11-13) --------------------------


def test_chaine_de_cotes_fusionne_les_points_proches() -> None:
    from freecad.menuiserie.core.drawing import chain_segments

    # Plateau de 22 sur un pied : 0, 22 (dessous du plateau), 700, 722 (dessus).
    segments = chain_segments([0, 722, 700, 0, 22, 722], min_gap=10)
    assert segments == [(0, 22), (22, 700), (700, 722)]
    # Points trop proches : fusionnés, l'extrémité gardée.
    assert chain_segments([0, 3, 500, 1000], min_gap=10) == [(0, 500), (500, 1000)]


def test_chaine_inutile_quand_elle_redit_la_cote_hors_tout() -> None:
    from freecad.menuiserie.core.drawing import chain_segments

    assert chain_segments([0, 1000, 0, 1000], min_gap=10) == []
    assert chain_segments([], min_gap=10) == []


def test_angle_des_pieces_en_biais() -> None:
    from freecad.menuiserie.core.drawing import slant_angle

    assert slant_angle(1, 0) is None  # horizontale
    assert slant_angle(0, 1) is None  # verticale
    assert slant_angle(0, 0) is None  # vue de bout
    assert slant_angle(1, 1) == pytest.approx(45)
    assert slant_angle(-1, math.tan(math.radians(35))) == pytest.approx(35)


def test_place_des_cotes_au_dessus_et_a_gauche_de_la_face() -> None:
    plain = overall_layout((1200, 600, 750), A3)
    banded = overall_layout((1200, 600, 750), A3, band=35)
    assert banded.scale <= plain.scale
    half_width, half_height = 1200 * banded.scale / 2, 750 * banded.scale / 2
    from freecad.menuiserie.core.drawing._layout import MARGIN_MM

    assert banded.front.x - half_width - 35 >= MARGIN_MM - 1e-9
    assert banded.front.y + half_height + 35 <= A3.height - MARGIN_MM + 1e-9
