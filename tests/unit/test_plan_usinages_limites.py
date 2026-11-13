# SPDX-License-Identifier: LGPL-2.1-or-later
"""Plan de pièce (lot P-c) : cas limites du tableau des usinages et de sa mise en page
(revue testeur de la PR #247, issue #153, ADR 0053)."""

from __future__ import annotations

import math

import pytest

from freecad.menuiserie.core._polyhedron import SlantedCylinder
from freecad.menuiserie.core.drawing import (
    MAX_NOTE_LINES,
    MachiningKind,
    Orientation,
    PageSize,
    capped,
    corner_iso_layout,
    machining_lines,
    machinings,
    notes_band,
    notes_layout,
    overall_layout,
    page_size,
)
from freecad.menuiserie.core.drawing._layout import (
    CHAR_WIDTH_RATIO,
    MARGIN_MM,
    TITLE_BLOCK_MM,
)
from freecad.menuiserie.core.geometry import Axis, Box, Cylinder, Vec3

SIZE = (600.0, 80.0, 22.0)  # longueur, largeur, épaisseur
NOTE_SIZE = 3.5  # hauteur du texte du tableau (features/drawing_views.NOTE_SIZE_MM)
PAGES = (
    page_size("A3"),
    page_size("A3", Orientation.PORTRAIT),
    page_size("A4"),
    page_size("A4", Orientation.PORTRAIT),
)


# --- Pièce sans usinage, regroupements ---------------------------------------------------------


def test_piece_sans_usinage() -> None:
    assert machinings([], SIZE) == []
    assert machining_lines([]) == []


def test_memes_percages_de_deux_assemblages_non_regroupes() -> None:
    hole = Cylinder(Vec3(100, 40, 22), Axis.Z_NEG, 4.0, 10.0)
    other = Cylinder(Vec3(300, 40, 22), Axis.Z_NEG, 4.0, 10.0)
    items = machinings([("A", hole, MachiningKind.CUT), ("B", other, MachiningKind.CUT)], SIZE)
    lines = machining_lines(items)
    assert [values["label"] for _, values in lines] == ["A", "B"]
    assert all(values["count"] == "1" for _, values in lines)


def test_profondeurs_differentes_non_regroupees() -> None:
    holes = [
        Cylinder(Vec3(100, 40, 22), Axis.Z_NEG, 4.0, 10.0),
        Cylinder(Vec3(300, 40, 22), Axis.Z_NEG, 4.0, 12.0),
    ]
    items = machinings([("A", hole, MachiningKind.CUT) for hole in holes], SIZE)
    assert len(machining_lines(items)) == 2


def test_percage_sur_le_chant_bas() -> None:
    hole = Cylinder(Vec3(100, 0, 11), Axis.Y_POS, 4.0, 25.0)
    (item,) = machinings([("T", hole, MachiningKind.CUT)], SIZE)
    assert item.kind is MachiningKind.HOLE
    assert item.face == (1, -1)
    assert item.depth == pytest.approx(25)


def test_tenon_en_bout_gauche() -> None:
    tenon = Box(Vec3(-30, 20, 6), Vec3(0, 60, 16))
    (item,) = machinings([("Tenon", tenon, MachiningKind.ADDED)], SIZE)
    assert item.face == (0, -1)
    assert item.depth == pytest.approx(30)


def test_quatre_positions_sans_points_de_suite() -> None:
    holes = [Cylinder(Vec3(x, 40, 22), Axis.Z_NEG, 2.5, 10.0) for x in (50, 150, 250, 350)]
    items = machinings([("Taquets", hole, MachiningKind.CUT) for hole in holes], SIZE)
    ((_, values),) = machining_lines(items)
    assert values["count"] == "4"
    assert not values["positions"].endswith("…")
    assert values["positions"].count("x ") == 4


# --- Usinages débouchants : défauts ------------------------------------------------------------


