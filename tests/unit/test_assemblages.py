# SPDX-License-Identifier: LGPL-2.1-or-later
"""Stratégies d'assemblage (J3a, critères M3 à M10)."""

from __future__ import annotations

import math
from typing import Any

import pytest

from freecad.menuiserie.core.geometry import Box, JointError, PlacedBlock, Vec3
from freecad.menuiserie.core.joints import (
    JointKind,
    JointPlan,
    JointStrategy,
    guess_roles,
    mm_round,
    strategy_for,
)
from freecad.menuiserie.core.joints._profile import ProfileValues
from freecad.menuiserie.core.joints._registry import STRATEGIES
from freecad.menuiserie.core.joints.dovetail import DovetailParams
from freecad.menuiserie.core.joints.dowels import DowelParams
from freecad.menuiserie.core.joints.half_lap import HalfLapParams
from freecad.menuiserie.core.joints.miter import MiterParams
from freecad.menuiserie.core.joints.mortise_tenon import MortiseTenonParams
from freecad.menuiserie.core.joints.rabbet import RabbetParams
from freecad.menuiserie.core.joints.tongue_groove import TongueGrooveParams
from tests.unit.aides_assemblages import block, dovetail_corner, miter_corner, rail, stile

TENON = strategy_for(JointKind.MORTISE_TENON)
TONGUE = strategy_for(JointKind.TONGUE_GROOVE)
RABBET = strategy_for(JointKind.RABBET)


def box(low: tuple[float, float, float], high: tuple[float, float, float]) -> Box:
    return Box(Vec3(*low), Vec3(*high))


def only(solids: tuple[object, ...]) -> Box:
    assert len(solids) == 1
    solid = solids[0]
    assert isinstance(solid, Box)
    return solid


def board(y: float = 0.0, length: float = 1000.0, thickness: float = 22.0) -> PlacedBlock:
    """Lame 1000 x 100 x 22 (chant contre chant quand ``y`` = 100)."""
    return block((length, 100.0, thickness), (0.0, y, 0.0))


def refused(
    strategy: JointStrategy[Any, Any],
    host: PlacedBlock,
    guest: PlacedBlock,
    params: object,
    text: str,
) -> None:
    with pytest.raises(JointError, match=text):
        strategy.plan(host, guest, params)


# --- M3 : tenon-mortaise automatique ------------------------------------------------------


@pytest.mark.parametrize(("value", "expected"), [(7.33, 7), (7.5, 8), (53.33, 53), (0.2, 1)])
def test_mm_round(value: float, expected: float) -> None:
    assert mm_round(value) == expected


def test_tenon_automatique() -> None:
    values = TENON.resolve(stile(), rail(), MortiseTenonParams())
    assert values == ProfileValues(7.0, 40.0, 40.0, 0.0, 0.0, 42.0)
    plan = TENON.plan(stile(), rail(), MortiseTenonParams())
    assert only(plan.guest_additions) == box((-40, 10, 7.5), (0, 50, 14.5))
    assert only(plan.host_cuts) == box((10, 18, 7.5), (50, 60, 14.5))
    assert plan.host_additions == plan.guest_cuts == plan.inserts == ()


# --- M4 : tenon-mortaise, paramètres saisis et refus ---------------------------------------


def test_tenon_parametres_saisis() -> None:
    params = MortiseTenonParams(
        tenon_thickness=8, tenon_width=30, width_offset=5, thickness_offset=-2
    )
    plan = TENON.plan(stile(), rail(), params)
    assert only(plan.guest_additions) == box((-40, 20, 5), (0, 50, 13))
    assert only(plan.host_cuts) == box((10, 18, 5), (40, 60, 13))


def test_tenon_traversant() -> None:
    plan = TENON.plan(stile(), rail(), MortiseTenonParams(through=True, tenon_length=10))
    assert only(plan.guest_additions).size(0) == 60
    assert only(plan.host_cuts) == box((10, 0, 7.5), (50, 60, 14.5))


