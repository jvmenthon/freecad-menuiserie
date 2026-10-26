# SPDX-License-Identifier: LGPL-2.1-or-later
"""Glissement à la souris (SM-a, critères A1 à A8) : règles pures de ``core/magnet/``."""

from __future__ import annotations

import math

import pytest

from freecad.menuiserie.core.geometry import Box, Vec3
from freecad.menuiserie.core.magnet import (
    Guide,
    GuideKind,
    Handle,
    MagnetKind,
    PixelTarget,
    Ray,
    arrows,
    axis_param,
    handle_at,
    magnet,
    mm_per_pixel,
    resize,
)
from freecad.menuiserie.core.snap import Frame
from tests.unit.aides import ROOT, imported_modules

BOX = Box.from_ranges([(0, 100), (0, 50), (0, 20)])
WIDE = (0.0, 1000.0)
ALL = (0, 1, 2)
MAGNET_PACKAGE = ROOT / "freecad" / "menuiserie" / "core" / "magnet"


def plane(axis: int, position: float, sign: int = -1) -> Guide:
    """Plan infini en pratique (étendue large) normal à ``axis``."""
    ranges = [WIDE, WIDE, WIDE]
    ranges[axis] = (position, position)
    return Guide(GuideKind.PLANE, Box.from_ranges(ranges), axis, sign)


def point(x: float, y: float, z: float) -> Guide:
    return Guide(GuideKind.POINT, Box(Vec3(x, y, z), Vec3(x, y, z)))


def line(axis: int, fixed: tuple[float, float], span: tuple[float, float] = WIDE) -> Guide:
    """Droite parallèle à ``axis`` passant par ``fixed`` sur les deux autres axes."""
    others = [i for i in range(3) if i != axis]
    ranges = [(0.0, 0.0)] * 3
    ranges[axis] = span
    ranges[others[0]] = (fixed[0], fixed[0])
    ranges[others[1]] = (fixed[1], fixed[1])
    return Guide(GuideKind.LINE, Box.from_ranges(ranges), axis)


def delta(x: float = 0.0, y: float = 0.0, z: float = 0.0) -> Vec3:
    return Vec3(x, y, z)


# --- A1 : flèches ---------------------------------------------------------------------------


def test_a1_arrows_follow_the_piece_axes_from_its_center() -> None:
    """A1 : trois flèches de longueur ``size`` selon X, Y, Z de la pièce, depuis le centre."""
    frame = Frame(Vec3(10, 20, 30), Vec3(1, 0, 0), Vec3(0, 1, 0), Vec3(0, 0, 1))
    x, y, z = arrows(frame, BOX, 80)
    assert (x.axis, y.axis, z.axis) == (0, 1, 2)
    assert x.start == y.start == z.start == Vec3(60, 45, 40)
    assert x.end == Vec3(140, 45, 40)
    assert y.end == Vec3(60, 125, 40)
    assert z.end == Vec3(60, 45, 120)


def test_a1_arrows_of_a_turned_piece_are_turned() -> None:
    """A1 : pièce tournée de 90° autour de Z, la flèche X part vers +Y global."""
    frame = Frame(Vec3(0, 0, 0), Vec3(0, 1, 0), Vec3(-1, 0, 0), Vec3(0, 0, 1))
    x, y, _ = arrows(frame, BOX, 10)
    assert x.start == Vec3(-25, 50, 10)
    assert x.end == Vec3(-25, 60, 10)
    assert y.end == Vec3(-35, 50, 10)


@pytest.mark.parametrize("size", [0.0, -5.0, math.nan, math.inf])
def test_a1_arrow_length_must_be_positive(size: float) -> None:
    frame = Frame(Vec3(0, 0, 0), Vec3(1, 0, 0), Vec3(0, 1, 0), Vec3(0, 0, 1))
    with pytest.raises(ValueError, match="size"):
        arrows(frame, BOX, size)


# --- A2 : point de l'axe le plus proche du rayon ---------------------------------------------


