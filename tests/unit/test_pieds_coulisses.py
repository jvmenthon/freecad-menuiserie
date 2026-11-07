# SPDX-License-Identifier: LGPL-2.1-or-later
"""Pieds de caisson et coulisses de tiroir (issue #159, ADR 0033)."""

from __future__ import annotations

import pytest

from freecad.menuiserie.core.geometry import Box, Cylinder, JointError, PlacedBlock
from freecad.menuiserie.core.joints import JointKind, strategy_for
from freecad.menuiserie.core.joints.feet import FootParams
from freecad.menuiserie.core.joints.slides import SlideParams
from tests.unit.aides_assemblages import block, placed, rotation_y

FOOT = strategy_for(JointKind.FOOT)
SLIDE = strategy_for(JointKind.DRAWER_SLIDE)


def bottom_panel() -> PlacedBlock:
    """Fond de caisson couché 600 x 500 x 19."""
    return block((600.0, 500.0, 19.0))


def cylinders(solids: tuple[object, ...]) -> list[Cylinder]:
    assert all(isinstance(solid, Cylinder) for solid in solids)
    return [solid for solid in solids if isinstance(solid, Cylinder)]


def test_quatre_pieds_aux_coins() -> None:
    panel = bottom_panel()
    values = FOOT.resolve(panel, panel, FootParams())
    assert values.count == 4 and values.edge_distance == 50.0
    assert sorted({x for x, _ in values.centers}) == [50.0, 550.0]
    plan = FOOT.plan(panel, panel, FootParams())
    holes = cylinders(plan.host_cuts)
    assert len(holes) == 4 and not plan.guest_cuts
    assert holes[0].base.z == 0.0 and holes[0].axis.value == "+Z"  # dans le panneau, vers le haut
    assert len(plan.inserts) == 8  # embase et tige par pied
    base = cylinders(plan.inserts)[0]
    assert base.axis.value == "-Z" and base.height == 15.0  # l'embase sort sous le panneau


def test_pieds_en_grille() -> None:
    panel = bottom_panel()
    values = FOOT.resolve(panel, panel, FootParams(columns=3, rows=2))
    assert values.count == 6


def test_pieds_refuses_sur_panneau_dresse() -> None:
    upright = placed((600.0, 500.0, 19.0), rotation_y(90.0), (0.0, 0.0, 0.0))
    with pytest.raises(JointError):
        FOOT.plan(upright, upright, FootParams())


def test_pieds_trop_serres_ou_trop_profonds() -> None:
    panel = bottom_panel()
    with pytest.raises(JointError):
        FOOT.plan(panel, panel, FootParams(columns=12))
    with pytest.raises(JointError):
        FOOT.plan(panel, panel, FootParams(hole_depth=18))
    with pytest.raises(JointError):
        FOOT.plan(panel, panel, FootParams(stem_diameter=60))


def sides(gap: float = 12.7) -> tuple[PlacedBlock, PlacedBlock]:
    """Côté de caisson 500 x 300 et côté de tiroir 450 x 150, face à face avec un jeu."""
    return block((500.0, 300.0, 19.0)), block((450.0, 150.0, 16.0), (0.0, 50.0, 19.0 + gap))


def test_coulisse_automatique() -> None:
    host, guest = sides()
    values = SLIDE.resolve(host, guest, SlideParams())
    assert values.length == 450.0 and values.gap == pytest.approx(12.7)
    assert values.hole_positions[0] == 37.0 and values.hole_count == 3
    plan = SLIDE.plan(host, guest, SlideParams())
    (body,) = plan.inserts
    assert isinstance(body, Box)
    assert body.size(0) == 450.0 and body.size(1) == 45.0
    assert body.size(2) == pytest.approx(12.7) and body.lo(2) == pytest.approx(19.0)
    assert len(cylinders(plan.host_cuts)) == len(cylinders(plan.guest_cuts)) == 3


def test_coulisse_reglages() -> None:
    host, guest = sides()
    params = SlideParams(length=400, front_setback=20, height_offset=10, hole_count=2)
    values = SLIDE.resolve(host, guest, params)
    assert values.length == 400 and len(values.hole_positions) == 2
    (body,) = SLIDE.plan(host, guest, params).inserts
    assert isinstance(body, Box) and body.lo(0) == 20.0
    reversed_plan = SLIDE.plan(host, guest, SlideParams(length=400, reversed=True))
    (back,) = reversed_plan.inserts
    assert isinstance(back, Box) and back.hi(0) == 450.0


def test_coulisse_refus() -> None:
    host, guest = sides()
    for params in (SlideParams(length=500), SlideParams(slide_height=200)):
        with pytest.raises(JointError):
            SLIDE.plan(host, guest, params)
    touching = block((450.0, 150.0, 16.0), (0.0, 50.0, 19.0))
    with pytest.raises(JointError):
        SLIDE.plan(host, touching, SlideParams())
    away = block((450.0, 150.0, 16.0), (900.0, 50.0, 40.0))
    with pytest.raises(JointError):
        SLIDE.plan(host, away, SlideParams())


def test_coulisse_refus_dit_l_ecart_reel() -> None:
    host, _ = sides()
    flush = block((450.0, 150.0, 16.0), (0.0, 50.0, 10.0))  # chevauche le côté du caisson de 9 mm
    with pytest.raises(JointError) as error:
        SLIDE.plan(host, flush, SlideParams())
    assert error.value.params["gap"] == "-9"


def test_coulisse_choisit_l_axe_le_plus_proche() -> None:
    """Deux axes séparés : le plus proche (l'épaisseur) fait face, puis le recouvrement manque."""
    host = block((500.0, 300.0, 19.0))
    guest = block((450.0, 150.0, 16.0), (600.0, 50.0, 31.7))  # séparé aussi selon X (100 mm)
    with pytest.raises(JointError):  # aucun recouvrement : refus net
        SLIDE.plan(host, guest, SlideParams())
