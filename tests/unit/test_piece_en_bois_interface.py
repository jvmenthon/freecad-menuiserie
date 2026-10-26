# SPDX-License-Identifier: LGPL-2.1-or-later
"""Interface de la pièce en bois (PD-d) vérifiée sans FreeCAD : dessin du repère, textes et
enregistrement de la commande, icônes, ViewProvider (analyse statique)."""

from __future__ import annotations

import ast

from freecad.menuiserie import ICONS_DIR
from freecad.menuiserie.gui.task_panels.shaped_part_drawing import (
    GRAIN_COLOR,
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
    grain = drawing.strokes[-1]
    assert grain.color == GRAIN_COLOR
    start, end = grain.lines[0]
    assert (start.z, end.z) == (45.0, 45.0)
    assert (start.y, end.y) == (47.5, 47.5)
    assert end.x > start.x


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