def test_a2_axis_param_is_the_closest_point_of_the_axis() -> None:
    """A2 : le rayon vertical passant au-dessus de x = 30 donne le paramètre 30."""
    axis = Ray(Vec3(0, 0, 0), Vec3(1, 0, 0))
    ray = Ray(Vec3(30, 7, 100), Vec3(0, 0, -1))
    assert axis_param(ray, axis) == pytest.approx(30.0)


def test_a2_axis_param_with_oblique_ray_and_negative_side() -> None:
    """A2 : paramètre mesuré le long de l'axe orienté, négatif derrière l'origine."""
    axis = Ray(Vec3(10, 0, 0), Vec3(0, 2, 0))  # direction normée à la construction
    ray = Ray(Vec3(10, -40, 5), Vec3(1, 0, -1))
    assert axis_param(ray, axis) == pytest.approx(-40.0)


def test_a2_ray_parallel_to_the_axis_gives_none() -> None:
    """A2 : rayon parallèle (même sens ou contraire) ou presque → ``None``."""
    axis = Ray(Vec3(0, 0, 0), Vec3(1, 0, 0))
    assert axis_param(Ray(Vec3(0, 5, 5), Vec3(1, 0, 0)), axis) is None
    assert axis_param(Ray(Vec3(0, 5, 5), Vec3(-3, 0, 0)), axis) is None
    assert axis_param(Ray(Vec3(0, 5, 5), Vec3(1, 1e-9, 0)), axis) is None
    assert axis_param(Ray(Vec3(0, 5, 5), Vec3(1, 1e-3, 0)), axis) is not None


def test_a2_ray_needs_a_direction() -> None:
    with pytest.raises(ValueError, match="direction"):
        Ray(Vec3(0, 0, 0), Vec3(0, 0, 0))


# --- A3 : aimantation par axe ----------------------------------------------------------------


def test_a3_nearest_face_snaps_to_guide_within_tolerance() -> None:
    """A3 : la face de fin (x = 105) se colle au plan x = 110 (déplacement corrigé à 10)."""
    result = magnet(BOX, [plane(0, 110)], delta(5), 10, ALL)
    assert result.delta.x == pytest.approx(10.0)
    assert [(h.axis, h.at_end, h.position) for h in result.hits] == [(0, True, 110.0)]


def test_a3_start_face_can_snap_too() -> None:
    """A3 : la face de début (x = -3) se colle au plan x = 0."""
    result = magnet(BOX, [plane(0, 0)], delta(-3), 5, ALL)
    assert result.delta.x == pytest.approx(0.0)
    assert result.hits[0].at_end is False


def test_a3_no_guide_in_range_leaves_delta_unchanged() -> None:
    """A3 : aucun guide à moins de la tolérance → ``delta`` inchangé, aucun résultat."""
    result = magnet(BOX, [plane(0, 500)], delta(5, 1, 2), 10, ALL)
    assert result.delta == delta(5, 1, 2)
    assert result.hits == ()
    assert magnet(BOX, [], delta(5), 10, ALL).delta == delta(5)


def test_a3_axes_are_independent_and_restricted_to_axes_argument() -> None:
    """A3 : deux axes s'aimantent chacun de leur côté ; ``axes`` limite le calcul."""
    guides = [plane(0, 110), plane(1, 53)]
    both = magnet(BOX, guides, delta(7, 1), 5, ALL)
    assert both.delta.x == pytest.approx(10.0)
    assert both.delta.y == pytest.approx(3.0)
    only_x = magnet(BOX, guides, delta(7, 1), 5, (0,))
    assert only_x.delta.y == pytest.approx(1.0)
    assert [h.axis for h in only_x.hits] == [0]


def test_a3_nearest_of_two_guides_wins() -> None:
    """A3 : deux guides à portée, la face va au plus proche."""
    result = magnet(BOX, [plane(0, 112), plane(0, 108)], delta(5), 10, (0,))
    assert result.delta.x == pytest.approx(8.0)
    assert result.hits[0].guide == 1