@pytest.mark.parametrize(
    ("params", "text"),
    [
        (MortiseTenonParams(tenon_length=59), "Logement trop profond"),
        (MortiseTenonParams(tenon_width=61), "sort de la surface de contact"),
        (MortiseTenonParams(width_offset=11), "sort de la surface de contact"),
        (MortiseTenonParams(thickness_offset=-8), "sort de la surface de contact"),
        (MortiseTenonParams(tenon_width=60), "paroi de matière"),
        (MortiseTenonParams(tenon_thickness=22), "paroi de matière"),
    ],
)
def test_tenon_refus(params: MortiseTenonParams, text: str) -> None:
    refused(TENON, stile(), rail(), params, text)


# Écart toléré par M2 : la traverse reculée ou avancée de 0,005 mm reste en contact ; le
# logement part de la face de l'hôte, sans peau de matière.
GAPS = pytest.mark.parametrize("y", [60.0, 60.005, 59.995], ids=["0", "+0,005", "-0,005"])


@GAPS
def test_mortaise_ancree_sur_la_face_de_l_hote(y: float) -> None:
    plan = TENON.plan(stile(), rail(y=y), MortiseTenonParams())
    assert only(plan.host_cuts) == box((10, 18, 7.5), (50, 60, 14.5))
    assert only(plan.guest_additions).size(0) == pytest.approx(40)


@GAPS
def test_tenon_traversant_avec_ecart(y: float) -> None:
    plan = TENON.plan(stile(), rail(y=y), MortiseTenonParams(through=True))
    assert only(plan.host_cuts) == box((10, 0, 7.5), (50, 60, 14.5))
    tenon = only(plan.guest_additions)
    assert (tenon.lo(0), tenon.hi(0)) == pytest.approx((-y, 0.0))
    assert TENON.resolve(stile(), rail(y=y), MortiseTenonParams(through=True)).length == (
        pytest.approx(y)
    )


@GAPS
def test_tenon_longueur_plus_jeu_egale_a_la_profondeur_debouche(y: float) -> None:
    plan = TENON.plan(stile(), rail(y=y), MortiseTenonParams(tenon_length=58))
    assert only(plan.host_cuts) == box((10, 0, 7.5), (50, 60, 14.5))


def test_tenon_refus_selon_la_position() -> None:
    refused(TENON, stile(), rail(y=65.0), MortiseTenonParams(), "ne se touchent pas")
    refused(TENON, stile(), rail(y=55.0), MortiseTenonParams(), "se chevauchent")
    on_face = block((100.0, 50.0, 10.0), (10.0, 5.0, 22.0))
    refused(TENON, stile(), on_face, MortiseTenonParams(), "par une face")
    refused(TENON, board(), board(100.0), MortiseTenonParams(), "pas sur son chant")


def test_tenon_trop_petit() -> None:
    tiny = block((50.0, 2.0, 22.0), (2.0, 60.0, 0.0), 90.0)
    refused(TENON, stile(), tiny, MortiseTenonParams(), "trop petites")


# --- M5 : les proportions suivent les pièces ----------------------------------------------


def test_proportions_suivent_les_pieces() -> None:
    wide_rail = TENON.resolve(stile(), rail(width=80.0), MortiseTenonParams())
    assert wide_rail.width == 80 - 2 * 13 == 54
    wide_stile = TENON.resolve(stile(80.0), rail(y=80.0), MortiseTenonParams())
    assert (wide_stile.length, wide_stile.housing_depth) == (53, 55)
    thick_rail = TENON.resolve(block((600, 60, 27)), rail(thickness=27), MortiseTenonParams())
    assert thick_rail.thickness == 9


def test_valeur_saisie_ne_suit_pas() -> None:
    params = MortiseTenonParams(tenon_width=30, tenon_length=20, tenon_thickness=8)
    values = TENON.resolve(stile(80.0), rail(width=80.0, y=80.0), params)
    assert (values.width, values.length, values.thickness) == (30, 20, 8)


# --- M6 : rainure-languette ---------------------------------------------------------------


def test_languette_automatique() -> None:
    values = TONGUE.resolve(board(), board(100.0), TongueGrooveParams())
    assert (values.thickness, values.length, values.housing_depth) == (7, 10, 11)
    plan = TONGUE.plan(board(), board(100.0), TongueGrooveParams())
    assert only(plan.guest_additions) == box((0, -10, 7.5), (1000, 0, 14.5))
    assert only(plan.host_cuts) == box((0, 89, 7.5), (1000, 100, 14.5))


