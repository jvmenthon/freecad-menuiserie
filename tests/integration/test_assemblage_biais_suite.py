# SPDX-License-Identifier: LGPL-2.1-or-later
"""Feuillure, mi-bois, onglet, queue d'aronde et tourillons entre pièces en biais dans FreeCAD
(ADR 0034, lot S) : pièces usinées valides, un seul solide, volumes égaux à ceux de ``core``."""

from __future__ import annotations

import math
from typing import Any

import pytest

from freecad.menuiserie.core._polyhedron import Polyhedron
from freecad.menuiserie.core.geometry import Box, PlacedBlock
from freecad.menuiserie.core.joints import JointKind, strategy_for
from freecad.menuiserie.core.joints.dovetail import DovetailParams
from freecad.menuiserie.core.joints.half_lap import HalfLapParams
from freecad.menuiserie.core.joints.miter import MiterParams
from freecad.menuiserie.core.joints.rabbet import RabbetParams
from tests.integration.cadre import stale_or_invalid
from tests.integration.test_assemblage_biais import placement_of
from tests.integration.types_assemblages import wood
from tests.unit.aides_assemblages import block, placed, rotation_z
from tests.unit.aides_biais import product, rotation_x, rotation_y

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
api = pytest.importorskip("freecad.menuiserie.api")


def volume_of(solid: object) -> float:
    if isinstance(solid, Polyhedron):
        return solid.volume()
    assert isinstance(solid, Box)
    return solid.size(0) * solid.size(1) * solid.size(2)


def size_of(piece: PlacedBlock) -> tuple[float, float, float]:
    box = piece.dimensions
    return (box.length, box.width, box.thickness)


def check(
    document: Any,
    kind: JointKind,
    params: Any,
    host_block: PlacedBlock,
    guest_block: PlacedBlock,
    make: Any,
) -> None:
    host = wood(document, "H", size_of(host_block), placement_of(host_block))
    guest = wood(document, "I", size_of(guest_block), placement_of(guest_block))
    document.recompute()
    joint = make(host, guest)
    document.recompute()
    assert joint.isValid(), joint.getStatusString()
    plan = strategy_for(kind).plan(host_block, guest_block, params)
    host_expected = math.prod(size_of(host_block)) - sum(volume_of(s) for s in plan.host_cuts)
    guest_expected = (
        math.prod(size_of(guest_block))
        - sum(volume_of(s) for s in plan.guest_cuts)
        - sum(volume_of(s) for s in plan.guest_trims)
        + sum(volume_of(s) for s in plan.guest_additions)
    )
    host_shape = api.machined_part_of(host).Shape
    guest_shape = api.machined_part_of(guest).Shape
    assert len(host_shape.Solids) == len(guest_shape.Solids) == 1
    assert host_shape.isValid() and guest_shape.isValid()
    assert host_shape.Volume == pytest.approx(host_expected, rel=1e-5)
    assert guest_shape.Volume == pytest.approx(guest_expected, rel=1e-5)
    assert stale_or_invalid(document) == []


def test_feuillure_en_biais(document: Any) -> None:
    host = placed((600.0, 60.0, 22.0), rotation_z(0.0), (0.0, 0.0, 0.0))
    guest = placed((50.0, 20.0, 22.0), rotation_z(30.0), (300.0, 10.0, 0.0))
    check(document, JointKind.RABBET, RabbetParams(), host, guest, api.make_rabbet)


def test_mi_bois_en_biais(document: Any) -> None:
    host = placed((300.0, 40.0, 20.0), rotation_z(0.0), (0.0, 0.0, 0.0))
    angle = math.radians(30.0)
    base = (
        150.0 - (150.0 * math.cos(angle) - 20.0 * math.sin(angle)),
        20.0 - (150.0 * math.sin(angle) + 20.0 * math.cos(angle)),
        0.0,
    )
    guest = placed((300.0, 40.0, 20.0), rotation_z(30.0), base)
    check(document, JointKind.HALF_LAP, HalfLapParams(), host, guest, api.make_half_lap)


@pytest.mark.parametrize("degrees", [60.0, 120.0])
def test_onglet_en_biais(document: Any, degrees: float) -> None:
    angle = math.radians(degrees)
    base = (
        -100.0 * math.cos(angle) + 40.0 * math.sin(angle),
        -100.0 * math.sin(angle) - 40.0 * math.cos(angle),
        0.0,
    )
    host = placed((500.0, 40.0, 20.0), rotation_z(0.0), (-100.0, 0.0, 0.0))
    guest = placed((500.0, 40.0, 20.0), rotation_z(degrees), base)
    check(document, JointKind.MITER, MiterParams(), host, guest, api.make_miter)


@pytest.mark.parametrize("degrees", [10.0, 30.0])
def test_queue_d_aronde_en_biais(document: Any, degrees: float) -> None:
    size = (400.0, 150.0, 18.0)
    guest = placed(size, product(rotation_x(degrees), rotation_y(-90.0)), (18.0, 0.0, 18.0))
    check(document, JointKind.DOVETAIL, DovetailParams(), block(size), guest, api.make_dovetail)


def test_tourillons_en_biais_pieces_valides(document: Any) -> None:
    from tests.unit.aides_biais import stile_block, tilted_rail

    host_block, guest_block = stile_block(), tilted_rail(10.0)
    host = wood(document, "H", (600, 60, 22), (0, 0, 0))
    guest = wood(document, "I", (280, 60, 22), placement_of(guest_block))
    document.recompute()
    joint = api.make_dowels(host, guest)
    document.recompute()
    assert joint.isValid(), joint.getStatusString()
    assert api.machined_part_of(host).Shape.isValid()
    assert api.machined_part_of(guest).Shape.isValid()
    assert host_block and stale_or_invalid(document) == []