def test_a3_tie_goes_to_guide_nearest_the_cursor_then_first() -> None:
    """A3 : égalité de distance → guide le plus proche du curseur (centre de la boîte), puis le
    premier."""
    # Face de fin à x = 100 ; guides à 95 et 105 (écart 5 des deux côtés). Centre à x = 50 : le
    # guide à 95 est le plus proche.
    result = magnet(BOX, [plane(0, 105), plane(0, 95)], delta(), 10, (0,))
    assert result.hits[0].guide == 1
    assert result.delta.x == pytest.approx(-5.0)
    # Deux guides confondus : le premier.
    twins = magnet(BOX, [plane(0, 105), plane(0, 105)], delta(), 10, (0,))
    assert twins.hits[0].guide == 0


# --- A4 : types de guides et portée ----------------------------------------------------------


def test_a4_plane_only_snaps_parallel_faces() -> None:
    """A4 : un plan x = 110 n'aimante que l'axe X, même si une face Y en est proche."""
    guide = plane(0, 52)  # proche de la face de fin en Y (50), mais normal à X
    result = magnet(BOX, [guide], delta(), 5, ALL)
    assert result.hits == ()
    assert result.delta == delta()


def test_a4_line_snaps_the_two_perpendicular_axes() -> None:
    """A4 : une droite parallèle à Z aimante X et Y, pas Z."""
    guide = line(2, (104, 53))
    result = magnet(BOX, [guide], delta(), 5, ALL)
    assert sorted(h.axis for h in result.hits) == [0, 1]
    assert result.delta.x == pytest.approx(4.0)
    assert result.delta.y == pytest.approx(3.0)
    assert result.delta.z == 0.0


def test_a4_point_snaps_the_three_axes() -> None:
    """A4 : un sommet aimante X, Y et Z."""
    result = magnet(BOX, [point(103, 52, 22)], delta(), 5, ALL)
    assert sorted(h.axis for h in result.hits) == [0, 1, 2]
    assert result.delta == Vec3(3, 2, 2)


def test_a4_guide_out_of_reach_on_other_axes_is_ignored() -> None:
    """A4 : plan voisin (recouvrement des étendues) retenu, plan d'un autre meuble ignoré."""
    near = Guide(GuideKind.PLANE, Box.from_ranges([(110, 110), (0, 50), (0, 20)]), 0, -1)
    far = Guide(GuideKind.PLANE, Box.from_ranges([(110, 110), (900, 950), (0, 20)]), 0, -1)
    assert magnet(BOX, [near], delta(), 15, (0,)).hits
    assert magnet(BOX, [far], delta(), 15, (0,)).hits == ()
    # Une marge de tolérance sur les autres axes suffit.
    edge = Guide(GuideKind.PLANE, Box.from_ranges([(110, 110), (52, 80), (0, 20)]), 0, -1)
    assert magnet(BOX, [edge], delta(), 15, (0,)).hits
    assert magnet(BOX, [edge], delta(), 1, (0,)).hits == ()


def test_a4_point_out_of_reach_is_ignored() -> None:
    assert magnet(BOX, [point(103, 500, 10)], delta(), 5, ALL).hits == ()


@pytest.mark.parametrize(
    "build",
    [
        lambda: Guide(GuideKind.PLANE, BOX, 0, -1),  # plan non aplati
        lambda: Guide(GuideKind.PLANE, Box.from_ranges([(1, 1), WIDE, WIDE]), 0, 0),  # sans sens
        lambda: Guide(GuideKind.LINE, BOX, 2),  # droite non aplatie
        lambda: Guide(GuideKind.LINE, Box.from_ranges([(1, 1), (1, 1), WIDE])),  # sans axe
        lambda: Guide(GuideKind.POINT, BOX),  # point étendu
    ],
)
def test_a4_invalid_guides_are_refused(build) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(ValueError, match="Guide"):
        build()


# --- A5 : contact et affleurement ------------------------------------------------------------


def test_a5_contact_when_normals_are_opposite() -> None:
    """A5 : la face de début (normale -X) contre une face voisine de normale +X → contact."""
    result = magnet(BOX, [plane(0, 0, sign=1)], delta(-3), 5, (0,))
    assert result.hits[0].kind is MagnetKind.CONTACT
    # La face de fin (+X) contre une face de normale -X : contact aussi.
    end = magnet(BOX, [plane(0, 100, sign=-1)], delta(3), 5, (0,))
    assert end.hits[0].kind is MagnetKind.CONTACT


