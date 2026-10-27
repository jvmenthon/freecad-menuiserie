# SPDX-License-Identifier: LGPL-2.1-or-later
"""Glisser à la souris, partie pure de l'interface (SM-c, ``gui/drag/geometry.py``) : clés des
flèches et poignées, rayon, disposition, dessin, cadence ; et garde-fous de structure (pivy dans
un seul module, filtre posé et retiré avec l'atelier)."""

from __future__ import annotations

import ast

import pytest

from freecad.menuiserie.core.geometry import Box, Vec3
from freecad.menuiserie.core.magnet import Guide, GuideKind, Handle, handle_at
from freecad.menuiserie.core.snap import Frame
from freecad.menuiserie.gui.drag.geometry import (
    GUIDE_COLOR,
    HANDLE_COLOR,
    HOVER_COLOR,
    Throttle,
    arrow_key,
    build_drawing,
    build_layout,
    guide_outline,
    handle_key,
    mouse_ray,
    parse_key,
    pixel_targets,
    target_line,
)
from tests.unit.aides import ROOT, imported_modules

FRAME = Frame(Vec3(10, 20, 30), Vec3(1, 0, 0), Vec3(0, 1, 0), Vec3(0, 0, 1))
BOX = Box.from_ranges([(0, 800), (0, 200), (0, 22)])
PACKAGE = ROOT / "freecad" / "menuiserie"
FREE = frozenset({0, 1, 2})


def project(point: Vec3) -> tuple[float, float]:
    """Projection de test : vue de dessus, 1 pixel = 1 mm."""
    return point.x, point.y


# --- Clés ---------------------------------------------------------------------------------


def test_cles_des_fleches_et_des_poignees() -> None:
    assert [parse_key(arrow_key(a)) for a in range(3)] == [0, 1, 2]
    for handle in (Handle(0, False), Handle(1, True)):
        assert parse_key(handle_key(handle)) == handle
    assert len({handle_key(Handle(a, e)) for a in range(3) for e in (False, True)}) == 6


@pytest.mark.parametrize("key", ["", "arrow3", "handle0", "handle3s", "handle0x", "x"])
def test_cle_inconnue(key: str) -> None:
    with pytest.raises(ValueError, match="clé"):
        parse_key(key)


# --- Rayon de la souris -------------------------------------------------------------------


def test_rayon_orthogonal_et_perspective() -> None:
    ortho = mouse_ray(Vec3(5, 6, 0), Vec3(0, 0, -2), None)
    assert (ortho.origin, ortho.direction) == (Vec3(5, 6, 0), Vec3(0, 0, -1))
    persp = mouse_ray(Vec3(0, 0, 0), Vec3(0, 0, -1), Vec3(0, 0, 10))
    assert (persp.origin, persp.direction) == (Vec3(0, 0, 10), Vec3(0, 0, -1))


# --- Disposition --------------------------------------------------------------------------


def test_trois_fleches_et_quatre_poignees() -> None:
    layout = build_layout(FRAME, BOX, 100.0, frozenset(), frozenset({0, 1}))
    assert [a.axis for a in layout.arrows] == [0, 1, 2]
    assert [(h.axis, h.at_end) for h, _ in layout.handles] == [
        (0, False),
        (0, True),
        (1, False),
        (1, True),
    ]
    centers = {(h.axis, h.at_end): p for h, p in layout.handles}
    assert centers[(0, False)] == Vec3(10, 120, 41)  # milieu de la face de début, repère global
    assert centers[(0, True)] == Vec3(810, 120, 41)
    assert centers[(1, True)] == Vec3(410, 220, 41)


def test_poignees_d_epaisseur_ecartees_du_depart_des_fleches() -> None:
    layout = build_layout(FRAME, BOX, 100.0, frozenset(), frozenset({0, 1, 2}))
    centers = {(h.axis, h.at_end): p for h, p in layout.handles}
    start = layout.arrows[0].start
    top, bottom = centers[(2, True)], centers[(2, False)]
    assert (top.x, top.y) == (start.x - 200, start.y)  # un quart des 800 mm vers le début
    assert (bottom.x, bottom.y) == (start.x + 200, start.y)
    assert top.z > start.z > bottom.z


def test_axe_pilote_par_une_formule_sans_fleche() -> None:
    layout = build_layout(FRAME, BOX, 100.0, frozenset({1}), frozenset())
    assert [a.axis for a in layout.arrows] == [0, 2]
    assert layout.handles == ()


