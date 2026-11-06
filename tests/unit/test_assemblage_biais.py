# SPDX-License-Identifier: LGPL-2.1-or-later
"""Tenon-mortaise et rainure-languette entre pièces en biais (AB-b, B1 à B6)."""

from __future__ import annotations

import math

import pytest

from freecad.menuiserie.core._polyhedron import Polyhedron
from freecad.menuiserie.core.geometry import Axis, Box, JointError, PlacedBlock
from freecad.menuiserie.core.joints import JointKind, JointPlan, strategy_for
from freecad.menuiserie.core.joints._base import SQUARE_ONLY
from freecad.menuiserie.core.joints._profile import OUTSIDE_CONTACT, TOO_DEEP
from freecad.menuiserie.core.joints.dovetail import DovetailParams
from freecad.menuiserie.core.joints.dowels import DowelParams
from freecad.menuiserie.core.joints.half_lap import HalfLapParams
from freecad.menuiserie.core.joints.miter import MiterParams
from freecad.menuiserie.core.joints.mortise_tenon import MortiseTenonParams
from freecad.menuiserie.core.joints.tongue_groove import TongueGrooveParams
from tests.unit.aides_assemblages import rail, stile
from tests.unit.aides_biais import Mode, leaning_rail, stile_block, tilted_rail

TENON = strategy_for(JointKind.MORTISE_TENON)
TONGUE = strategy_for(JointKind.TONGUE_GROOVE)
THIN = 22.0
SECTION = 40.0 * 7.0  # tenon automatique d'une traverse de 60 x 22 : 40 x 7 mm


def size_of(solid: object) -> float:
    if isinstance(solid, Polyhedron):
        return solid.volume()
    assert isinstance(solid, Box)
    return solid.size(0) * solid.size(1) * solid.size(2)


def total(solids: tuple[object, ...]) -> float:
    return sum(size_of(solid) for solid in solids)


def tenon_of(plan: JointPlan) -> Polyhedron:
    tenon = plan.guest_additions[-1]
    assert isinstance(tenon, Polyhedron)
    return tenon


@pytest.mark.parametrize("mode", ["pointe", "hors tout", "cheval"])
@pytest.mark.parametrize("degrees", [5.0, 10.0, 30.0])
def test_tenon_et_mortaise_en_biais_ont_la_section_voulue(degrees: float, mode: Mode) -> None:
    host, guest = stile_block(), tilted_rail(degrees, mode)
    values = TENON.resolve(host, guest, MortiseTenonParams())
    plan = TENON.plan(host, guest, MortiseTenonParams())
    # Une barre coupée par un plan qui passe par son axe : section x longueur.
    assert size_of(tenon_of(plan)) == pytest.approx(SECTION * values.length, rel=1e-6)
    housing = plan.host_cuts[0]
    assert isinstance(housing, Polyhedron)
    assert housing.volume() == pytest.approx(SECTION * values.housing_depth, rel=1e-6)


def test_valeurs_en_biais_sont_celles_d_equerre_quand_l_angle_tend_vers_zero() -> None:
    square = TENON.resolve(stile(), rail(), MortiseTenonParams())
    nearly = TENON.resolve(stile_block(), tilted_rail(1e-4), MortiseTenonParams())
    assert nearly == square


def test_plan_continu_quand_l_angle_tend_vers_zero() -> None:
    square = TENON.plan(stile(), rail(), MortiseTenonParams())
    nearly = TENON.plan(stile_block(), tilted_rail(1e-4, "pointe"), MortiseTenonParams())
    assert total(nearly.host_cuts) == pytest.approx(total(square.host_cuts), rel=1e-4)
    assert size_of(tenon_of(nearly)) == pytest.approx(total(square.guest_additions), rel=1e-4)


def test_longueur_automatique_suit_la_profondeur_sur_l_axe() -> None:
    values = TENON.resolve(stile_block(), tilted_rail(10.0), MortiseTenonParams())
    assert values.length == round(2 * 60.0 / (3 * math.cos(math.radians(10.0))))


def test_longueur_automatique_reduite_pour_laisser_une_paroi() -> None:
    host, guest = stile_block(), tilted_rail(70.0)
    values = TENON.resolve(host, guest, MortiseTenonParams())
    assert values.length < round(2 * 60.0 / (3 * math.cos(math.radians(70.0))))
    TENON.plan(host, guest, MortiseTenonParams())  # sans refus


def test_tenon_traversant_s_arrete_a_la_face_opposee() -> None:
    host, guest = stile_block(), tilted_rail(10.0)
    plan = TENON.plan(host, guest, MortiseTenonParams(through=True))
    expected = SECTION * 60.0 / math.cos(math.radians(10.0))
    assert size_of(tenon_of(plan)) == pytest.approx(expected, rel=1e-6)