def test_a5_flush_when_normals_have_the_same_direction() -> None:
    """A5 : la face de fin (+X) alignée sur une face voisine de normale +X → affleurement."""
    result = magnet(BOX, [plane(0, 100, sign=1)], delta(3), 5, (0,))
    assert result.hits[0].kind is MagnetKind.FLUSH
    start = magnet(BOX, [plane(0, 0, sign=-1)], delta(-3), 5, (0,))
    assert start.hits[0].kind is MagnetKind.FLUSH


def test_a5_both_are_valid_candidates() -> None:
    """A5 : un plan peut aimanter les deux faces ; la plus proche gagne, quel que soit le type."""
    guide = plane(0, 60, sign=1)
    near_start = magnet(BOX, [guide], delta(57), 5, (0,))  # début à 57 → 60 (normales opposées)
    assert near_start.hits[0].kind is MagnetKind.CONTACT
    near_end = magnet(BOX, [guide], delta(-37), 5, (0,))  # fin à 63 → 60 (même sens)
    assert near_end.hits[0].kind is MagnetKind.FLUSH


# --- A6 : redimensionnement ------------------------------------------------------------------


def test_a6_end_handle_moves_only_its_face() -> None:
    """A6 : tirer la face de fin de X de +30 → cote 130, origine inchangée."""
    result = resize(BOX, Handle(0, True), 30, [], 5)
    assert result.size == pytest.approx(130.0)
    assert result.origin_shift == Vec3(0, 0, 0)
    assert result.hit is None


def test_a6_start_handle_shifts_the_origin() -> None:
    """A6 : tirer la face de début de Y de -20 → cote 70, origine décalée de -20."""
    result = resize(BOX, Handle(1, False), -20, [], 5)
    assert result.size == pytest.approx(70.0)
    assert result.origin_shift == Vec3(0, -20, 0)


def test_a6_resize_snaps_the_moved_face() -> None:
    """A6 : la face tirée s'aimante au guide ; les autres faces ne bougent pas."""
    result = resize(BOX, Handle(0, True), 27, [plane(0, 130)], 5)
    assert result.size == pytest.approx(130.0)
    assert result.hit is not None
    assert result.hit.position == 130.0


def test_a6_size_is_bounded_to_the_minimum() -> None:
    """A6 : la cote ne descend pas sous 1 mm ; l'origine suit pour la poignée de début."""
    end = resize(BOX, Handle(0, True), -500, [], 5)
    assert end.size == pytest.approx(1.0)
    start = resize(BOX, Handle(0, False), 500, [], 5)
    assert start.size == pytest.approx(1.0)
    assert start.origin_shift.x == pytest.approx(99.0)
    custom = resize(BOX, Handle(1, True), -500, [], 5, minimum=4)
    assert custom.size == pytest.approx(4.0)


def test_a6_bound_wins_over_a_guide_behind_it() -> None:
    """A6 : un aimant au-delà de la borne ne la franchit pas."""
    result = resize(BOX, Handle(0, True), -99.5, [plane(0, -50)], 200)
    assert result.size >= 1.0


def test_a6_thickness_handle_is_no_longer_refused() -> None:
    """A6 (amendé le 2026-10-26, Q4) : l'épaisseur (axe Z) se redimensionne comme les autres axes ;
    c'est ``drag_limits`` qui décide de la poignée (massif seulement)."""
    end = resize(BOX, Handle(2, True), 5, [], 5)
    assert end.size == pytest.approx(BOX.size(2) + 5)
    assert end.origin_shift == Vec3(0, 0, 0)
    start = resize(BOX, Handle(2, False), -4, [], 5)
    assert start.size == pytest.approx(BOX.size(2) + 4)
    assert start.origin_shift == Vec3(0, 0, -4)


def test_a6_thickness_keeps_the_minimum_and_snaps() -> None:
    """A6 : la borne de 1 mm et l'aimant valent aussi pour l'épaisseur."""
    assert resize(BOX, Handle(2, True), -500, [], 5).size == pytest.approx(1.0)
    snapped = resize(BOX, Handle(2, True), 27, [plane(2, BOX.hi(2) + 30)], 5)
    assert snapped.size == pytest.approx(BOX.size(2) + 30)
    assert snapped.hit is not None


