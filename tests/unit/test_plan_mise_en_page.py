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
    layout = overall_layout(1200, 600, 750, A3)
    assert layout.fits
    assert layout.scale == 0.1
    # Face en haut à gauche, dessus dessous, vue de gauche à droite, perspective à droite.
    assert layout.front.x == pytest.approx(20 + 60)
    assert layout.front.y == pytest.approx(297 - 20 - 37.5)
    assert layout.top.x == layout.front.x
    assert layout.top.y < layout.front.y - 37.5 - 30
    assert layout.side.y == layout.front.y
    assert layout.side.x > layout.front.x + 60 + 30
    assert layout.iso.x > layout.side.x + 30


def test_echelle_la_plus_grande_qui_tient() -> None:
    small = overall_layout(40, 20, 30, A3)
    assert small.scale == 2.0  # agrandissement d'un petit ouvrage
    tall = overall_layout(900, 400, 2200, A3)
    assert tall.fits
    larger = SCALES[SCALES.index(tall.scale) - 1]
    assert larger > tall.scale
    assert 2200 * larger + 20 + 65 > A3.height  # l'échelle au-dessus déborde en hauteur


def test_vues_dans_la_feuille() -> None:
    for sizes in ((1200, 600, 750), (600, 600, 2000), (3000, 300, 200), (10, 10, 10)):
        for page in (A3, page_size("A4"), page_size("A4", Orientation.PORTRAIT)):
            layout = overall_layout(*sizes, page)
            if not layout.fits:
                continue
            width, depth, height = (value * layout.scale for value in sizes)
            assert layout.front.x - width / 2 >= 20 - 1e-9
            assert layout.front.y + height / 2 <= page.height - 20 + 1e-9
            assert layout.top.y - depth / 2 >= 20 - 1e-9
            assert layout.iso.x <= page.width - 20


def test_ouvrage_trop_grand_signale() -> None:
    layout = overall_layout(900_000, 900_000, 900_000, page_size("A4"))
    assert not layout.fits
    assert layout.scale == SCALES[-1]


@pytest.mark.parametrize("bad", [0.0, -5.0, math.nan, math.inf, 1e9])
def test_cote_refusee(bad: float) -> None:
    with pytest.raises(TemplatedError):
        overall_layout(bad, 600, 750, A3)
    with pytest.raises(TemplatedError):
        overall_layout(1200, 600, bad, A3)


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