def test_un_bevel_par_bout_coupe_en_biais() -> None:
    host, guest = stile_block(), tilted_rail(10.0, "pointe")
    plan = TENON.plan(host, guest, MortiseTenonParams())
    assert len(plan.guest_bevels) == 1
    bevel = plan.guest_bevels[0]
    assert bevel.face is Axis.X_NEG
    # Le long point dépasse le bout de 60 x tan(10°), vers l'hôte (-X).
    assert bevel.long_point == pytest.approx(-60.0 * math.tan(math.radians(10.0)), rel=1e-6)
    assert math.hypot(bevel.normal.x, bevel.normal.y, bevel.normal.z) == pytest.approx(1.0)


def test_pas_de_bevel_pour_un_bout_d_equerre() -> None:
    assert TENON.plan(stile(), rail(), MortiseTenonParams()).guest_bevels == ()


def test_coin_retire_et_coin_ajoute_sont_dans_le_plan() -> None:
    host = stile_block()
    pointe = TENON.plan(host, tilted_rail(10.0, "pointe"), MortiseTenonParams())
    assert pointe.guest_trims == ()
    assert len(pointe.guest_additions) == 2
    hors_tout = TENON.plan(host, tilted_rail(10.0, "hors tout"), MortiseTenonParams())
    assert len(hors_tout.guest_trims) == 1
    assert len(hors_tout.guest_additions) == 1


def test_le_logement_est_dans_le_repere_de_l_hote() -> None:
    plan = TENON.plan(stile_block(), tilted_rail(10.0), MortiseTenonParams())
    housing = plan.host_cuts[0]
    assert isinstance(housing, Polyhedron)
    bounds = housing.bounds()
    assert 0.0 < bounds.lo(0) < bounds.hi(0) < 600.0
    assert bounds.hi(1) == pytest.approx(60.0, abs=1e-6)  # part de la face de l'hôte
    assert bounds.lo(1) > 0.0


def test_section_hors_de_la_face_est_refusee() -> None:
    with pytest.raises(JointError) as error:
        TENON.plan(stile_block(), tilted_rail(10.0), MortiseTenonParams(tenon_width=70.0))
    assert error.value.template == OUTSIDE_CONTACT


def test_tenon_trop_long_est_refuse() -> None:
    with pytest.raises(JointError) as error:
        TENON.plan(stile_block(), tilted_rail(10.0), MortiseTenonParams(tenon_length=200.0))
    assert error.value.template == TOO_DEEP


def test_biais_compose_et_inclinaison_dans_l_epaisseur() -> None:
    host = stile_block(thickness=80.0)
    for degrees in (5.0, 10.0):
        guest = leaning_rail(degrees)
        values = TENON.resolve(host, guest, MortiseTenonParams())
        plan = TENON.plan(host, guest, MortiseTenonParams())
        assert size_of(tenon_of(plan)) == pytest.approx(SECTION * values.length, rel=1e-6)


@pytest.mark.parametrize("mode", ["pointe", "hors tout", "cheval"])
def test_languette_en_biais(mode: Mode) -> None:
    host, guest = stile_block(thickness=80.0), leaning_rail(10.0, mode)
    values = TONGUE.resolve(host, guest, TongueGrooveParams())
    plan = TONGUE.plan(host, guest, TongueGrooveParams())
    assert size_of(tenon_of(plan)) == pytest.approx(60.0 * values.thickness * 10.0, rel=1e-6)
    groove = plan.host_cuts[0]
    assert isinstance(groove, Polyhedron)
    bounds = groove.bounds()
    assert bounds.lo(0) == pytest.approx(0.0, abs=1e-6)  # rainure filante : toute la longueur
    assert bounds.hi(0) == pytest.approx(600.0, abs=1e-6)


@pytest.mark.parametrize("degrees", [5.0, 10.0, 30.0])
def test_rainure_filante_biais_dans_la_largeur(degrees: float) -> None:
    """Rainure de toute la longueur et de profondeur constante, quel que soit le biais."""
    host, guest = stile_block(), tilted_rail(degrees)
    plan = TONGUE.plan(host, guest, TongueGrooveParams())
    groove = plan.host_cuts[0]
    assert isinstance(groove, Polyhedron)
    bounds = groove.bounds()
    assert bounds.lo(0) == pytest.approx(0.0, abs=1e-6)
    assert bounds.hi(0) == pytest.approx(600.0, abs=1e-6)
    assert bounds.hi(1) <= 60.0 + 1e-6  # ne sort pas de l'hôte


def test_languette_publie_le_biais() -> None:
    values = TONGUE.resolve(stile_block(), tilted_rail(10.0), TongueGrooveParams())
    assert values.oblique == pytest.approx(10.0)
    assert values.cut_angle > 0.0


def test_tenon_garde_sa_longueur_si_le_logement_debouche() -> None:
    """B4 : un tenon de 58 mm avec 2 mm de jeu dans un hôte de 60 mm reste de 58 mm."""
    params = MortiseTenonParams(tenon_length=58.0, mortise_clearance=2.0)
    plan = TENON.plan(stile_block(), tilted_rail(1e-4), params)
    assert tenon_of(plan).bounds().size(0) == pytest.approx(58.0, abs=0.05)