# --- A7 : saisie en pixels -------------------------------------------------------------------


def test_a7_nothing_within_radius_gives_none() -> None:
    """A7 : rien à moins de 8 pixels → ``None``."""
    targets = [PixelTarget("handle", (100, 100)), PixelTarget("arrow", (0, 0), (50, 0))]
    assert handle_at(targets, (300, 300)) is None
    assert handle_at([], (0, 0)) is None


def test_a7_handle_within_radius() -> None:
    """A7 : la poignée est saisie à 8 pixels (inclus), pas à 9."""
    targets = [PixelTarget("handle", (100, 100))]
    assert handle_at(targets, (108, 100)) == "handle"
    assert handle_at(targets, (109, 100)) is None
    assert handle_at(targets, (100, 100), radius=3) == "handle"


def test_a7_arrow_is_a_projected_segment() -> None:
    """A7 : toute la longueur de la flèche est saisissable, pas seulement ses extrémités."""
    targets = [PixelTarget("arrow", (0, 0), (80, 0))]
    assert handle_at(targets, (40, 6)) == "arrow"
    assert handle_at(targets, (40, 9)) is None
    assert handle_at(targets, (-5, 0)) == "arrow"
    assert handle_at(targets, (90, 0)) is None


def test_a7_nearest_target_wins() -> None:
    targets = [PixelTarget("a", (0, 0), (80, 0)), PixelTarget("b", (0, 0), (0, 80))]
    assert handle_at(targets, (40, 2)) == "a"
    assert handle_at(targets, (2, 40)) == "b"


def test_a7_handle_wins_a_tie_with_an_arrow() -> None:
    """A7 : à égalité de distance, la poignée l'emporte, même placée après la flèche."""
    targets = [PixelTarget("arrow", (0, 0), (80, 0)), PixelTarget("handle", (40, 5))]
    assert handle_at(targets, (40, 2.5)) == "handle"
    swapped = [PixelTarget("handle", (40, 5)), PixelTarget("arrow", (0, 0), (80, 0))]
    assert handle_at(swapped, (40, 2.5)) == "handle"


def test_a7_arrow_seen_end_on_is_not_grabbable() -> None:
    """A7 : flèche vue de bout (segment réduit à un point) → ignorée."""
    assert handle_at([PixelTarget("arrow", (10, 10), (10, 10))], (10, 10)) is None


# --- A8 : tolérance en mm --------------------------------------------------------------------


def test_a8_mm_per_pixel_scales_with_distance() -> None:
    """A8 : 10 pixels valent 10 fois la distance entre deux points voisins d'un pixel."""
    assert mm_per_pixel(Vec3(0, 0, 0), Vec3(0.5, 0, 0), 10) == pytest.approx(5.0)
    assert mm_per_pixel(Vec3(0, 0, 0), Vec3(0.3, 0.4, 0), 10) == pytest.approx(5.0)


@pytest.mark.parametrize("px", [0.0, -10.0, 10.0])
def test_a8_never_null_nor_negative(px: float) -> None:
    """A8 : points confondus, nombre de pixels nul ou négatif → toujours strictement positif."""
    same = Vec3(1, 2, 3)
    assert mm_per_pixel(same, same, px) > 0
    assert mm_per_pixel(Vec3(0, 0, 0), Vec3(2, 0, 0), px) > 0


def test_a8_non_finite_input_is_refused() -> None:
    with pytest.raises(ValueError, match="finies"):
        mm_per_pixel(Vec3(math.nan, 0, 0), Vec3(0, 0, 0), 10)


# --- pureté ----------------------------------------------------------------------------------


def test_core_magnet_imports_neither_freecad_nor_qt() -> None:
    """``core/magnet/`` reste du Python pur (règle FreeCAD n° 1)."""
    forbidden = ("FreeCAD", "FreeCADGui", "Part", "PySide", "PySide2", "PySide6", "pivy")
    for path in sorted(MAGNET_PACKAGE.glob("*.py")):
        modules = imported_modules(path, ROOT)
        assert not [m for m in modules if m.split(".")[0] in forbidden], path.name
