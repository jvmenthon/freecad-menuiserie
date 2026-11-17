# SPDX-License-Identifier: LGPL-2.1-or-later
"""Cas limites des profils sur une arête quelconque (ADR 0063, lot P-a, revue de test).

Bornes exactes des angles, jeu de l'angle droit, arête parcourue dans l'autre sens, cotes et
repères non finis, encombrement d'un quart de rond à angle aigu.
"""

from __future__ import annotations

import math

import pytest

from freecad.menuiserie.core.edges import (
    MAX_ANGLE_DEG,
    MIN_ANGLE_DEG,
    OVERSHOOT_MM,
    EdgeError,
    EdgeFamily,
    EdgeFrame,
    edge_cut_in_frame,
    frame_refusal,
)
from freecad.menuiserie.core.geometry import Vec3


def _arete(
    angle: float,
    *,
    room: float = 100.0,
    reverse: bool = False,
    extend_start: bool = True,
    extend_end: bool = True,
) -> EdgeFrame:
    """Arête de 200 mm sur l'axe Z (parcourue vers le bas si ``reverse``), première face le long
    de X, seconde face à ``angle`` degrés de la première."""
    alpha = math.radians(angle)
    return EdgeFrame(
        name="Edge3",
        start=Vec3(0.0, 0.0, 200.0 if reverse else 0.0),
        direction=Vec3(0.0, 0.0, -1.0 if reverse else 1.0),
        length=200.0,
        first=Vec3(1.0, 0.0, 0.0),
        second=Vec3(math.cos(alpha), math.sin(alpha), 0.0),
        convex=True,
        room_first=room,
        room_second=room,
        extend_start=extend_start,
        extend_end=extend_end,
    )


def _z_range(frame: EdgeFrame) -> tuple[float, float]:
    cut = edge_cut_in_frame(frame, EdgeFamily.CHAMFER, 2.0)
    zs = sorted(round(cut.point(0.0, 0.0, along).z, 9) for along in (0.0, cut.length))
    return zs[0], zs[1]


# --- A3 : bornes exactes ---------------------------------------------------------------------


@pytest.mark.parametrize("angle", [MIN_ANGLE_DEG, MAX_ANGLE_DEG])
def test_angles_aux_bornes_acceptes(angle: float) -> None:
    assert frame_refusal(_arete(angle), EdgeFamily.CHAMFER) is None
    cut = edge_cut_in_frame(_arete(angle), EdgeFamily.CHAMFER, 2.0)
    assert cut.section.area() > 0


@pytest.mark.parametrize("angle", [MIN_ANGLE_DEG - 0.1, MAX_ANGLE_DEG + 0.1])
def test_angles_juste_hors_bornes_refuses(angle: float) -> None:
    with pytest.raises(EdgeError, match="entre 30"):
        edge_cut_in_frame(_arete(angle), EdgeFamily.CHAMFER, 2.0)


def test_jeu_de_l_angle_droit() -> None:
    """À 0,5° de l'équerre une doucine passe encore ; au-delà elle est refusée."""
    assert frame_refusal(_arete(90.5), EdgeFamily.OGEE) is None
    edge_cut_in_frame(_arete(90.5), EdgeFamily.OGEE, 6.0, 4.0)
    assert frame_refusal(_arete(90.6), EdgeFamily.OGEE) is not None


# --- B5 : arête parcourue dans l'autre sens ----------------------------------------------------


def test_arete_inversee_depasse_du_bon_bout() -> None:
    """Le balayage part de l'autre bout quand l'arête va à rebours du repère de la section : le
    bout fermé (``extend_start``, à z = 200) ne doit pas dépasser."""
    assert _z_range(_arete(90.0, reverse=True)) == (-OVERSHOOT_MM, 200.0 + OVERSHOOT_MM)
    closed_start = _arete(90.0, reverse=True, extend_start=False)
    assert _z_range(closed_start) == (-OVERSHOOT_MM, 200.0)
    closed_end = _arete(90.0, reverse=True, extend_end=False)
    assert _z_range(closed_end) == (0.0, 200.0 + OVERSHOOT_MM)


# --- A3 : chanfrein asymétrique et quart de rond à angle aigu ---------------------------------


def test_chanfrein_asymetrique_oblique_cotes_sur_chaque_face() -> None:
    alpha = math.radians(60.0)
    cut = edge_cut_in_frame(_arete(60.0), EdgeFamily.CHAMFER, 5.0, 2.0)
    points = cut.section.outline()
    assert any(math.dist(point, (5.0, 0.0)) < 1e-9 for point in points)
    far = (2.0 * math.cos(alpha), 2.0 * math.sin(alpha))
    assert any(math.dist(point, far) < 1e-9 for point in points)


def test_quart_de_rond_aigu_encombrement_controle() -> None:
    """À 40°, un quart de rond de 2 mm touche chaque face à 2 / tan 20° ≈ 5,5 mm de l'arête :
    refusé sur des faces de 10 mm (moitié : 5 mm), accepté sur des faces de 12 mm."""
    with pytest.raises(EdgeError, match="trop grand"):
        edge_cut_in_frame(_arete(40.0, room=10.0), EdgeFamily.ROUND, 2.0)
    edge_cut_in_frame(_arete(40.0, room=12.0), EdgeFamily.ROUND, 2.0)


# --- Valeurs invalides -------------------------------------------------------------------------


@pytest.mark.parametrize("size", [0.0, -2.0, math.nan, math.inf, -math.inf])
def test_cote_invalide_refusee_a_tout_angle(size: float) -> None:
    for angle in (60.0, 90.0):
        with pytest.raises(EdgeError, match="Edge3"):
            edge_cut_in_frame(_arete(angle), EdgeFamily.CHAMFER, size)


def test_cote_tres_grande_refusee() -> None:
    with pytest.raises(EdgeError, match="trop grand"):
        edge_cut_in_frame(_arete(60.0), EdgeFamily.COVE, 1e9)


@pytest.mark.parametrize("field", ["length", "room_first", "room_second"])
@pytest.mark.parametrize("value", [math.nan, math.inf])
def test_repere_non_fini_refuse(field: str, value: float) -> None:
    with pytest.raises(ValueError, match="finis"):
        EdgeFrame(**{**_arete(90.0).__dict__, field: value})


def test_famille_inconnue_refusee() -> None:
    with pytest.raises(ValueError):
        edge_cut_in_frame(_arete(60.0), "Moulure", 2.0)