@pytest.mark.parametrize("reference", ["TenonPiece", "MortisedPiece", "HalfAngle"])
def test_long_point_independant_de_la_reference(reference: str) -> None:
    host, guest = stile_block(), tilted_rail(10.0, "pointe")
    params = MortiseTenonParams(oblique_reference=reference)
    bevel = TENON.plan(host, guest, params).guest_bevels[0]
    base = TENON.plan(host, guest, MortiseTenonParams()).guest_bevels[0]
    assert bevel.long_point == pytest.approx(base.long_point, abs=1e-6)


@pytest.mark.parametrize(
    ("kind", "params"),
    [
        (JointKind.DOWELS, DowelParams()),
        (JointKind.HALF_LAP, HalfLapParams()),
        (JointKind.DOVETAIL, DovetailParams()),
        (JointKind.MITER, MiterParams()),
    ],
)
def test_les_autres_assemblages_demandent_des_pieces_d_equerre(
    kind: JointKind, params: object
) -> None:
    host: PlacedBlock = stile_block()
    guest = tilted_rail(10.0)
    with pytest.raises(JointError) as error:
        strategy_for(kind).plan(host, guest, params)
    assert error.value.template == SQUARE_ONLY


def test_reglages_de_la_scie_biais_dans_la_largeur() -> None:
    values = TENON.resolve(stile_block(), tilted_rail(10.0), MortiseTenonParams())
    assert (values.oblique, values.cut_angle, values.blade_tilt) == (10.0, 10.0, 0.0)


def test_reglages_de_la_scie_biais_dans_l_epaisseur() -> None:
    host = stile_block(thickness=80.0)
    values = TENON.resolve(host, leaning_rail(10.0), MortiseTenonParams())
    assert (values.oblique, values.cut_angle, values.blade_tilt) == (10.0, 0.0, 10.0)


def test_pas_de_reglage_d_equerre() -> None:
    values = TENON.resolve(stile(), rail(), MortiseTenonParams())
    assert (values.oblique, values.cut_angle, values.blade_tilt) == (0.0, 0.0, 0.0)


# --- Référence du tenon (AB-e, E1 à E4) ---------------------------------------------------

REFERENCES = ("TenonPiece", "MortisedPiece", "HalfAngle")


def test_reference_invalide_refusee() -> None:
    with pytest.raises(JointError):
        MortiseTenonParams(oblique_reference="Autre")
    with pytest.raises(JointError):
        TongueGrooveParams(oblique_reference="Autre")


@pytest.mark.parametrize("reference", REFERENCES)
def test_reference_sans_effet_entre_pieces_d_equerre(reference: str) -> None:
    default = TENON.plan(stile(), rail(), MortiseTenonParams())
    assert TENON.plan(stile(), rail(), MortiseTenonParams(oblique_reference=reference)) == default


@pytest.mark.parametrize("reference", REFERENCES)
@pytest.mark.parametrize("mode", ["pointe", "hors tout", "cheval"])
def test_tenon_de_meme_section_quelle_que_soit_la_reference(reference: str, mode: Mode) -> None:
    host, guest = stile_block(), tilted_rail(10.0, mode)
    params = MortiseTenonParams(oblique_reference=reference)
    values = TENON.resolve(host, guest, params)
    plan = TENON.plan(host, guest, params)
    assert size_of(tenon_of(plan)) == pytest.approx(SECTION * values.length, rel=1e-6)


@pytest.mark.parametrize(
    ("reference", "grain"), [("TenonPiece", 0.0), ("MortisedPiece", 10.0), ("HalfAngle", 5.0)]
)
def test_ecart_du_tenon_au_fil(reference: str, grain: float) -> None:
    params = MortiseTenonParams(oblique_reference=reference)
    values = TENON.resolve(stile_block(), tilted_rail(10.0), params)
    assert values.grain_angle == pytest.approx(grain, abs=0.05)


def test_pieces_mortaisee_donne_une_mortaise_d_equerre() -> None:
    params = MortiseTenonParams(oblique_reference="MortisedPiece")
    plan = TENON.plan(stile_block(), tilted_rail(10.0), params)
    housing = plan.host_cuts[0]
    assert isinstance(housing, Polyhedron)
    columns = {(round(v.x, 6), round(v.z, 6)) for v in housing.vertices()}
    assert len(columns) == 4  # parois perpendiculaires à la face de l'hôte


def test_reference_continue_quand_l_angle_tend_vers_zero() -> None:
    square = TENON.plan(stile(), rail(), MortiseTenonParams())
    for reference in REFERENCES:
        params = MortiseTenonParams(oblique_reference=reference)
        nearly = TENON.plan(stile_block(), tilted_rail(1e-4, "pointe"), params)
        assert total(nearly.host_cuts) == pytest.approx(total(square.host_cuts), rel=1e-4)