def test_cibles_en_pixels_et_saisie() -> None:
    layout = build_layout(FRAME, BOX, 100.0, frozenset(), frozenset({0, 1}))
    targets = pixel_targets(layout, project)
    assert handle_at(targets, (810, 120)) == handle_key(Handle(0, True))
    assert handle_at(targets, (810 + 28, 120 + 5)) == handle_key(Handle(0, True))  # pointe
    assert handle_at(targets, (410 + 50, 120)) == arrow_key(0)  # sur le corps de la flèche X
    assert handle_at(targets, (410, 120 + 40)) == arrow_key(1)
    assert handle_at(targets, (410, 400)) is None
    # Flèche Z vue de dessus : un point, pas saisissable ; la flèche X l'emporte au centre.
    assert handle_at(targets, (410, 120)) == arrow_key(0)


def test_axe_d_une_cible() -> None:
    layout = build_layout(FRAME, BOX, 100.0, frozenset(), frozenset({0}))
    line = target_line(layout, arrow_key(1))
    assert (line.origin, line.direction) == (Vec3(410, 120, 41), Vec3(0, 1, 0))
    line = target_line(layout, handle_key(Handle(0, True)))
    assert (line.origin, line.direction) == (Vec3(810, 120, 41), Vec3(1, 0, 0))
    with pytest.raises(ValueError, match="absente"):
        target_line(layout, handle_key(Handle(1, True)))


# --- Dessin -------------------------------------------------------------------------------


def test_dessin_des_fleches_aux_couleurs_des_axes() -> None:
    layout = build_layout(FRAME, BOX, 100.0, frozenset(), frozenset())
    drawing = build_drawing(layout)
    colors = [stroke.color for stroke in drawing.strokes]
    assert len(set(colors)) == 3 and HOVER_COLOR not in colors
    assert all(len(stroke.lines) == 5 for stroke in drawing.strokes)  # tige et quatre barbes
    assert drawing.dots == ()


def test_surbrillance_de_la_cible_survolee() -> None:
    layout = build_layout(FRAME, BOX, 100.0, frozenset(), frozenset({0}))
    drawing = build_drawing(layout, hover=arrow_key(1))
    assert [s.color == HOVER_COLOR for s in drawing.strokes] == [False, True, False, False, False]
    drawing = build_drawing(layout, hover=handle_key(Handle(0, True)))
    assert [d.color == HOVER_COLOR for d in drawing.dots] == [False, True]
    assert [s.color == HOVER_COLOR for s in drawing.strokes] == [False] * 4 + [True]


def test_poignee_dessinee_en_double_fleche_dans_l_axe_de_la_cote() -> None:
    layout = build_layout(FRAME, BOX, 100.0, frozenset(), frozenset({1}))
    drawing = build_drawing(layout)
    handles = [s for s in drawing.strokes if s.color == HANDLE_COLOR]
    assert len(handles) == 2 and all(len(s.lines) == 5 for s in handles)  # tige, 2 x 2 barbes
    (start, end) = handles[1].lines[0]  # poignée de fin de l'axe Y, centrée sur sa face
    assert (start.x, end.x, start.z, end.z) == (410, 410, 41, 41)
    assert (start.y, end.y) == (220 - 30, 220 + 30)  # 30 % des 100 mm des flèches de chaque côté
    assert {line[1].z for line in handles[1].lines[1:]} == {41}  # barbes dans le plan X, Y
    assert [d.points for d in drawing.dots] == [(p,) for _, p in layout.handles]


def test_guides_aimantes_en_surbrillance() -> None:
    layout = build_layout(FRAME, BOX, 100.0, frozenset(), frozenset())
    plane = Guide(GuideKind.PLANE, Box.from_ranges([(850, 850), (0, 200), (0, 22)]), 0, -1)
    corner = Guide(GuideKind.POINT, Box(Vec3(1, 2, 3), Vec3(1, 2, 3)))
    drawing = build_drawing(layout, guides=[plane, corner])
    lit = [s for s in drawing.strokes if s.color == GUIDE_COLOR]
    assert len(lit) == 1 and lit[0].lines[0][0] == Vec3(860, 20, 30)  # repère global
    assert [d.points for d in drawing.dots if d.color == GUIDE_COLOR] == [(Vec3(11, 22, 33),)]


