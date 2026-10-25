# SPDX-License-Identifier: LGPL-2.1-or-later
"""Cas limites de ``core/magnet`` (SM-a) : tolérance, axes, bornes, rayon parallèle, saisie."""

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
    axis_param,
    handle_at,
    magnet,
    resize,
)

BOX = Box.from_ranges([(0, 10), (0, 10), (0, 10)])
WIDE = (0.0, 1000.0)


def plane(axis: int, position: float, sign: int = -1) -> Guide:
    ranges = [WIDE, WIDE, WIDE]
    ranges[axis] = (position, position)
    return Guide(GuideKind.PLANE, Box.from_ranges(ranges), axis, sign)


def point(x: float) -> Guide:
    return Guide(GuideKind.POINT, Box(Vec3(x, 5, 5), Vec3(x, 5, 5)))


def test_tolerance_incluse_et_bornee() -> None:
    guide = plane(0, 20)
    assert magnet(BOX, [guide], Vec3(8, 0, 0), 2, (0,)).hits  # écart 2 = tolérance : collé
    assert not magnet(BOX, [guide], Vec3(7.99, 0, 0), 2, (0,)).hits
    assert magnet(BOX, [guide], Vec3(10, 0, 0), 0, (0,)).hits  # contact exact, tolérance nulle
    assert not magnet(BOX, [guide], Vec3(9.99, 0, 0), 0, (0,)).hits


@pytest.mark.parametrize("tolerance", [-1.0, math.nan, math.inf])
def test_tolerance_invalide_refusee(tolerance: float) -> None:
    with pytest.raises(ValueError, match="tolerance"):
        magnet(BOX, [], Vec3(0, 0, 0), tolerance, (0,))
    with pytest.raises(ValueError, match="tolerance"):
        resize(BOX, Handle(0, True), 1, [], tolerance)


def test_axes_en_double_ou_vides() -> None:
    guide = plane(0, 20)
    assert len(magnet(BOX, [guide], Vec3(9, 0, 0), 5, (0, 0)).hits) == 1
    assert magnet(BOX, [guide], Vec3(9, 0, 0), 5, ()).delta == Vec3(9, 0, 0)


@pytest.mark.xfail(strict=True, raises=IndexError, reason="axe 3 non validé dans magnet()")
def test_axe_inexistant_refuse_proprement() -> None:
    with pytest.raises(ValueError, match="axe"):
        magnet(BOX, [plane(0, 20)], Vec3(0, 0, 0), 1, (3,))


def test_deja_en_contact_ne_bouge_pas() -> None:
    result = magnet(BOX, [plane(0, 10)], Vec3(0, 0, 0), 1, (0,))
    assert result.delta == Vec3(0, 0, 0)
    assert result.hits[0].kind is MagnetKind.CONTACT


@pytest.mark.parametrize(("delta", "guide_x"), [(-1.0, -2.0), (11.9, 22.0)])
def test_un_sommet_donne_toujours_un_contact(delta: float, guide_x: float) -> None:
    hits = magnet(BOX, [point(guide_x)], Vec3(delta, 0, 0), 3, (0,)).hits
    assert [h.kind for h in hits] == [MagnetKind.CONTACT]


def test_boite_plus_mince_que_la_tolerance_prend_la_face_la_plus_proche() -> None:
    thin = Box.from_ranges([(0, 1), (0, 10), (0, 10)])
    result = magnet(thin, [plane(0, 4)], Vec3(0, 0, 0), 10, (0,))
    assert result.hits[0].at_end is True
    assert result.delta.x == pytest.approx(3.0)


def test_grandes_coordonnees() -> None:
    far = 1e9
    result = magnet(BOX, [plane(0, far + 10)], Vec3(far, 0, 0), 1, (0,))
    assert result.hits
    assert result.delta.x == pytest.approx(far)


@pytest.mark.parametrize("delta", [math.nan, math.inf])
def test_resize_delta_non_fini_refuse(delta: float) -> None:
    with pytest.raises(ValueError, match="fini"):
        resize(BOX, Handle(0, True), delta, [], 1)


@pytest.mark.parametrize("minimum", [0.0, -1.0, math.nan])
def test_resize_minimum_invalide_refuse(minimum: float) -> None:
    with pytest.raises(ValueError, match="minimum"):
        resize(BOX, Handle(0, True), 1, [], 1, minimum)


def test_resize_borne_l_emporte_sur_l_aimant_pour_la_poignee_de_debut() -> None:
    result = resize(BOX, Handle(0, False), 20, [plane(0, 10.5, sign=1)], 5)
    assert result.size == pytest.approx(1.0)
    assert result.origin_shift.x == pytest.approx(9.0)
    assert result.hit is None


def test_resize_ignore_un_guide_hors_de_portee_sur_les_autres_axes() -> None:
    far = Guide(GuideKind.PLANE, Box.from_ranges([(15, 15), (50, 60), (0, 10)]), 0, -1)
    assert resize(BOX, Handle(0, True), 5, [far], 1).hit is None


def test_resize_delta_nul_ne_change_rien() -> None:
    result = resize(BOX, Handle(1, True), 0, [], 1)
    assert (result.size, result.origin_shift, result.hit) == (10.0, Vec3(0, 0, 0), None)


def test_axis_param_rayon_parallele_ou_oppose() -> None:
    axis = Ray(Vec3(5, 0, 0), Vec3(0, 0, 1))
    assert axis_param(Ray(Vec3(0, 0, 0), Vec3(0, 0, -1)), axis) is None
    assert axis_param(Ray(Vec3(0, 0, 0), Vec3(1e-7, 0, 1)), axis) is None
    assert axis_param(Ray(Vec3(0, 0, 0), Vec3(1e-3, 0, 1)), axis) is not None


def test_axis_param_change_de_signe_avec_le_sens_de_l_axe() -> None:
    ray = Ray(Vec3(0, 3, 7), Vec3(1, 0, 0))
    assert axis_param(ray, Ray(Vec3(0, 0, 0), Vec3(0, 1, 0))) == pytest.approx(3.0)
    assert axis_param(ray, Ray(Vec3(0, 0, 0), Vec3(0, -1, 0))) == pytest.approx(-3.0)


def test_handle_at_rayon_nul_et_egalite_de_poignees() -> None:
    assert handle_at([PixelTarget("a", (1, 1))], (1, 1), 0) == "a"
    assert handle_at([PixelTarget("a", (1, 1))], (1, 1.1), 0) is None
    assert handle_at([PixelTarget("a", (1, 1))], (1, 1), -1) is None
    twins = [PixelTarget("a", (0, 0)), PixelTarget("b", (0, 0))]
    assert handle_at(twins, (0, 0)) == "a"


def test_pixel_target_invalide() -> None:
    with pytest.raises(ValueError, match="clé"):
        PixelTarget("", (0, 0))
    with pytest.raises(ValueError, match="finies"):
        PixelTarget("a", (0, math.nan))


@pytest.mark.xfail(strict=True, reason="curseur NaN : handle_at saisit la première cible")
def test_handle_at_curseur_non_fini_ne_saisit_rien() -> None:
    assert handle_at([PixelTarget("a", (0, 0))], (math.nan, math.nan)) is None
