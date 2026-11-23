# SPDX-License-Identifier: LGPL-2.1-or-later
"""Interface de la pièce en bois (PD-d) vérifiée sans FreeCAD : dessin du repère, textes et
enregistrement de la commande, icônes, ViewProvider (analyse statique)."""

from __future__ import annotations

import ast
import math
from typing import Any

import pytest

from freecad.menuiserie import ICONS_DIR
from freecad.menuiserie.core.grain_band import GrainBand, grain_band, rectangle
from freecad.menuiserie.gui.task_panels.shaped_part_drawing import (
    GRAIN_COLOR,
    GRAIN_OUTLINE_COLOR,
    axes_drawing,
    grain_axis,
)
from tests.unit.aides import ROOT
from tests.unit.test_commandes_assemblages import registered_commands
from tests.unit.test_structure_gui import literal_text_calls

GUI = ROOT / "freecad" / "menuiserie" / "gui"
COMMAND = GUI / "commands" / "shaped_part.py"
NAME = "Menuiserie_ShapedPart"


def test_trois_axes_et_pas_de_fil_sans_fil() -> None:
    drawing = axes_drawing((720.0, 95.0, 45.0))
    assert len(drawing.strokes) == 3
    origins = {stroke.lines[0][0] for stroke in drawing.strokes}
    assert len(origins) == 1


def test_fleche_du_fil_sur_la_face_du_dessus() -> None:
    drawing = axes_drawing((720.0, 95.0, 45.0), grain=0)
    (fill,) = drawing.solids
    contour, dashes = drawing.strokes[3:]
    assert fill.color == GRAIN_COLOR
    assert contour.color == dashes.color == GRAIN_OUTLINE_COLOR
    points = [p for face in fill.faces for p in face] + list(contour.lines[0])
    assert {p.z for p in points} == {45.0}
    xs, ys = [p.x for p in points], [p.y for p in points]
    assert (min(xs), max(xs)) == (72.0, 648.0)  # marge de 10 % à chaque bout
    assert 0.0 < min(ys) < 47.5 < max(ys) < 95.0
    assert contour.lines[0][0] == contour.lines[0][-1]  # contour fermé
    assert len(dashes.lines) >= 3


def test_double_fleche_symetrique() -> None:
    contour = axes_drawing((720.0, 95.0, 45.0), grain=0).strokes[3].lines[0]
    tips = [p for p in contour if p.y == 47.5]
    assert sorted(p.x for p in tips) == [72.0, 72.0, 648.0]  # deux pointes (départ répété)


def test_fil_en_largeur() -> None:
    (fill,) = axes_drawing((720.0, 95.0, 45.0), grain=1).solids
    points = [p for face in fill.faces for p in face]
    assert {p.x for p in points if p.y in (9.5, 85.5)} == {360.0}


def test_piece_convertie_en_l_fleche_sur_le_bois() -> None:
    ell = (((0.0, 0.0), (560.0, 0.0), (560.0, 90.0), (100.0, 90.0), (100.0, 330.0), (0.0, 330.0)),)
    (fill,) = axes_drawing((560.0, 330.0, 22.0), grain=0, outline=ell).solids
    points = [p for face in fill.faces for p in face]
    assert all(0.0 < p.y < 90.0 and 0.0 < p.x < 560.0 for p in points)


def test_bande_de_bois() -> None:
    band = grain_band(rectangle(720.0, 95.0), 0)
    assert band is not None
    assert (band.start, band.end, band.across) == (0.0, 720.0, 47.5)
    assert band.width == pytest.approx(95.0)
    assert grain_band((), 0) is None
    assert grain_band((((0.0, 0.0), (10.0, 0.0), (5.0, 0.0)),), 0) is None