def test_guide_dessine_la_ou_il_est_malgre_le_deplacement_de_la_piece() -> None:
    """La pièce a glissé de 300 mm en X depuis le début : le guide (lu dans son repère de départ)
    reste sur la face voisine au lieu de la suivre."""
    moved = Frame(Vec3(310, 20, 30), Vec3(1, 0, 0), Vec3(0, 1, 0), Vec3(0, 0, 1))
    layout = build_layout(moved, BOX, 100.0, frozenset(), frozenset())
    plane = Guide(GuideKind.PLANE, Box.from_ranges([(850, 850), (0, 200), (0, 22)]), 0, -1)
    drawing = build_drawing(layout, guides=[plane], guides_frame=FRAME)
    lit = [s for s in drawing.strokes if s.color == GUIDE_COLOR]
    assert {p.x for p in lit[0].lines[0]} == {860}  # 10 + 850, pas 310 + 850
    suivi = build_drawing(layout, guides=[plane])  # sans repère de départ : repère courant
    assert {p.x for s in suivi.strokes if s.color == GUIDE_COLOR for p in s.lines[0]} == {1160}


def test_contour_des_guides() -> None:
    plane = Guide(GuideKind.PLANE, Box.from_ranges([(5, 5), (0, 2), (0, 3)]), 0, 1)
    outline = guide_outline(plane)
    assert len(outline) == 5 and outline[0] == outline[-1]
    assert {p.x for p in outline} == {5}
    line = Guide(GuideKind.LINE, Box.from_ranges([(0, 9), (1, 1), (2, 2)]), 0)
    assert guide_outline(line) == (Vec3(0, 1, 2), Vec3(9, 1, 2))
    assert guide_outline(Guide(GuideKind.POINT, Box(Vec3(1, 1, 1), Vec3(1, 1, 1)))) == (
        Vec3(1, 1, 1),
    )


# --- Cadence ------------------------------------------------------------------------------


def test_cadence_de_trente_par_seconde() -> None:
    throttle = Throttle(30)
    assert throttle.wait(0.0) == 0.0
    assert throttle.ready(0.0) is True
    assert throttle.ready(0.01) is False
    assert throttle.wait(0.01) == pytest.approx(1 / 30 - 0.01)
    assert throttle.ready(1 / 30) is True
    assert sum(throttle.ready(i / 1000) for i in range(100, 1100)) == pytest.approx(30, abs=1)


def test_cadence_invalide() -> None:
    with pytest.raises(ValueError, match="rate"):
        Throttle(0)


# --- Structure ----------------------------------------------------------------------------


def test_pivy_dans_un_seul_module_du_glissement() -> None:
    drag = PACKAGE / "gui" / "drag"
    users = [
        path.name for path in sorted(drag.glob("*.py")) if "pivy.coin" in imported_modules(path)
    ]
    assert users == ["overlay.py"]


def test_geometrie_du_glissement_sans_freecad_ni_qt() -> None:
    modules = imported_modules(PACKAGE / "gui" / "drag" / "geometry.py")
    forbidden = {"FreeCAD", "FreeCADGui", "PySide", "pivy", "pivy.coin", "Part"}
    assert forbidden.isdisjoint(modules)


def _calls(path: str, method: str, owner: str | None = None) -> list[str]:
    tree = ast.parse((PACKAGE / path).read_text(encoding="utf-8"))
    scope = next(n for n in ast.walk(tree) if isinstance(n, ast.ClassDef) and n.name == owner)
    node = next(
        n
        for n in ast.walk(scope if owner else tree)
        if isinstance(n, ast.FunctionDef) and n.name == method
    )
    return [ast.unparse(c.func) for c in ast.walk(node) if isinstance(c, ast.Call)]


def test_filtre_pose_a_l_activation_et_retire_a_la_desactivation() -> None:
    assert "events.install" in _calls("init_gui.py", "Activated", "MenuiserieWorkbench")
    assert "events.uninstall" in _calls("init_gui.py", "Deactivated", "MenuiserieWorkbench")
    assert "double_click.install" in _calls("init_gui.py", "Activated", "MenuiserieWorkbench")


def test_observateur_de_selection_retire_avec_le_filtre() -> None:
    events = "gui/drag/events.py"
    assert "Gui.Selection.addObserver" in _calls(events, "install", "_Installation")
    assert "Gui.Selection.removeObserver" in _calls(events, "uninstall", "_Installation")
    assert "application.installEventFilter" in _calls(events, "install", "_Installation")
    assert "application.removeEventFilter" in _calls(events, "uninstall", "_Installation")
