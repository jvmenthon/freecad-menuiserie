# SPDX-License-Identifier: LGPL-2.1-or-later
"""Pieds de caisson et coulisses de tiroir (issue #159, ADR 0033)."""

from __future__ import annotations

import pytest

from freecad.menuiserie.core.geometry import Box, Cylinder, JointError, PlacedBlock
from freecad.menuiserie.core.joints import JointKind, strategy_for
from freecad.menuiserie.core.joints._footprint import margin
from freecad.menuiserie.core.joints.feet import FootParams
from freecad.menuiserie.core.joints.slides import SlideParams
from freecad.menuiserie.core.part_model import Dimensions
from tests.unit.aides_assemblages import block, placed, rotation_y

FOOT = strategy_for(JointKind.FOOT)
WOOD = FootParams(foot_material="wood")
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
    plan = FOOT.plan(panel, panel, WOOD)
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
        FOOT.plan(panel, panel, FootParams(hole_depth=18, foot_material="wood"))
    with pytest.raises(JointError):
        FOOT.plan(panel, panel, FootParams(stem_diameter=60, foot_material="wood"))


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
    away = block((450.0, 150.0, 16.0), (900.0, 50.0, 40.0))
    with pytest.raises(JointError):
        SLIDE.plan(host, away, SlideParams())


def test_cotes_qui_se_touchent_acceptes_avec_le_jeu_manquant() -> None:
    host, guest = sides(gap=0.0)
    values = SLIDE.resolve(host, guest, SlideParams())
    assert values.gap == pytest.approx(0.0) and values.shortfall == pytest.approx(12.7)
    assert values.direction.value == "+Z"
    plan = SLIDE.plan(host, guest, SlideParams())
    (body,) = plan.inserts
    assert isinstance(body, Box) and body.size(2) == pytest.approx(12.7)


def test_cotes_qui_se_chevauchent_acceptes() -> None:
    host, _ = sides()
    inside = block((450.0, 150.0, 16.0), (0.0, 50.0, 10.0))  # chevauche le côté de 9 mm
    values = SLIDE.resolve(host, inside, SlideParams())
    assert values.gap == pytest.approx(-9.0) and values.shortfall == pytest.approx(21.7)
    plan = SLIDE.plan(host, inside, SlideParams())
    assert len(cylinders(plan.host_cuts)) == len(cylinders(plan.guest_cuts)) == 3


def test_jeu_suffisant_sans_manque() -> None:
    host, guest = sides()
    assert SLIDE.resolve(host, guest, SlideParams()).shortfall == 0.0


def test_cotes_confondus_refuses() -> None:
    host, _ = sides()
    same = block((450.0, 150.0, 16.0), (0.0, 50.0, 3.0))  # moitié dans le côté du caisson
    with pytest.raises(JointError) as error:
        SLIDE.plan(host, same, SlideParams())
    assert error.value.params["gap"] == "-16"


def test_coulisse_choisit_l_axe_le_plus_proche() -> None:
    """Deux axes séparés : le plus proche (l'épaisseur) fait face, puis le recouvrement manque."""
    host = block((500.0, 300.0, 19.0))
    guest = block((450.0, 150.0, 16.0), (600.0, 50.0, 31.7))  # séparé aussi selon X (100 mm)
    with pytest.raises(JointError):  # aucun recouvrement : refus net
        SLIDE.plan(host, guest, SlideParams())


def test_matiere_des_pieds() -> None:
    panel = bottom_panel()
    assert FOOT.resolve(panel, panel, FootParams()).foot_material == "plastic"
    assert FOOT.resolve(panel, panel, FootParams(foot_material="wood")).foot_material == "wood"
    with pytest.raises(JointError):
        FootParams(foot_material="acier")


def test_pieds_en_plastique_sans_tige_ni_percage() -> None:
    panel = bottom_panel()
    plan = FOOT.plan(panel, panel, FootParams())
    assert not plan.host_cuts and not plan.guest_cuts
    assert len(plan.inserts) == 4  # l'embase seule, sous le panneau
    base = cylinders(plan.inserts)[0]
    assert base.axis.value == "-Z" and base.height == 15.0
    # Sans tige : ni tige trop large ni logement trop profond ne gênent.
    assert FOOT.plan(panel, panel, FootParams(stem_diameter=60, hole_depth=18)).inserts


def test_nombre_de_pieds_automatique() -> None:
    small = bottom_panel()  # 600 x 500 : 2 x 2
    assert FOOT.resolve(small, small, WOOD).count == 4
    long = block((1800.0, 500.0, 19.0))  # 1700 mm entre les pieds extrêmes : 4 en longueur
    values = FOOT.resolve(long, long, WOOD)
    assert (values.columns, values.rows, values.count) == (4, 2, 8)
    fixed = FootParams(columns=3, rows=1, foot_material="wood")
    assert FOOT.resolve(long, long, fixed).count == 3


L_SHAPE = (
    (
        (0.0, 0.0),
        (1000.0, 0.0),
        (1000.0, 100.0),
        (100.0, 100.0),
        (100.0, 600.0),
        (0.0, 600.0),
    ),
)


def l_panel() -> PlacedBlock:
    """Panneau couché en L : branche de 1000 mm le long de X, branche de 600 mm le long de Y."""
    return PlacedBlock(Dimensions(1000.0, 600.0, 19.0), bottom_panel().placement, L_SHAPE)


def test_pieds_restent_dans_le_contour_d_une_piece_coudee() -> None:
    panel = l_panel()
    values = FOOT.resolve(panel, panel, FootParams())
    assert values.count >= 2
    for x, y in values.centers:
        assert margin((x, y), L_SHAPE) >= 25.0 - 1e-6  # l'embase (Ø50) reste sur la matière
    plan = FOOT.plan(panel, panel, WOOD)
    assert len(cylinders(plan.host_cuts)) == values.count


def test_piece_rectangulaire_sans_contour_inchangee() -> None:
    panel = bottom_panel()
    assert panel.footprint is None
    assert FOOT.resolve(panel, panel, FootParams()).count == 4


def test_contour_trop_etroit_refuse() -> None:
    thin = PlacedBlock(
        Dimensions(1000.0, 600.0, 19.0),
        bottom_panel().placement,
        (((0.0, 0.0), (1000.0, 0.0), (1000.0, 30.0), (0.0, 30.0)),),
    )
    with pytest.raises(JointError):
        FOOT.resolve(thin, thin, FootParams())