def _inside(loops: tuple[tuple[tuple[float, float], ...], ...], x: float, y: float) -> bool:
    """Point dans le contour (pair-impair, rayon vers +X)."""
    crossings = 0
    for loop in loops:
        for a, b in zip(loop, (*loop[1:], loop[0]), strict=True):
            if (a[1] <= y < b[1]) or (b[1] <= y < a[1]):
                crossings += a[0] + (y - a[1]) / (b[1] - a[1]) * (b[0] - a[0]) > x
    return crossings % 2 == 1


def _band_in_wood(loops: tuple[tuple[tuple[float, float], ...], ...], axis: int) -> GrainBand:
    band = grain_band(loops, axis)
    assert band is not None
    for k in range(41):
        along = band.start + (band.end - band.start) * (0.001 + 0.998 * k / 40)
        for j in range(41):
            across = band.across + band.width * (j / 40 - 0.5) * 0.999
            x, y = (along, across) if axis == 0 else (across, along)
            assert _inside(loops, x, y), (x, y)
    return band


THIN_L = (((0.0, 0.0), (560.0, 0.0), (560.0, 5.0), (100.0, 5.0), (100.0, 330.0), (0.0, 330.0)),)
THIN_HOLE = (
    *rectangle(600.0, 200.0),
    ((200.0, 98.0), (400.0, 98.0), (400.0, 99.0), (200.0, 99.0)),
)
TRAPEZE = (((0.0, 0.0), (600.0, 0.0), (550.0, 95.0), (50.0, 95.0)),)
ELLIPSE = (
    tuple(
        (300.0 + 300.0 * math.cos(math.tau * k / 400), 100.0 + 100.0 * math.sin(math.tau * k / 400))
        for k in range(400)
    ),
)


@pytest.mark.parametrize("loops", [THIN_L, THIN_HOLE, TRAPEZE, ELLIPSE])
@pytest.mark.parametrize("axis", [0, 1])
def test_bande_toujours_dans_le_bois(loops: Any, axis: int) -> None:
    _band_in_wood(loops, axis)


def test_branche_fine_gardee_dans_le_sens_du_fil() -> None:
    band = _band_in_wood(THIN_L, 0)
    assert (band.start, band.end) == (0.0, 560.0)


def test_trou_fin_jamais_traverse() -> None:
    band = _band_in_wood(THIN_HOLE, 0)
    assert band.length == 600.0
    low, high = band.across - band.width / 2, band.across + band.width / 2
    assert high <= 98.0 or low >= 99.0


def test_sans_fil_pas_de_marque() -> None:
    assert not axes_drawing((720.0, 95.0, 45.0), grain=None).solids


def test_axe_du_fil() -> None:
    assert (grain_axis("Length"), grain_axis("Width"), grain_axis("None")) == (0, 1, None)


def test_taille_des_axes_bornee() -> None:
    small = axes_drawing((10.0, 10.0, 5.0)).strokes[0].lines[0][1].x
    large = axes_drawing((9000.0, 100.0, 20.0)).strokes[0].lines[0][1].x
    assert (small, large) == (40.0, 400.0)


def test_commande_enregistree_icone_et_menu() -> None:
    assert registered_commands(COMMAND) == [NAME]
    assert (ICONS_DIR / f"{NAME}.svg").is_file()
    assert (ICONS_DIR / "Menuiserie_ShapedPartObject.svg").is_file()
    assert f'"{NAME}"' in (ROOT / "freecad" / "menuiserie" / "init_gui.py").read_text("utf-8")


def test_aucun_texte_en_dur() -> None:
    for name in ("shaped_part", "shaped_part_frame", "timber_rows"):
        folder = "commands" if name == "shaped_part" else "task_panels"
        assert literal_text_calls(GUI / folder / f"{name}.py") == []
    assert literal_text_calls(GUI / "task_panels" / "shaped_part.py") == []


def test_viewprovider_chemin_fige() -> None:
    tree = ast.parse((GUI / "view_providers" / "shaped_part.py").read_text("utf-8"))
    names = [n.name for n in tree.body if isinstance(n, ast.ClassDef)]
    assert names == ["ViewProviderShapedPart"]