@pytest.mark.parametrize(("through", "length"), [(True, 1000), (False, 600)])
def test_rainure_filante(through: bool, length: float) -> None:
    params = TongueGrooveParams(through_groove=through)
    plan = TONGUE.plan(board(), board(100.0, length=600.0), params)
    assert only(plan.host_cuts).size(0) == length


def test_languette_longueur_zero_automatique() -> None:
    values = TONGUE.resolve(board(), board(100.0), TongueGrooveParams(tongue_length=0))
    assert values.length == 10


def test_emboiture_par_le_bout() -> None:
    plan = TONGUE.plan(stile(), rail(), TongueGrooveParams())
    assert only(plan.host_cuts) == box((0, 49, 7.5), (600, 60, 14.5))


def test_panneau_en_rainure() -> None:
    panel = block((300.0, 200.0, 10.0), (0.0, 60.0, 6.0))
    params = TongueGrooveParams(tongue_thickness=10)
    plan = TONGUE.plan(stile(), panel, params)
    assert only(plan.host_cuts) == box((0, 49, 6), (600, 60, 16))
    flush = block((300.0, 200.0, 22.0), (0.0, 60.0, 0.0))
    refused(TONGUE, stile(), flush, TongueGrooveParams(tongue_thickness=22), "paroi")


def test_languette_refus() -> None:
    refused(TONGUE, stile(), rail(), TongueGrooveParams(tongue_length=60), "trop profond")
    on_face = block((100.0, 50.0, 10.0), (10.0, 5.0, 22.0))
    refused(TONGUE, stile(), on_face, TongueGrooveParams(), "par une face")


# --- M7 : feuillure / logement ------------------------------------------------------------


def side_and_back(back_length: float = 600.0) -> tuple[PlacedBlock, PlacedBlock]:
    side = block((600.0, 300.0, 18.0))
    back = block((back_length, 400.0, 6.0), (0.0, 290.0, 0.0))
    return side, back


def test_feuillure() -> None:
    side, back = side_and_back()
    plan = RABBET.plan(side, back, RabbetParams())
    assert only(plan.host_cuts) == box((0, 290, 0), (600, 300, 6))
    assert plan.guest_cuts == plan.guest_additions == ()


@pytest.mark.parametrize(("through", "length"), [(True, 600), (False, 200)])
def test_feuillure_filante(through: bool, length: float) -> None:
    side = block((600.0, 300.0, 18.0))
    back = block((200.0, 400.0, 6.0), (100.0, 290.0, 0.0))
    assert RABBET.resolve(side, back, RabbetParams(through=through)).length == length


def test_feuillure_refus_sans_chevauchement() -> None:
    refused(RABBET, stile(), rail(), RabbetParams(), "ne se chevauchent pas")


# --- M8 : paramètres validés --------------------------------------------------------------


PARAMS_CLASSES = (
    MortiseTenonParams,
    TongueGrooveParams,
    RabbetParams,
    DowelParams,
    HalfLapParams,
    DovetailParams,
    MiterParams,
)


@pytest.mark.parametrize(
    ("factory", "field", "value"),
    [
        (MortiseTenonParams, "tenon_thickness", -0.1),
        (MortiseTenonParams, "tenon_width", 20_000.1),
        (MortiseTenonParams, "tenon_length", float("nan")),
        (MortiseTenonParams, "mortise_clearance", True),
        (MortiseTenonParams, "tenon_length", "10"),
        (MortiseTenonParams, "width_offset", 20_000.1),
        (MortiseTenonParams, "thickness_offset", float("inf")),
        (MortiseTenonParams, "through", 1),
        (TongueGrooveParams, "tongue_length", -1),
        (TongueGrooveParams, "through_groove", "oui"),
        (RabbetParams, "through", None),
        (DowelParams, "count", 51),
        (DowelParams, "count", -1),
        (DowelParams, "count", 2.0),
        (DowelParams, "count", True),
        (DowelParams, "diameter", -3),
        (HalfLapParams, "depth", -1.0),
        (HalfLapParams, "depth", float("inf")),
        (HalfLapParams, "flip_side", 0),
        (DovetailParams, "tail_count", -1),
        (DovetailParams, "pin_width", math.nan),
        (DovetailParams, "slope", 1.0),
        (DovetailParams, "slope", 21),
    ],
)
def test_parametres_refuses(factory: type, field: str, value: object) -> None:
    with pytest.raises(ValueError, match=f"invalide : {field} = ") as error:
        factory(**{field: value})
    assert isinstance(error.value, JointError)
    assert error.value.params["field"] == field