def test_percage_debouchant_n_est_pas_dans_la_masse() -> None:
    """Un perçage qui traverse l'épaisseur s'ouvre sur la face ; sa profondeur est l'épaisseur
    de la pièce, pas son diamètre."""
    hole = Cylinder(Vec3(100, 40, 22), Axis.Z_NEG, 4.0, 22.0)
    (item,) = machinings([("Traversant", hole, MachiningKind.CUT)], SIZE)
    ((_, values),) = machining_lines([item])
    assert values["face"] != "dans la masse"
    assert item.depth == pytest.approx(22)


def test_mortaise_debouchante_n_est_pas_dans_la_masse() -> None:
    mortise = Box(Vec3(50, 30, 0), Vec3(90, 40, 22))
    (item,) = machinings([("Mortaise", mortise, MachiningKind.CUT)], SIZE)
    assert item.face is not None
    assert item.depth == pytest.approx(22)


# --- Perçage en biais : défauts ------------------------------------------------------------------


def _slanted() -> SlantedCylinder:
    angle = math.radians(30)
    direction = Vec3(math.sin(angle), 0.0, -math.cos(angle))
    return SlantedCylinder(Vec3(100, 40, 22), direction, 4.0, 15.0)


def test_percage_en_biais_profondeur() -> None:
    """Point le plus bas d'un perçage Ø 8 de 15 mm incliné de 30° depuis la face :
    15 cos 30° + 4 sin 30° ≈ 15 mm sous la face (et non 17, encombrement majoré du rayon)."""
    (item,) = machinings([("Biais", _slanted(), MachiningKind.CUT)], SIZE)
    assert item.kind is MachiningKind.HOLE
    assert item.face == (2, 1)
    assert item.depth == pytest.approx(15.0, abs=0.5)


def test_percage_en_biais_centre_de_l_entree() -> None:
    """La position écrite d'un perçage est le centre de son entrée (docstring du module)."""
    (item,) = machinings([("Biais", _slanted(), MachiningKind.CUT)], SIZE)
    ((_, values),) = machining_lines([item])
    assert values["positions"] == "x 100 y 40"


# --- Ajouts hors de la pièce -----------------------------------------------------------------


def test_ajout_detache_de_la_piece_ignore() -> None:
    """Un ajout qui ne touche pas la pièce n'est pas un usinage de cette pièce."""
    floating = Box(Vec3(700, 20, 6), Vec3(730, 60, 16))
    beside = Box(Vec3(600, 200, 6), Vec3(630, 260, 16))
    items = [("A", floating, MachiningKind.ADDED), ("B", beside, MachiningKind.ADDED)]
    assert machinings(items, SIZE) == []


def test_tenon_engage_dans_la_piece_sort_par_le_bout() -> None:
    """Tenon modélisé avec 1 mm d'engagement dans la pièce (recouvrement pour la fusion) :
    il sort toujours par le bout droit, il n'est pas « dans la masse »."""
    tenon = Box(Vec3(599, 20, 6), Vec3(630, 60, 16))
    (item,) = machinings([("Tenon", tenon, MachiningKind.ADDED)], SIZE)
    assert item.face == (0, 1)


# --- Tableau tronqué et coupé à la largeur de sa bande -----------------------------------------


def test_tableau_juste_a_la_limite() -> None:
    lines = [f"ligne {index}" for index in range(MAX_NOTE_LINES)]
    assert capped(lines, "… et {count} autres") == lines
    over = capped([*lines, "de trop"], "… et {count} autres")
    assert len(over) == MAX_NOTE_LINES
    assert over[-1] == "… et 2 autres"


@pytest.mark.parametrize("page", PAGES, ids=lambda page: f"{page.width:g}x{page.height:g}")
def test_lignes_longues_coupees_dans_la_bande(page: PageSize) -> None:
    head = "Tenon-mortaise : 12 enlèvement(s) 40 \u00d7 10 \u00d7 20, prof. 20, face, "
    long_line = head + "; ".join(f"x {x} y 30" for x in range(50, 600, 50))
    wrapped, spot = notes_layout(page, ["Usinages :", long_line], NOTE_SIZE)
    assert len(wrapped) > 2
    assert all(line.startswith("    ") for line in wrapped[2:])  # suite en retrait
    char = CHAR_WIDTH_RATIO * NOTE_SIZE
    block = max(len(line) for line in wrapped) * char
    assert spot.x - block / 2 >= MARGIN_MM - 1e-9
    _, reserve = notes_band(page)
    if reserve == 0:  # à gauche du cartouche : n'empiète pas dessus
        assert spot.x + block / 2 <= page.width - TITLE_BLOCK_MM[0] + 1e-9
    else:
        assert spot.x + block / 2 <= page.width - MARGIN_MM + 1e-9


