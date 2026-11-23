# SPDX-License-Identifier: LGPL-2.1-or-later
"""Assemblages de « Fermer le caisson » (ADR 0064, spécification § 5) : chaque choix de liste est
réalisable par les stratégies de J3 ou grisé avec sa raison."""

from __future__ import annotations

from dataclasses import replace
from itertools import product

import pytest

from freecad.menuiserie.core.i18n import TemplatedError
from freecad.menuiserie.core.part_model import Dimensions
from freecad.menuiserie.core.templates.closing import (
    back_availability,
    check_feasible,
    closing_layout,
    joinery_availability,
)
from freecad.menuiserie.core.templates.closing_params import (
    BackJoinery,
    ClosingJoinery,
    ClosingParams,
    ClosingRole,
    Element,
)
from tests.unit.aides_fermeture import layout, params

EVERYTHING = frozenset(Element)


@pytest.mark.parametrize(
    ("joinery", "back", "role", "turns", "elements"),
    list(
        product(
            ClosingJoinery,
            BackJoinery,
            ClosingRole,
            (0, 1),
            (frozenset(Element) - {Element.BACK}, EVERYTHING, params().elements),
        )
    ),
)
def test_chaque_combinaison_se_calcule_sur_les_pieces_du_gabarit(
    joinery: ClosingJoinery,
    back: BackJoinery,
    role: ClosingRole,
    turns: int,
    elements: frozenset[Element],
) -> None:
    result = layout(
        joinery=joinery, back_joinery=back, role=role, front_turns=turns, elements=elements
    )
    check_feasible(result)  # un plan d'usinage par assemblage, sans refus
    assert all(
        {joint.host, joint.guest} <= {piece.key for piece in result.pieces}
        for joint in result.joints
    )


@pytest.mark.parametrize("thick_back", [False, True])
def test_fond_epais_ou_mince_se_calcule(thick_back: bool) -> None:
    for joinery in ClosingJoinery:
        check_feasible(layout(joinery=joinery, thick_back=thick_back, elements=EVERYTHING))


def test_tous_les_choix_sont_disponibles_pour_la_reference() -> None:
    probe = params(joinery="None", back_joinery="None")
    assert set(joinery_availability(probe).values()) == {None}
    assert set(back_availability(probe).values()) == {None}
    assert list(joinery_availability(probe)) == list(ClosingJoinery)


def test_tourillons_grises_avec_la_raison_sous_12_mm() -> None:
    probe = params(joinery="None", back_joinery="None", thickness=10.0)
    reasons = joinery_availability(probe)
    assert reasons[ClosingJoinery.DOWELS] is not None
    assert "12 mm pour des tourillons" in str(reasons[ClosingJoinery.DOWELS])
    assert [k for k, v in reasons.items() if v is not None] == [ClosingJoinery.DOWELS]


def test_tourillons_et_queues_d_aronde_grises_quand_les_cotes_ne_tiennent_pas() -> None:
    thick = Dimensions(2000.0, 100.0, 40.0)  # côtés de 20 mm de haut entre deux pièces de 40 mm
    probe = ClosingParams(
        thick,
        "m",
        thickness=40.0,
        height=100.0,
        joinery=ClosingJoinery.NONE,
        back_joinery=BackJoinery.NONE,
        elements=EVERYTHING,
    )
    reasons = joinery_availability(probe)
    assert {k for k, v in reasons.items() if v is not None} == {
        ClosingJoinery.DOWELS,
        ClosingJoinery.DOVETAIL,
    }
    assert "Queues trop étroites" in str(reasons[ClosingJoinery.DOVETAIL])
    assert all(isinstance(v, TemplatedError) for v in reasons.values() if v is not None)


def test_la_raison_garde_son_gabarit_traduisible() -> None:
    probe = params(joinery="None", back_joinery="None", thickness=10.0)
    error = joinery_availability(probe)[ClosingJoinery.DOWELS]
    assert error is not None
    assert error.template.startswith("Fermer le caisson : {field}")
    assert error.params["min"] == "12"


def test_disponibilite_ne_modifie_pas_les_parametres() -> None:
    probe = params(joinery="None", back_joinery="Groove")
    before = replace(probe)
    joinery_availability(probe)
    back_availability(probe)
    assert probe == before
    assert probe.joinery is ClosingJoinery.NONE


def test_une_stratégie_de_j3_refuse_des_tourillons_trop_profonds() -> None:
    low = ClosingParams(
        Dimensions(600.0, 400.0, 40.0),
        "m",
        thickness=18.0,
        height=100.0,
        joinery=ClosingJoinery.NONE,
    )
    check_feasible(closing_layout(low))
    with pytest.raises(TemplatedError, match="trop profond"):
        check_feasible(closing_layout(replace(low, joinery=ClosingJoinery.DOWELS)))