@pytest.mark.parametrize(
    ("factory", "field", "value"),
    [
        (MortiseTenonParams, "tenon_thickness", 0),
        (MortiseTenonParams, "tenon_width", 20_000),
        (MortiseTenonParams, "width_offset", -20_000),
        (MortiseTenonParams, "thickness_offset", 20_000),
        (MortiseTenonParams, "through", True),
        (TongueGrooveParams, "through_groove", False),
        (DowelParams, "count", 50),
        (DowelParams, "count", 0),
        (HalfLapParams, "depth", 0),
        (HalfLapParams, "flip_side", True),
        (DovetailParams, "tail_count", 50),
        (DovetailParams, "slope", 2),
        (DovetailParams, "slope", 20),
    ],
)
def test_parametres_limites_acceptes(factory: type, field: str, value: object) -> None:
    params = factory(**{field: value})
    assert getattr(params, field) == value


def test_parametres_normalises_et_immuables() -> None:
    params = MortiseTenonParams(tenon_width=30)
    assert isinstance(params.tenon_width, float)
    with pytest.raises(AttributeError):
        params.tenon_width = 10  # type: ignore[misc]
    assert DowelParams().hole_clearance == 1.0
    assert hash(TongueGrooveParams()) == hash(TongueGrooveParams())


# --- M9 : registre ------------------------------------------------------------------------


@pytest.mark.parametrize("kind", list(JointKind))
def test_une_strategie_par_type(kind: JointKind) -> None:
    strategy = strategy_for(kind)
    assert strategy.kind is kind
    assert isinstance(strategy, JointStrategy)


def test_registre_fige() -> None:
    assert set(STRATEGIES) == set(JointKind)
    with pytest.raises(TypeError):
        STRATEGIES[JointKind.RABBET] = TENON  # type: ignore[index]


@pytest.mark.parametrize(
    ("kind", "host", "guest", "params"),
    [
        (JointKind.MORTISE_TENON, stile(), rail(), MortiseTenonParams()),
        (JointKind.TONGUE_GROOVE, board(), board(100.0), TongueGrooveParams()),
        (JointKind.RABBET, *side_and_back(), RabbetParams()),
        (JointKind.DOWELS, stile(), rail(), DowelParams()),
        (
            JointKind.HALF_LAP,
            stile(),
            block((600.0, 60.0, 22.0), (330.0, -270.0, 0.0), 90.0),
            HalfLapParams(),
        ),
        (JointKind.DOVETAIL, *dovetail_corner(), DovetailParams()),
        (JointKind.MITER, *miter_corner(), MiterParams()),
    ],
)
def test_plan_par_le_registre(
    kind: JointKind, host: PlacedBlock, guest: PlacedBlock, params: object
) -> None:
    strategy = strategy_for(kind)
    assert strategy.resolve(host, guest, params) is not None
    assert isinstance(strategy.plan(host, guest, params), JointPlan)


# --- M10 : rôles ----------------------------------------------------------------------------


def test_roles_bout_contre_chant() -> None:
    assert guess_roles(stile(), rail()) == (0, 1)
    assert guess_roles(rail(), stile()) == (1, 0)


def test_roles_chevauchement_piece_la_plus_mince() -> None:
    side, back = side_and_back()
    assert guess_roles(side, back) == (0, 1)
    assert guess_roles(back, side) == (1, 0)


def test_roles_cas_symetriques_ordre_conserve() -> None:
    first, second = board(), block((1000.0, 100.0, 22.0), (1000.0, 0.0, 0.0))
    assert guess_roles(first, second) == (0, 1)
    assert guess_roles(second, first) == (0, 1)
    assert guess_roles(stile(), rail(y=70.0)) == (0, 1)
