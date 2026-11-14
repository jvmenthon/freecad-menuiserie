# SPDX-License-Identifier: LGPL-2.1-or-later
"""Plan de pièce (lot P-c) : usinages lus dans les formes des plans d'usinage, tableau, bande."""

from __future__ import annotations

import pytest

from freecad.menuiserie.core.drawing import (
    MAX_NOTE_LINES,
    MachiningKind,
    Orientation,
    capped,
    machining_lines,
    machinings,
    notes_band,
    overall_layout,
    page_size,
)
from freecad.menuiserie.core.drawing._layout import MARGIN_MM, TITLE_BLOCK_MM
from freecad.menuiserie.core.geometry import Axis, Box, Cylinder, Vec3

SIZE = (600.0, 80.0, 22.0)  # longueur, largeur, épaisseur


def test_mortaise_sur_la_face() -> None:
    mortise = Box(Vec3(50, 30, 2), Vec3(90, 40, 22))
    (item,) = machinings([("Tenon-mortaise", mortise, MachiningKind.CUT)], SIZE)
    assert item.kind is MachiningKind.CUT
    assert item.face == (2, 1)  # s'ouvre sur la face
    assert item.depth == pytest.approx(20)
    assert item.size == pytest.approx((40, 10, 20))


def test_percages_en_bout_regroupes() -> None:
    holes = [Cylinder(Vec3(0, y, 11), Axis.X_POS, 4.0, 30.0) for y in (20.0, 60.0)]
    items = machinings([("Tourillons", hole, MachiningKind.CUT) for hole in holes], SIZE)
    assert all(item.kind is MachiningKind.HOLE and item.face == (0, -1) for item in items)
    assert items[0].diameter == pytest.approx(8)
    ((template, values),) = machining_lines(items)
    assert "Ø" in template
    assert values["count"] == "2"
    assert values["diameter"] == "8" and values["depth"] == "30"
    assert values["face"] == "au bout gauche"
    assert values["positions"] == "x 0 y 20; x 0 y 60"


def test_rainure_traversante_et_feuillure() -> None:
    groove = Box(Vec3(0, 30, 12), Vec3(600, 40, 22))  # de bout en bout, sur la face
    rabbet = Box(Vec3(0, 0, 12), Vec3(600, 10, 22))  # face et chant bas
    items = machinings(
        [("Rainure", groove, MachiningKind.CUT), ("Feuillure", rabbet, MachiningKind.CUT)], SIZE
    )
    assert [item.face for item in items] == [(2, 1), (2, 1)]
    assert [item.depth for item in items] == pytest.approx([10, 10])


def test_tenon_ajoute_en_bout() -> None:
    tenon = Box(Vec3(600, 20, 6), Vec3(630, 60, 16))
    (item,) = machinings([("Tenon", tenon, MachiningKind.ADDED)], SIZE)
    assert item.face == (0, 1)
    assert item.depth == pytest.approx(30)
    ((template, values),) = machining_lines([item])
    assert "longueur" in template and values["depth"] == "30"
    assert values["size"].split()[::2] == ["40", "10"]  # vue du bout : largeur, épaisseur
    assert values["name"] == "partie en saillie"  # sans nom d'assemblage
    assert values["positions"] == "y 20"  # repérée le long du bout


def test_forme_hors_de_la_piece_ignoree() -> None:
    outside = Box(Vec3(700, 0, 0), Vec3(720, 10, 10))
    assert machinings([("X", outside, MachiningKind.CUT)], SIZE) == []


def test_usinage_dans_la_masse() -> None:
    inner = Box(Vec3(100, 20, 5), Vec3(120, 30, 15))
    (item,) = machinings([("X", inner, MachiningKind.CUT)], SIZE)
    assert item.face is None
    ((_, values),) = machining_lines([item])
    assert values["face"] == "dans la masse"


def test_positions_limitees() -> None:
    holes = [Cylinder(Vec3(x, 40, 22), Axis.Z_NEG, 2.5, 10.0) for x in range(50, 550, 50)]
    items = machinings([("Taquets", hole, MachiningKind.CUT) for hole in holes], SIZE)
    ((_, values),) = machining_lines(items)
    assert values["count"] == "10"
    assert values["positions"].endswith("; …")


def test_tableau_tronque() -> None:
    lines = [f"ligne {index}" for index in range(20)]
    kept = capped(lines, "… et {count} autres")
    assert len(kept) == MAX_NOTE_LINES
    assert kept[-1] == f"… et {20 - MAX_NOTE_LINES + 1} autres"
    assert capped(lines[:3], "x") == lines[:3]


def test_tableau_hors_des_vues() -> None:
    for page in (page_size("A3"), page_size("A4"), page_size("A4", Orientation.PORTRAIT)):
        spot, reserve = notes_band(page)
        layout = overall_layout((1800, 22, 400), page, reserve=reserve)
        assert layout.fits
        # Toutes les vues restent au-dessus du cartouche et du tableau.
        lowest = layout.top.y - 22 * layout.scale / 2
        assert lowest >= TITLE_BLOCK_MM[1] + reserve - 1e-9
        if reserve == 0:  # bande à gauche du cartouche
            assert MARGIN_MM < spot.x < page.width - TITLE_BLOCK_MM[0]
            assert MARGIN_MM < spot.y < TITLE_BLOCK_MM[1]
        else:  # bande au-dessus du cartouche
            assert TITLE_BLOCK_MM[1] < spot.y < TITLE_BLOCK_MM[1] + reserve
    assert notes_band(page_size("A4", Orientation.PORTRAIT))[1] > 0
    assert notes_band(page_size("A3"))[1] == 0
