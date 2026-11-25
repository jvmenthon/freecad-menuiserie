# SPDX-License-Identifier: LGPL-2.1-or-later
"""Glisser à la souris, partie pure de l'interface (SM-c, ``gui/drag/drawing.py``) : clés des
flèches et poignées, rayon, disposition, dessin, cadence ; et garde-fous de structure (pivy dans
un seul module, filtre posé et retiré avec l'atelier)."""

from __future__ import annotations

import ast
import math
from dataclasses import replace

import pytest

from freecad.menuiserie.core.geometry import Box, Vec3
from freecad.menuiserie.core.magnet import Blocker, Guide, GuideKind, Handle, handle_at, mouse_ray
from freecad.menuiserie.core.snap import Frame
from freecad.menuiserie.core.text import mm_text
from freecad.menuiserie.gui.drag.badge_place import Slot, badge_width_px, facing_ends, spread
from freecad.menuiserie.gui.drag.drawing import (
    AXIS_COLORS,
    FACE_TRANSPARENCY,
    GUIDE_COLOR,
    HOVER_COLOR,
    LOCKED_COLOR,
    BadgeState,
    Layout,
    Throttle,
    arrow_key,
    build_drawing,
    build_layout,
    guide_outline,
    handle_key,
    is_locked_key,
    key_at,
    locked_blocker,
    locked_key,
    on_screen,
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


NAMES = ("Long.", "Larg.", "Ép.")


def named(layout: Layout) -> Layout:
    """Disposition avec les noms courts des cotes, comme ``PartTarget.layout`` la donne."""
    return replace(layout, axis_names=NAMES)


def test_surbrillance_de_la_cible_survolee() -> None:
    layout = named(build_layout(FRAME, BOX, 100.0, frozenset(), frozenset({0})))
    drawing = build_drawing(layout, hover=arrow_key(1))
    assert [s.color == HOVER_COLOR for s in drawing.strokes] == [False, True, False, False]
    assert drawing.solids == ()
    drawing = build_drawing(layout, hover=handle_key(Handle(0, True)))
    assert [d.size for d in drawing.dots] == [8.0, 11.0]  # rond de la face survolée grossi
    assert [b.state for b in drawing.badges] == [BadgeState.HOVER]
    (face,) = drawing.solids  # face qui bouge, à la couleur de son axe
    assert face.color == AXIS_COLORS[0] and face.transparency == FACE_TRANSPARENCY
    assert {p.x for p in face.faces[0]} == {810.0}
    start = build_drawing(layout, hover=handle_key(Handle(0, False)))
    assert {p.x for p in start.solids[0].faces[0]} == {10.0}  # face d'en face : son rond


def test_une_etiquette_par_cote() -> None:
    """ADR 0068 (maquette K) : une étiquette par cote, nommée, à la couleur de son axe, sur la
    face tournée vers la caméra (hors vue : face de fin) ; la face d'en face n'a qu'un rond."""
    layout = named(build_layout(FRAME, BOX, 100.0, frozenset(), frozenset({1})))
    drawing = build_drawing(layout)
    (badge,) = drawing.badges
    assert (badge.name, badge.text, badge.axis) == ("Larg.", "200", 1)
    (leader,) = [s for s in drawing.strokes if s.color == AXIS_COLORS[1] and len(s.lines) == 1]
    (start, end) = leader.lines[0]  # poignée de fin de l'axe Y, centrée sur sa face
    assert (start.x, end.x, start.z, end.z) == (410, 410, 41, 41)
    assert (start.y, end.y) == pytest.approx((220, 220 + 57))  # 1,9 fois 30 % des 100 mm
    assert badge.position == end
    assert [d.points for d in drawing.dots] == [(p,) for _, p in layout.handles]
    assert {d.color for d in drawing.dots} == {AXIS_COLORS[1]}
    back = build_drawing(replace(layout, badge_ends=frozenset()))  # face de début vers la vue
    assert back.badges[0].position.y == pytest.approx(20 - 57)


def test_etiquette_sur_la_face_vue() -> None:
    """La face de fin de l'axe porte l'étiquette si elle regarde la caméra."""
    axes = (FRAME.x, FRAME.y, FRAME.z)
    assert facing_ends(axes, Vec3(0, 0, -1)) == frozenset({0, 1, 2})  # vue de dessus
    assert facing_ends(axes, Vec3(-1, 1, -1)) == frozenset({0, 2})  # Y fin cachée
    layout = named(build_layout(FRAME, BOX, 100.0, frozenset(), frozenset({0, 1, 2})))
    placed = on_screen(layout, 2.0, project, Vec3(-1, 1, -1))
    assert placed.badge_scale == 2.0 and placed.badge_ends == frozenset({0, 2})
    assert [b.axis for b in build_drawing(placed).badges] == [0, 1, 2]


def test_etiquettes_ecartees_si_elles_se_touchent() -> None:
    """Deux étiquettes au même endroit à l'écran : la seconde recule le long de son axe."""
    one = Slot("a", (0.0, 0.0), (24.0, 0.0), 60.0, 24.0)  # une unité de poignée : 24 pixels
    two = Slot("b", (0.0, 5.0), (24.0, 0.0), 60.0, 24.0)
    far = Slot("c", (500.0, 500.0), (24.0, 0.0), 60.0, 24.0)
    reaches = dict(spread([one, two, far]))
    assert reaches["a"] == pytest.approx(1.9) and reaches["c"] == pytest.approx(1.9)
    assert reaches["b"] >= 1.9 + 64 / 24  # 64 pixels plus loin au moins : plus de contact
    stuck = Slot("d", (0.0, 0.0), (0.0, 0.0), 60.0, 24.0)  # vue de bout : ne s'écarte pas
    assert dict(spread([one, stuck]))["d"] == pytest.approx(1.9 + 6 * 0.8)


def test_etiquette_a_distance_constante_a_l_ecran() -> None:
    def reach(size_mm: float, scale: float = 1.0) -> float:
        layout = build_layout(FRAME, BOX, size_mm, frozenset(), frozenset({0}))
        layout = replace(layout, badge_scale=scale)
        badge = build_drawing(layout).badges[0]
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
    """Milieu de la face, étiquette (segment horizontal, tolérance de sa demi-hauteur, même
    largeur que son image) et trait qui les relie ; la face d'en face n'a que son milieu."""
    layout = named(build_layout(FRAME, BOX, 100.0, frozenset(), frozenset({0})))
    targets = pixel_targets(layout, project)
    mine = [t for t in targets if t.key == handle_key(Handle(0, True))]
    _, width = badge_width_px("Long.", "800", False)
    assert width == 90.0
    assert [(t.start, t.end, t.radius) for t in mine] == [
        ((810, 120), None, None),
        ((867 - 33, 120), (867 + 33, 120), 12.0),  # 90 sur 24 pixels : 45 - 12 de chaque côté
        ((810, 120), (867, 120), None),
    ]
    other = [t for t in targets if t.key == handle_key(Handle(0, False))]
    assert [(t.start, t.end) for t in other] == [((10, 120), None)]
    key = handle_key(Handle(0, True))
    assert handle_at(targets, (867 + 40, 120 + 8)) == key  # bord droit de l'étiquette
    assert handle_at(targets, (867, 120 + 13)) is None  # au-dessus de l'étiquette


# --- Poignées impossibles (ADR 0068) -----------------------------------------------------

BLOCKER = Blocker(
    "Épaisseur non modifiable", "Un panneau garde son épaisseur : 19 mm.", "→ Changer"
)


def test_poignees_impossibles_grisees() -> None:
    layout = build_layout(FRAME, BOX, 100.0, frozenset(), frozenset({0, 1}), [(2, BLOCKER)])
    assert [(h.axis, h.at_end) for h, _, _ in layout.locked] == [(2, False), (2, True)]
    assert {b for _, _, b in layout.locked} == {BLOCKER}
    drawing = build_drawing(layout)
    states = [b.state for b in drawing.badges]
    assert states == [BadgeState.NORMAL] * 2 + [BadgeState.LOCKED]
    assert [b.text for b in drawing.badges][-1] == "22"
    assert [s.color for s in drawing.strokes][-1] == LOCKED_COLOR
    assert [d.color for d in drawing.dots][-2:] == [LOCKED_COLOR, LOCKED_COLOR]
    key = locked_key(Handle(2, True))
    hovered = build_drawing(layout, hover=key)
    assert hovered.badges[-1].state == BadgeState.LOCKED_HOVER
    assert [s.color for s in hovered.solids] == [LOCKED_COLOR]  # face figée : grise
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


def test_etiquette_ne_cache_pas_une_fleche() -> None:
    """Pièce courte : la flèche X (de 70 à 170) passe sous le trait et l'étiquette de la poignée
    grisée de fin X (face à 130, étiquette centrée à 187, 40 pixels de large sans nom). À égalité
    de distance, la flèche l'emporte ; au centre de l'étiquette, l'étiquette."""
    box = Box.from_ranges([(0, 120), (0, 200), (0, 22)])
    layout = build_layout(FRAME, box, 100.0, frozenset(), frozenset(), [(0, BLOCKER)])
    targets = pixel_targets(layout, project)
    assert handle_at(targets, (150, 120)) == arrow_key(0)  # trait et flèche confondus
    assert handle_at(targets, (168, 120)) == arrow_key(0)  # étiquette et pointe confondues
    assert handle_at(targets, (187, 120)) == locked_key(Handle(0, True))
    # Recherche de la vue (key_at) : une poignée grisée ne cache jamais la flèche, même plus
    # proche qu'elle ; seule, elle reste survolable (infobulle).
    assert handle_at(targets, (176, 120)) == locked_key(Handle(0, True))  # sur l'étiquette
    assert key_at(layout, project, (176, 120), locked=False) == arrow_key(0)  # pointe à 6 px
    assert key_at(layout, project, (187, 120), locked=False) is None
    assert key_at(layout, project, (187, 120), locked=True) == locked_key(Handle(0, True))


def test_axe_tirable_jamais_grise() -> None:
    layout = build_layout(FRAME, BOX, 100.0, frozenset(), frozenset({0}), [(0, BLOCKER)])
    assert layout.locked == ()


def test_infobulle_echappee() -> None:
    text = tooltip_html(Blocker("<b>Titre</b>", "a & b", "→ piste"))
    assert text == "<b>&lt;b&gt;Titre&lt;/b&gt;</b><br>a &amp; b<br><i>→ piste</i>"


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


@pytest.mark.parametrize(
    ("value", "text"),
    [(19.0, "19"), (19.04, "19"), (380.46, "380.5"), (0.05, "0.1"), (math.inf, "?")],
)
def test_cote_en_millimetres(value: float, text: str) -> None:
    """Formatage commun à l'étiquette et à l'infobulle d'épaisseur (ADR 0068)."""
    assert mm_text(value) == text


def test_etat_d_une_etiquette_grisee() -> None:
    assert [s.locked for s in BadgeState] == [False, False, True, True]


# --- Étiquettes de cote : cas limites (revue testeur, ADR 0068 maquette K) --------------------


def iso(point: Vec3) -> tuple[float, float]:
    """Projection oblique de test : Y et Z fuient vers le haut à droite, 1 pixel = 1 mm."""
    return point.x + 0.5 * point.y, point.z + 0.5 * point.y + 0.3 * point.x


def test_axe_vu_de_bout_et_vue_exactement_de_face() -> None:
    """Direction de vue orthogonale à un axe : la face de fin compte comme visible (produit
    nul), aucune erreur, une seule étiquette par cote, les deux ronds restent là."""
    axes = (FRAME.x, FRAME.y, FRAME.z)
    assert facing_ends(axes, Vec3(0, 0, -1)) == frozenset({0, 1, 2})  # X et Y vus de la tranche
    assert facing_ends(axes, Vec3(1, 0, 0)) == frozenset({1, 2})  # X de bout, vu par sa fin
    assert facing_ends(axes, Vec3(0, 0, 0)) == frozenset({0, 1, 2})  # direction nulle : défaut
    layout = named(build_layout(FRAME, BOX, 100.0, frozenset(), FREE))

    def side(point: Vec3) -> tuple[float, float]:  # vue le long de X : les deux faces X confondues
        return point.y, point.z

    placed = on_screen(layout, 1.0, side, Vec3(-1, 0, 0))
    drawing = build_drawing(placed)
    assert sorted(b.axis for b in drawing.badges) == [0, 1, 2]
    assert sum(len(d.points) for d in drawing.dots) == 6
    assert all(math.isfinite(r) for _, r in placed.badge_reach)
    assert all(1.9 <= r <= 1.9 + 6 * 0.8 for _, r in placed.badge_reach)
    targets = pixel_targets(placed, side)  # étiquette d'un axe de bout : segment dégénéré admis
    assert handle_at(targets, (120 - 33, 41)) == handle_key(Handle(0, True))
    # Les deux faces X au même pixel : celle qui porte l'étiquette l'emporte (survol cohérent).
    face = side(dict(placed.handles)[Handle(0, True)])
    assert 0 in placed.badge_ends  # vue vers -X : face de fin étiquetée
    assert handle_at(targets, face) == handle_key(Handle(0, True))


def test_vue_degeneree_ou_bruitee() -> None:
    """Bruit flottant sur un axe vu par la tranche : l'étiquette ne saute pas d'une face à
    l'autre ; direction non finie : faces de fin ; projection ratée : recul par défaut."""
    axes = (FRAME.x, FRAME.y, FRAME.z)
    assert facing_ends(axes, Vec3(1e-17, 0, -1)) == facing_ends(axes, Vec3(-1e-17, 0, -1))
    assert facing_ends(axes, Vec3(math.nan, 0, -1)) == frozenset({0, 1, 2})
    bad = Slot("x", (math.inf, 0.0), (24.0, 0.0), 60.0, 24.0)
    good = Slot("y", (0.0, 0.0), (24.0, 0.0), 60.0, 24.0)
    assert spread([bad, good]) == (("y", 1.9),)


def test_etiquettes_ecartees_en_vue_oblique() -> None:
    """Pièce petite à l'écran, vue oblique : après l'écart, les étiquettes dessinées ne se
    touchent pas à l'écran (la mesure est celle de l'image, badge_width_px)."""
    box = Box.from_ranges([(0, 30), (0, 30), (0, 30)])
    layout = named(build_layout(FRAME, box, 20.0, frozenset(), FREE))
    placed = on_screen(layout, 1.0, iso, Vec3(-1, 1, -1))
    badges = build_drawing(placed).badges
    assert sorted(b.axis for b in badges) == [0, 1, 2]
    rects = []
    for badge in badges:
        width = badge_width_px(NAMES[badge.axis], badge.text, False)[1]
        x, y = iso(badge.position)
        rects.append((x - width / 2, y - 12, x + width / 2, y + 12))
    for i, one in enumerate(rects):
        for other in rects[i + 1 :]:
            apart = (
                one[2] <= other[0] or other[2] <= one[0] or one[3] <= other[1] or other[3] <= one[1]
            )
            assert apart
    assert any(r > 1.9 for _, r in placed.badge_reach)  # trop serrées sans écart


def test_ecart_vide_ou_isole() -> None:
    assert spread([]) == ()
    alone = Slot("a", (0.0, 0.0), (10.0, 0.0), 60.0, 24.0)
    assert spread([alone], base=3.0) == (("a", 3.0),)
    # Ordre conservé et déterministe : la première étiquette ne bouge jamais.
    again = Slot("b", (0.0, 0.0), (0.0, 10.0), 60.0, 24.0)
    assert spread([alone, again]) == spread([alone, again])
    assert dict(spread([again, alone]))["b"] == 1.9


def test_etiquette_figee_large_comme_son_image() -> None:
    """Zone de saisie d'une cote figée : largeur de badge_width_px avec cadenas, à l'échelle de
    l'écran haute définition ; une cote « ? » et un nom long suivent la même mesure."""
    _, plain = badge_width_px("Ép.", "22", False)
    _, locked = badge_width_px("Ép.", "22", True)
    assert locked == plain + 16.0
    long_name = badge_width_px("Épaisseur", "22", False)[1]
    assert long_name > plain and badge_width_px("Ép.", "?", False)[1] < plain + 1
    for scale in (1.0, 2.0):
        layout = replace(
            build_layout(FRAME, BOX, 100.0, frozenset(), frozenset(), [(2, BLOCKER)]),
            axis_names=NAMES,
            badge_scale=scale,
        )
        key = locked_key(Handle(2, True))
        zone = [t for t in pixel_targets(layout, project) if t.key == key and t.radius]
        (label,) = zone
        assert label.end is not None and label.radius == pytest.approx(12.0 * scale)
        assert label.end[0] - label.start[0] == pytest.approx(locked * scale - 24.0 * scale)
    drawing = build_drawing(layout)
    (badge,) = [b for b in drawing.badges if b.state is BadgeState.LOCKED]
    assert (badge.name, badge.axis, badge.scale) == ("Ép.", 2, 2.0)


def test_cote_inconnue_sur_l_etiquette() -> None:
    box = Box.from_ranges([(0, 1e12), (0, 200), (0, 22)])
    layout = named(build_layout(FRAME, box, 100.0, frozenset(), frozenset({0, 1})))
    drawing = build_drawing(layout)
    assert [(b.name, b.text) for b in drawing.badges] == [("Long.", "?"), ("Larg.", "200")]
    zone = [t for t in pixel_targets(layout, project) if t.key == handle_key(Handle(0, True))]
    assert zone and all(math.isfinite(t.start[0]) for t in zone)


def test_piece_sans_poignee() -> None:
    layout = named(build_layout(FRAME, BOX, 100.0, frozenset(), frozenset()))
    placed = on_screen(layout, 2.0, project, Vec3(0, 0, -1))
    assert placed.badge_reach == ()
    drawing = build_drawing(placed, hover=handle_key(Handle(0, True)))
    assert drawing.badges == () and drawing.solids == () and drawing.dots == ()
    assert [t.key for t in pixel_targets(placed, project)] == [arrow_key(a) for a in range(3)]


def test_survol_de_la_face_d_en_face_et_des_fleches() -> None:
    """Le rond de la face sans étiquette allume sa face ; une flèche n'allume aucune face."""
    layout = named(build_layout(FRAME, BOX, 100.0, frozenset(), FREE))
    drawing = build_drawing(layout, hover=handle_key(Handle(2, False)))
    assert [b.state for b in drawing.badges].count(BadgeState.HOVER) == 0  # pas d'étiquette là
    (face,) = drawing.solids
    assert face.color == AXIS_COLORS[2] and {p.z for p in face.faces[0]} == {30.0}
    assert len({(p.x, p.y) for p in face.faces[0]}) == 4  # quatre coins distincts
    assert build_drawing(layout, hover=arrow_key(2)).solids == ()
    assert build_drawing(layout, hover="inconnue").solids == ()
    assert build_drawing(layout, hover=None).solids == ()


def test_une_seule_etiquette_par_cote_avec_cote_figee() -> None:
    layout = named(build_layout(FRAME, BOX, 100.0, frozenset(), frozenset({0, 1}), [(2, BLOCKER)]))
    placed = on_screen(layout, 1.0, project, Vec3(0, 0, 1))  # vue de dessous : Z début visible
    assert 2 not in placed.badge_ends
    drawing = build_drawing(placed)
    assert sorted(b.axis for b in drawing.badges) == [0, 1, 2]
    (grey,) = [b for b in drawing.badges if b.axis == 2]
    assert grey.state is BadgeState.LOCKED and grey.position.z < 30  # côté de la face de début
    ends = {t.key for t in pixel_targets(placed, project) if t.radius}
    assert locked_key(Handle(2, False)) in ends and locked_key(Handle(2, True)) not in ends
