# SPDX-License-Identifier: LGPL-2.1-or-later
"""Feuillure entre pièces en biais (ADR 0034, lot S-a, critères R1 à R3)."""

from __future__ import annotations

import pytest

from freecad.menuiserie.core._polyhedron import Polyhedron
from freecad.menuiserie.core.geometry import CUT_OVERRUN_MM, JointError
from freecad.menuiserie.core.joints import JointKind, strategy_for
from freecad.menuiserie.core.joints._overlap import OBLIQUE_OVERLAP_ONLY
from freecad.menuiserie.core.joints.rabbet import NO_MATERIAL_LEFT, RabbetParams
from tests.unit.aides_assemblages import placed, rotation_z
from tests.unit.aides_biais import stile_block, tilted_rail

RABBET = strategy_for(JointKind.RABBET)


@pytest.mark.parametrize("degrees", [10.0, 30.0, 60.0])
def test_la_feuillure_en_biais_enleve_la_place_de_la_pieces_logee(degrees: float) -> None:
    host = stile_block()
    guest = placed((50.0, 20.0, 22.0), rotation_z(degrees), (300.0, 10.0, 0.0))
    plan = RABBET.plan(host, guest, RabbetParams())
    (cut,) = plan.host_cuts
    assert isinstance(cut, Polyhedron)
    assert cut.volume() == pytest.approx((50.0 + 2 * CUT_OVERRUN_MM) * 20.0 * 22.0, rel=1e-6)
    assert not plan.guest_additions and not plan.guest_trims


def test_la_feuillure_en_biais_calcule_les_memes_valeurs_que_le_plan() -> None:
    host = stile_block()
    guest = placed((50.0, 20.0, 22.0), rotation_z(30.0), (300.0, 10.0, 0.0))
    values = RABBET.resolve(host, guest, RabbetParams())
    assert values.length > 0


def test_la_feuillure_en_biais_refuse_des_pieces_ecartees() -> None:
    far = placed((50.0, 20.0, 22.0), rotation_z(30.0), (300.0, 500.0, 0.0))
    with pytest.raises(JointError):
        RABBET.plan(stile_block(), far, RabbetParams())


def test_la_feuillure_en_biais_refuse_des_pieces_au_contact() -> None:
    with pytest.raises(JointError) as error:
        RABBET.plan(stile_block(), tilted_rail(10.0, "pointe"), RabbetParams())
    assert error.value.template == OBLIQUE_OVERLAP_ONLY


def test_la_feuillure_en_biais_ne_peut_pas_enlever_tout_l_hote() -> None:
    host = placed((60.0, 20.0, 22.0), rotation_z(0.0), (0.0, 0.0, 0.0))
    guest = placed((300.0, 300.0, 22.0), rotation_z(20.0), (-100.0, -100.0, 0.0))
    with pytest.raises(JointError) as error:
        RABBET.plan(host, guest, RabbetParams())
    assert error.value.template == NO_MATERIAL_LEFT


def test_la_feuillure_en_biais_refuse_une_piece_qui_coupe_l_hote_en_deux() -> None:
    """Recette de jv : une pièce qui traverse l'hôte de part en part le couperait en deux."""
    host = stile_block()
    guest = placed((300.0, 20.0, 22.0), rotation_z(30.0), (230.0, -50.0, 0.0))
    with pytest.raises(JointError) as error:
        RABBET.plan(host, guest, RabbetParams())
    assert error.value.template == NO_MATERIAL_LEFT


def test_la_feuillure_en_biais_accepte_une_entaille_qui_n_atteint_pas_les_deux_bords() -> None:
    host = stile_block()
    guest = placed((50.0, 20.0, 22.0), rotation_z(30.0), (300.0, 10.0, 0.0))
    assert RABBET.plan(host, guest, RabbetParams()).host_cuts


def test_la_feuillure_en_biais_accepte_une_piece_moins_epaisse_qui_traverse() -> None:
    host = stile_block()
    guest = placed((300.0, 20.0, 10.0), rotation_z(30.0), (230.0, -50.0, 0.0))
    assert RABBET.plan(host, guest, RabbetParams()).host_cuts
