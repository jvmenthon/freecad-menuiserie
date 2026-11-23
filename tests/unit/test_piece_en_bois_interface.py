# SPDX-License-Identifier: LGPL-2.1-or-later
"""Interface de la pièce en bois (PD-d) vérifiée sans FreeCAD : dessin du repère, textes et
enregistrement de la commande, icônes, ViewProvider (analyse statique)."""

from __future__ import annotations

import ast

from freecad.menuiserie import ICONS_DIR
from freecad.menuiserie.core.grain_band import grain_band, rectangle
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
    assert (band.start, band.end, band.across, band.width) == (0.0, 720.0, 47.5, 95.0)
    holed = (
        *rectangle(600.0, 200.0),
        ((200.0, 80.0), (400.0, 80.0), (400.0, 120.0), (200.0, 120.0)),
    )
    band = grain_band(holed, 0)
    assert band is not None
    assert band.length == 600.0
    assert band.across + band.width / 2 <= 80.0 or band.across - band.width / 2 >= 120.0
    assert grain_band((), 0) is None
    assert grain_band((((0.0, 0.0), (10.0, 0.0)),), 0) is None


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
