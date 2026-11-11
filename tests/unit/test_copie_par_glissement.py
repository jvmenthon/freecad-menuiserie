# SPDX-License-Identifier: LGPL-2.1-or-later
"""Copie par glissement, partie pure (lot R-d, ``gui/drag/copy_rules.py`` et fantôme de
``gui/drag/geometry.py``) : axe global de la flèche, paramètres de la répétition d'une copie,
dessin du fantôme, garde-fous de structure."""

from __future__ import annotations

import math

import pytest

from freecad.menuiserie.core.geometry import Box, Vec3
from freecad.menuiserie.core.i18n import TemplatedError
from freecad.menuiserie.core.repeat import RepeatAxis, SpacingMode
from freecad.menuiserie.core.snap import Frame
from freecad.menuiserie.gui.drag.copy_rules import MIN_MOVE, copy_params, global_axis
from freecad.menuiserie.gui.drag.geometry import GHOST_COLOR, Cues, build_drawing, build_layout
from tests.unit.aides import ROOT, imported_modules

PACKAGE = ROOT / "freecad" / "menuiserie"
STRAIGHT = Frame(Vec3(0, 0, 0), Vec3(1, 0, 0), Vec3(0, 1, 0), Vec3(0, 0, 1))
QUARTER_TURN = Frame(Vec3(0, 0, 0), Vec3(0, 1, 0), Vec3(-1, 0, 0), Vec3(0, 0, 1))  # 90° autour de Z
HALF_TURN = Frame(Vec3(0, 0, 0), Vec3(-1, 0, 0), Vec3(0, -1, 0), Vec3(0, 0, 1))  # 180° autour de Z
TILTED = Frame(
    Vec3(0, 0, 0),
    Vec3(math.cos(0.3), math.sin(0.3), 0),
    Vec3(-math.sin(0.3), math.cos(0.3), 0),
    Vec3(0, 0, 1),
)
BOX = Box.from_ranges([(0, 800), (0, 200), (0, 22)])


# --- Axe global de la flèche --------------------------------------------------------------


@pytest.mark.parametrize(
    ("frame", "local", "expected"),
    [
        (STRAIGHT, 0, (RepeatAxis.X, 1.0)),
        (STRAIGHT, 2, (RepeatAxis.Z, 1.0)),
        (QUARTER_TURN, 0, (RepeatAxis.Y, 1.0)),
        (QUARTER_TURN, 1, (RepeatAxis.X, -1.0)),
        (HALF_TURN, 0, (RepeatAxis.X, -1.0)),
    ],
)
def test_axe_global_de_la_fleche(
    frame: Frame, local: int, expected: tuple[RepeatAxis, float]
) -> None:
    assert global_axis(frame, local) == expected


def test_piece_tournee_hors_des_axes_refusee() -> None:
    with pytest.raises(TemplatedError, match="parallèle à un axe X, Y ou Z"):
        global_axis(TILTED, 0)
    assert global_axis(TILTED, 2) == (RepeatAxis.Z, 1.0)  # l'axe de rotation reste droit


# --- Paramètres de la répétition d'une copie ---------------------------------------------


def test_une_copie_au_pas_du_deplacement() -> None:
    params = copy_params(RepeatAxis.X, 1.0, 250.0)
    assert params is not None
    assert (params.spacing, params.count, params.step) == (SpacingMode.COUNT_AND_STEP, 1, 250.0)
    assert (params.axis, params.reverse) == (RepeatAxis.X, False)


def test_deplacement_negatif_inverse_le_sens() -> None:
    params = copy_params(RepeatAxis.Y, 1.0, -120.0)
    assert params is not None
    assert (params.axis, params.step, params.reverse) == (RepeatAxis.Y, 120.0, True)


def test_axe_de_la_piece_oppose_a_l_axe_global() -> None:
    forward = copy_params(RepeatAxis.X, -1.0, 80.0)  # avance sur l'axe de la pièce = recule en X
    backward = copy_params(RepeatAxis.X, -1.0, -80.0)
    assert forward is not None and backward is not None
    assert (forward.reverse, backward.reverse) == (True, False)
    assert forward.step == backward.step == 80.0


def test_copie_par_defaut_liee_aux_assemblages() -> None:
    params = copy_params(RepeatAxis.Z, 1.0, 50.0)
    assert params is not None
    assert (params.copy_joints, params.follow_resize) == (True, False)


def test_simple_clic_sans_copie() -> None:
    assert copy_params(RepeatAxis.X, 1.0, 0.0) is None
    assert copy_params(RepeatAxis.X, 1.0, MIN_MOVE / 2) is None
    assert copy_params(RepeatAxis.X, 1.0, -MIN_MOVE / 2) is None
    assert copy_params(RepeatAxis.X, 1.0, MIN_MOVE) is not None  # au minimum : copie


# --- Fantôme ------------------------------------------------------------------------------


def test_fantome_boite_decalee_sans_toucher_aux_fleches() -> None:
    layout = build_layout(STRAIGHT, BOX, 100.0, frozenset(), frozenset())
    plain = build_drawing(layout)
    shown = build_drawing(layout, cues=Cues(ghost=Vec3(300, 0, 0)))
    assert len(shown.strokes) == len(plain.strokes) + 1
    assert len(shown.solids) == len(plain.solids) + 1
    outline = next(s for s in shown.strokes if s.color == GHOST_COLOR)
    points = {(p.x, p.y, p.z) for line in outline.lines for p in line}
    assert len(outline.lines) == 12
    assert min(p[0] for p in points) == 300.0
    assert max(p[0] for p in points) == 1100.0
    assert {p[1] for p in points} == {0.0, 200.0}
    face = next(s for s in shown.solids if s.color == GHOST_COLOR)
    assert len(face.faces) == 6
    assert 0.0 < face.transparency < 1.0


def test_fantome_dans_le_repere_de_la_piece() -> None:
    layout = build_layout(QUARTER_TURN, BOX, 100.0, frozenset(), frozenset())
    outline = next(
        s
        for s in build_drawing(layout, cues=Cues(ghost=Vec3(100, 0, 0))).strokes
        if s.color == GHOST_COLOR
    )
    points = {(round(p.x, 6), round(p.y, 6)) for line in outline.lines for p in line}
    assert {y for _, y in points} == {100.0, 900.0}  # X de la pièce = Y du document


def test_sans_copie_aucun_fantome() -> None:
    layout = build_layout(STRAIGHT, BOX, 100.0, frozenset(), frozenset())
    assert all(s.color != GHOST_COLOR for s in build_drawing(layout).strokes)


# --- Structure ----------------------------------------------------------------------------


def test_regles_de_la_copie_sans_freecad_ni_qt() -> None:
    modules = imported_modules(PACKAGE / "gui" / "drag" / "copy_rules.py")
    assert {"FreeCAD", "FreeCADGui", "PySide", "pivy", "Part"}.isdisjoint(modules)
