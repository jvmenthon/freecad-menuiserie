# SPDX-License-Identifier: LGPL-2.1-or-later
"""Glisser à la souris, partie pure de l'interface (SM-c, ``gui/drag/drawing.py``) : clés des
flèches et poignées, rayon, disposition, dessin, cadence ; et garde-fous de structure (pivy dans
un seul module, filtre posé et retiré avec l'atelier)."""

from __future__ import annotations

import ast
from dataclasses import replace

import pytest

from freecad.menuiserie.core.geometry import Box, Vec3
from freecad.menuiserie.core.magnet import Guide, GuideKind, Handle, handle_at, mouse_ray
from freecad.menuiserie.core.snap import Frame
from freecad.menuiserie.gui.drag.drawing import (
    GUIDE_COLOR,
    HANDLE_COLOR,
    HOVER_COLOR,
    LOCKED_COLOR,
    BadgeState,
    Throttle,
    arrow_key,
    badge_angles,
    build_drawing,
    build_layout,
    guide_outline,
    handle_key,
    is_locked_key,
    locked_blocker,
    locked_key,
    parse_key,
    pixel_targets,
    size_text,
    target_line,
    tooltip_html,
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
    assert [b.state for b in drawing.badges] == [BadgeState.NORMAL, BadgeState.HOVER]
    assert drawing.solids == ()


def test_poignee_dessinee_en_etiquette_de_cote() -> None:
    """ADR 0068 : une étiquette par poignée, devant sa face, reliée par un trait au milieu de la
    face ; elle porte la cote de son axe."""
    layout = build_layout(FRAME, BOX, 100.0, frozenset(), frozenset({1}))
    drawing = build_drawing(layout)
    leaders = [s for s in drawing.strokes if s.color == HANDLE_COLOR]
    assert len(leaders) == 2 and all(len(s.lines) == 1 for s in leaders)
    (start, end) = leaders[1].lines[0]  # poignée de fin de l'axe Y, centrée sur sa face
    assert (start.x, end.x, start.z, end.z) == (410, 410, 41, 41)
    assert (start.y, end.y) == pytest.approx((220, 220 + 57))  # 1,9 fois 30 % des 100 mm
    first = leaders[0].lines[0]
    assert (first[0].y, first[1].y) == pytest.approx((20, 20 - 57))  # début : vers l'extérieur
    assert [b.position for b in drawing.badges] == [first[1], end]
    assert [b.text for b in drawing.badges] == ["200", "200"]
    assert [d.points for d in drawing.dots] == [(p,) for _, p in layout.handles]
    assert drawing.solids == ()


def test_etiquette_a_distance_constante_a_l_ecran() -> None:
    def reach(size_mm: float, scale: float = 1.0) -> float:
        layout = build_layout(FRAME, BOX, size_mm, frozenset(), frozenset({0}))
        layout = replace(layout, badge_scale=scale)
        badge = build_drawing(layout).badges[1]
        return badge.position.x - 810

    assert reach(200.0) == pytest.approx(2 * reach(100.0))  # suit l'échelle des flèches
    assert reach(100.0, 2.0) == pytest.approx(2 * reach(100.0))  # écran haute définition


def test_cote_ecrite_sur_l_etiquette() -> None:
    assert size_text(Box.from_ranges([(0, 680), (0, 0.25), (0, 19.04)]), 0) == "680"
    assert size_text(Box.from_ranges([(0, 680), (0, 380.46), (0, 19)]), 1) == "380.5"
    assert size_text(Box.from_ranges([(0, 680), (0, 380), (0, 19.04)]), 2) == "19"
    # Document retouché : cote démesurée (une boîte est toujours finie), pas d'étiquette géante.
    assert size_text(Box.from_ranges([(0, 1e12), (0, 1), (0, 1)]), 0) == "?"


def test_zone_de_saisie_des_poignees() -> None:
    """Milieu de la face, étiquette (segment horizontal, tolérance de sa demi-hauteur) et trait
    qui les relie."""
    layout = build_layout(FRAME, BOX, 100.0, frozenset(), frozenset({0}))
    targets = pixel_targets(layout, project)
    mine = [t for t in targets if t.key == handle_key(Handle(0, True))]
    assert [(t.start, t.end, t.radius) for t in mine] == [
        ((810, 120), None, None),
        ((867 - 21, 120), (867 + 21, 120), 12.0),  # 66 sur 24 pixels : 33 - 12 de chaque côté
        ((810, 120), (867, 120), None),
    ]
    key = handle_key(Handle(0, True))
    assert handle_at(targets, (867 + 28, 120 + 8)) == key  # bord droit de l'étiquette
    assert handle_at(targets, (867, 120 + 13)) is None  # au-dessus de l'étiquette


# --- Poignées impossibles (ADR 0068) -----------------------------------------------------

BLOCKER = ("Épaisseur non modifiable", "Un panneau garde son épaisseur : 19 mm.", "→ Changer")


def test_poignees_impossibles_grisees() -> None:
    layout = build_layout(FRAME, BOX, 100.0, frozenset(), frozenset({0, 1}), [(2, BLOCKER)])
    assert [(h.axis, h.at_end) for h, _, _ in layout.locked] == [(2, False), (2, True)]
    assert {b for _, _, b in layout.locked} == {BLOCKER}
    drawing = build_drawing(layout)
    states = [b.state for b in drawing.badges]
    assert states == [BadgeState.NORMAL] * 4 + [BadgeState.LOCKED] * 2
    assert [b.text for b in drawing.badges][-2:] == ["22", "22"]
    assert [s.color for s in drawing.strokes][-2:] == [LOCKED_COLOR, LOCKED_COLOR]
    key = locked_key(Handle(2, True))
    hovered = build_drawing(layout, hover=key)
    assert hovered.badges[-1].state == BadgeState.LOCKED_HOVER
    assert locked_blocker(layout, key) == BLOCKER
    assert locked_blocker(layout, handle_key(Handle(0, True))) is None
    assert locked_blocker(layout, None) is None


def test_poignee_impossible_survolable_mais_jamais_saisie() -> None:
    layout = build_layout(FRAME, BOX, 100.0, frozenset(), frozenset(), [(0, BLOCKER)])
    targets = pixel_targets(layout, project)
    key = locked_key(Handle(0, True))
    assert handle_at(targets, (867, 120)) == key
    assert is_locked_key(key) and not is_locked_key(handle_key(Handle(0, True)))
    with pytest.raises(ValueError, match="inconnue"):
        parse_key(key)
    with pytest.raises(ValueError, match="inconnue"):
        target_line(layout, key)


def test_axe_tirable_jamais_grise() -> None:
    layout = build_layout(FRAME, BOX, 100.0, frozenset(), frozenset({0}), [(0, BLOCKER)])
    assert layout.locked == ()


def test_infobulle_echappee() -> None:
    text = tooltip_html(("<b>Titre</b>", "a & b", "→ piste"))
    assert text == "<b>&lt;b&gt;Titre&lt;/b&gt;</b><br>a &amp; b<br><i>→ piste</i>"


def test_direction_des_etiquettes_a_l_ecran() -> None:
    layout = build_layout(FRAME, BOX, 100.0, frozenset(), frozenset({0, 1, 2}))
    angles = badge_angles(layout, project)
    # X : début vers la gauche (180°), fin vers la droite (0°) ; Y : 270° puis 90° ;
    # Z vu de bout (vue de dessus) : 0°.
    assert angles == (180.0, 0.0, 270.0, 90.0, 0.0, 0.0)
    tilted = badge_angles(layout, lambda p: (p.x + 0.6 * p.y, p.y))
    assert tilted[3] == 60.0  # 59° arrondi au pas de 5°


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
    modules = imported_modules(PACKAGE / "gui" / "drag" / "drawing.py")
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


@pytest.mark.parametrize(
    ("panel", "name"),
    [("wood_part", "WoodPartTaskPanel"), ("shaped_part", "ShapedPartTaskPanel")],
)
def test_panneau_de_chaque_piece_branche_la_session_du_glissement(panel: str, name: str) -> None:
    """Sans ``PanelDrag``, la session voit un panneau d'une autre commande ouvert et masque les
    flèches de la pièce (recette de jv : pièce en bois issue d'une forme Part, dont le panneau
    s'ouvre à la conversion)."""
    path = f"gui/task_panels/{panel}.py"
    assert "PanelDrag" in _calls(path, "__init__", name)
    assert _calls(path, "after_drag", name) is not None