@pytest.mark.parametrize("page", PAGES, ids=lambda page: f"{page.width:g}x{page.height:g}")
def test_tableau_tronque_tient_dans_sa_bande(page: PageSize) -> None:
    """Huit lignes de 3,5 mm (interligne TechDraw compris, ≈ 1,5) tiennent dans la bande."""
    _, reserve = notes_band(page)
    height = reserve if reserve else TITLE_BLOCK_MM[1] - MARGIN_MM
    assert height >= MAX_NOTE_LINES * NOTE_SIZE * 1.5


# --- Pièce très longue, A4 portrait --------------------------------------------------------------


@pytest.mark.parametrize("length", [2500.0, 6000.0, 12000.0])
@pytest.mark.parametrize("page", PAGES, ids=lambda page: f"{page.width:g}x{page.height:g}")
def test_piece_tres_longue_tient_au_dessus_du_tableau(page: PageSize, length: float) -> None:
    _, reserve = notes_band(page)
    layout = overall_layout(length, 22, 80, page, reserve=reserve, iso=False)
    assert layout.fits
    face_width = length * layout.scale
    assert layout.front.x - face_width / 2 >= MARGIN_MM - 1e-9
    assert layout.side.x + 22 * layout.scale / 2 <= page.width - MARGIN_MM + 1e-9
    lowest = layout.top.y - 22 * layout.scale / 2
    assert lowest >= TITLE_BLOCK_MM[1] + reserve - 1e-9


def test_piece_demesuree_signalee() -> None:
    page = page_size("A4", Orientation.PORTRAIT)
    _, reserve = notes_band(page)
    assert not overall_layout(50_000, 22, 80, page, reserve=reserve, iso=False).fits


def test_tableau_tronque_garde_les_usinages_entiers() -> None:
    """Un usinage coupé sur plusieurs lignes n'est jamais coupé par la troncature ; le message
    compte les usinages omis."""
    lines = ["Usinages :"]
    for index in range(5):
        lines += [f"usinage {index}", "    suite"]
    kept = capped(lines, "… et {count} autres")
    assert len(kept) <= MAX_NOTE_LINES
    assert not kept[-2].startswith("    usinage")
    assert kept[-2] == "    suite"
    assert kept[-1] == "… et 2 autres"


# --- Perspective d'une pièce dans le coin libre --------------------------------------------------


@pytest.mark.parametrize("page", PAGES, ids=lambda page: f"{page.width:g}x{page.height:g}")
@pytest.mark.parametrize("length", [400.0, 2500.0])
def test_perspective_de_piece_dans_le_coin_libre(page: PageSize, length: float) -> None:
    _, reserve = notes_band(page)
    sizes = (length, 22.0, 80.0)
    layout = overall_layout(*sizes, page, reserve=reserve, iso=False)
    corner = corner_iso_layout(sizes, layout, page, reserve)
    if corner is None:
        return  # pas la place : pas de perspective
    scale, spot = corner
    assert scale <= layout.scale
    assert spot.x > layout.side.x + 22 * layout.scale / 2
    assert spot.x < page.width - MARGIN_MM
    assert spot.y > TITLE_BLOCK_MM[1] + reserve


def test_perspective_garde_l_echelle_des_vues_cotees() -> None:
    """La perspective ne réduit pas l'échelle de la face d'une pièce longue."""
    page = page_size("A3")
    _, reserve = notes_band(page)
    without = overall_layout(2000, 22, 80, page, reserve=reserve, iso=False)
    with_iso = overall_layout(2000, 22, 80, page, reserve=reserve, iso=True)
    assert without.scale >= with_iso.scale
    assert corner_iso_layout((2000, 22, 80), without, page, reserve) is not None
