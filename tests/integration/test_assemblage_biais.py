# SPDX-License-Identifier: LGPL-2.1-or-later
"""Tenon-mortaise et rainure-languette entre pièces en biais dans FreeCAD (AB-b, B9, ADR 0024) :
pièces usinées valides, un seul solide, volumes égaux à ceux que calcule ``core``."""

from __future__ import annotations

import math
from typing import Any

import pytest

from freecad.menuiserie.core._polyhedron import Polyhedron
from freecad.menuiserie.core.geometry import Box, PlacedBlock
from freecad.menuiserie.core.joints import JointKind, strategy_for
from freecad.menuiserie.core.joints.mortise_tenon import MortiseTenonParams
from freecad.menuiserie.core.joints.tongue_groove import TongueGrooveParams
from freecad.menuiserie.features.joints import feasible
from tests.integration.cadre import stale_or_invalid
from tests.integration.types_assemblages import wood
from tests.unit.aides_biais import Mode, leaning_rail, stile_block, tilted_rail

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
api = pytest.importorskip("freecad.menuiserie.api")

TENON = strategy_for(JointKind.MORTISE_TENON)
TONGUE = strategy_for(JointKind.TONGUE_GROOVE)
RAIL = (280.0, 60.0, 22.0)


def volume_of(solid: object) -> float:
    if isinstance(solid, Polyhedron):
        return solid.volume()
    assert isinstance(solid, Box)
    return solid.size(0) * solid.size(1) * solid.size(2)


def placement_of(block: PlacedBlock) -> Any:
    rows = block.placement.rotation
    shift = block.placement.translation
    matrix = App.Matrix(
        rows[0][0], rows[0][1], rows[0][2], shift.x,
        rows[1][0], rows[1][1], rows[1][2], shift.y,
        rows[2][0], rows[2][1], rows[2][2], shift.z,
        0, 0, 0, 1,
    )  # fmt: skip
    return App.Placement(matrix)


def expected_volumes(strategy: Any, host: PlacedBlock, guest: PlacedBlock, params: Any) -> Any:
    """Volumes que donnent les plans de ``core`` (enlèvements, ajouts, parties retirées)."""
    plan = strategy.plan(host, guest, params)
    host_volume = host.dimensions.length * host.dimensions.width * host.dimensions.thickness
    guest_volume = RAIL[0] * RAIL[1] * RAIL[2]
    host_after = host_volume - sum(volume_of(solid) for solid in plan.host_cuts)
    guest_after = (
        guest_volume
        - sum(volume_of(solid) for solid in plan.guest_trims)
        + sum(volume_of(solid) for solid in plan.guest_additions)
    )
    return host_after, guest_after


def assemble(document: Any, host_block: PlacedBlock, guest_block: PlacedBlock, make: Any) -> Any:
    host = wood(document, "H", (600, 60, host_block.dimensions.thickness), (0, 0, 0))
    guest = wood(document, "I", RAIL, placement_of(guest_block))
    document.recompute()
    joint = make(host, guest)
    document.recompute()
    return host, guest, joint


@pytest.mark.parametrize("mode", ["pointe", "hors tout", "cheval"])
@pytest.mark.parametrize("degrees", [10.0, 30.0])
def test_tenon_mortaise_en_biais(document: Any, degrees: float, mode: Mode) -> None:
    host_block, guest_block = stile_block(), tilted_rail(degrees, mode)
    host, guest, joint = assemble(document, host_block, guest_block, api.make_mortise_tenon)
    assert joint.isValid(), joint.getStatusString()
    host_volume, guest_volume = expected_volumes(
        TENON, host_block, guest_block, MortiseTenonParams()
    )
    host_shape = api.machined_part_of(host).Shape
    guest_shape = api.machined_part_of(guest).Shape
    assert len(host_shape.Solids) == len(guest_shape.Solids) == 1
    assert host_shape.isValid()
    assert guest_shape.isValid()
    assert host_shape.Volume == pytest.approx(host_volume, rel=1e-6)
    assert guest_shape.Volume == pytest.approx(guest_volume, rel=1e-6)
    assert host_shape.common(guest_shape).Volume == pytest.approx(0, abs=1e-3)
    assert stale_or_invalid(document) == []


