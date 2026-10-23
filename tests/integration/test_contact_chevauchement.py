# SPDX-License-Identifier: LGPL-2.1-or-later
"""Tenon et queue d'aronde entre pièces dessinées hors tout, qui se chevauchent (ADR 0016) :
la pièce usinée de l'invitée est raccourcie jusqu'au contact puis reçoit ses ajouts."""

from __future__ import annotations

from typing import Any

import pytest

from tests.integration.cadre import stale_or_invalid
from tests.integration.types_assemblages import DOVETAIL_VOLUME, wood

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
api = pytest.importorskip("freecad.menuiserie.api")

TENON = 40 * 40 * 7  # tenon automatique d'une traverse 60 x 22 dans un montant de 60
MORTISE = 40 * 42 * 7


def machined(*parts: Any) -> list[Any]:
    return [api.machined_part_of(part).Shape for part in parts]


def test_tenon_traverse_dessinee_hors_tout(document: Any) -> None:
    """Traverse 340 dessinée jusqu'au chant extérieur du montant : raccourcie de 60 mm."""
    stile = wood(document, "M", (600, 60, 22), (0, 0, 0))
    rail = wood(document, "T", (340, 60, 22), (60, 0, 90))
    document.recompute()
    joint = api.make_mortise_tenon(stile, rail)
    document.recompute()
    assert joint.isValid(), joint.getStatusString()
    stile_shape, rail_shape = machined(stile, rail)
    assert stile_shape.Volume == pytest.approx(600 * 60 * 22 - MORTISE)
    assert rail_shape.Volume == pytest.approx(280 * 60 * 22 + TENON)
    assert rail_shape.BoundBox.YMin == pytest.approx(60 - 40)  # le tenon entre de 40 mm
    assert stile_shape.common(rail_shape).Volume == pytest.approx(0, abs=1e-6)
    assert rail.Length.Value == 340  # la brute garde ses cotes
    assert stale_or_invalid(document) == []


def test_queue_d_aronde_planches_dessinees_hors_tout(document: Any) -> None:
    """Angle de caisson, les deux planches hors tout : l'invitée perd l'épaisseur de l'hôte,
    ses queues traversent l'hôte."""
    host = wood(document, "H", (400, 150, 18), (0, 0, 0))
    guest_place = App.Placement(App.Vector(18, 0, 0), App.Rotation(App.Vector(0, 1, 0), -90))
    guest = wood(document, "I", (418, 150, 18), guest_place)
    document.recompute()
    joint = api.make_dovetail(host, guest)
    document.recompute()
    assert joint.isValid(), joint.getStatusString()
    host_shape, guest_shape = machined(host, guest)
    assert host_shape.Volume == pytest.approx(400 * 150 * 18 - DOVETAIL_VOLUME)
    assert guest_shape.Volume == pytest.approx(400 * 150 * 18 + DOVETAIL_VOLUME)
    assert host_shape.common(guest_shape).Volume == pytest.approx(0, abs=1e-6)
    assert stale_or_invalid(document) == []