def test_tenon_traversant_en_biais(document: Any) -> None:
    host_block, guest_block = stile_block(), tilted_rail(10.0)
    host, guest, joint = assemble(
        document,
        host_block,
        guest_block,
        lambda h, g: api.make_mortise_tenon(h, g, through=True),
    )
    assert joint.isValid(), joint.getStatusString()
    host_volume, guest_volume = expected_volumes(
        TENON, host_block, guest_block, MortiseTenonParams(through=True)
    )
    assert api.machined_part_of(host).Shape.Volume == pytest.approx(host_volume, rel=1e-6)
    assert api.machined_part_of(guest).Shape.Volume == pytest.approx(guest_volume, rel=1e-6)


def test_biais_dans_l_epaisseur_sur_montant_epais(document: Any) -> None:
    host_block, guest_block = stile_block(thickness=80.0), leaning_rail(10.0)
    host, guest, joint = assemble(document, host_block, guest_block, api.make_mortise_tenon)
    assert joint.isValid(), joint.getStatusString()
    host_volume, guest_volume = expected_volumes(
        TENON, host_block, guest_block, MortiseTenonParams()
    )
    assert api.machined_part_of(host).Shape.Volume == pytest.approx(host_volume, rel=1e-6)
    assert api.machined_part_of(guest).Shape.Volume == pytest.approx(guest_volume, rel=1e-6)


def test_rainure_languette_en_biais(document: Any) -> None:
    host_block, guest_block = stile_block(thickness=80.0), leaning_rail(10.0)
    host, guest, joint = assemble(document, host_block, guest_block, api.make_tongue_groove)
    assert joint.isValid(), joint.getStatusString()
    host_volume, guest_volume = expected_volumes(
        TONGUE, host_block, guest_block, TongueGrooveParams()
    )
    assert api.machined_part_of(host).Shape.Volume == pytest.approx(host_volume, rel=1e-6)
    assert api.machined_part_of(guest).Shape.Volume == pytest.approx(guest_volume, rel=1e-6)


def test_autre_assemblage_refuse_le_biais(document: Any) -> None:
    host = wood(document, "H", (600, 60, 22), (0, 0, 0))
    guest = wood(document, "I", RAIL, placement_of(tilted_rail(10.0)))
    document.recompute()
    with pytest.raises(ValueError, match="équerre"):
        api.make_half_lap(host, guest, check=feasible.feasible_joint)


def test_liste_de_debit_longueur_au_long_point(document: Any) -> None:
    """Bout biais de 10°, dessiné pointe contre la face : cote finie au long point, coupe
    mentionnée, tenon en ajout (ADR 0024, C1 et C2)."""
    host_block, guest_block = stile_block(), tilted_rail(10.0, "pointe")
    assemble(document, host_block, guest_block, api.make_mortise_tenon)
    cut_list = api.cut_list_of(document)
    (line,) = [line for line in cut_list.lines if "I" in line.marks]
    assert line.finished.length == pytest.approx(280 + 60 * math.tan(math.radians(10)), abs=0.05)
    assert [(b.cut_angle, b.blade_tilt) for b in line.bevels] == [(10.0, 0.0)]
    assert line.additions.length > 0  # le tenon


@pytest.mark.parametrize("reference", ["MortisedPiece", "HalfAngle"])
def test_reference_du_tenon_en_biais(document: Any, reference: str) -> None:
    host_block, guest_block = stile_block(), tilted_rail(10.0, "cheval")
    host, guest, joint = assemble(
        document,
        host_block,
        guest_block,
        lambda h, g: api.make_mortise_tenon(h, g, oblique_reference=reference),
    )
    assert joint.isValid(), joint.getStatusString()
    assert joint.ObliqueReference == reference
    assert joint.Version == 2
    host_volume, guest_volume = expected_volumes(
        TENON, host_block, guest_block, MortiseTenonParams(oblique_reference=reference)
    )
    assert api.machined_part_of(host).Shape.Volume == pytest.approx(host_volume, rel=1e-6)
    assert api.machined_part_of(guest).Shape.Volume == pytest.approx(guest_volume, rel=1e-6)


def test_reference_par_defaut_et_liste_des_choix(document: Any) -> None:
    *_, joint = assemble(document, stile_block(), tilted_rail(10.0), api.make_mortise_tenon)
    assert joint.ObliqueReference == "TenonPiece"
    assert joint.getEnumerationsOfProperty("ObliqueReference") == [
        "TenonPiece",
        "MortisedPiece",
        "HalfAngle",
    ]
