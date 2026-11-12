# SPDX-License-Identifier: LGPL-2.1-or-later
"""Charnières à cuvette dans le document : côté de caisson et porte (issue #156, ADR 0055)."""

from __future__ import annotations

import math
from typing import Any

import pytest

from tests.integration.cadre import stale_or_invalid
from tests.integration.types_assemblages import FRAME, wood

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
api = pytest.importorskip("freecad.menuiserie.api")

SIDE = 720 * 500 * 19
DOOR = 720 * 400 * 16
CUP = math.pi * 17.5**2 * 13  # cuvette Ø35 x 13
PILOT = math.pi * 1.5**2 * 10  # avant-trou de platine Ø3 x 10


def cabinet_side_and_door(document: Any, height: float = 720) -> tuple[Any, Any]:
    """Côté de caisson (hauteur selon X, profondeur selon Y) et porte de recouvrement devant son
    chant avant : la porte est tournée de 90° autour de X (son épaisseur va vers -Y)."""
    side = wood(document, "C", (height, 500, 19), (0, 0, 0), FRAME)
    turned = App.Placement(App.Vector(0, 516, 0), App.Rotation(App.Vector(1, 0, 0), 90))
    door = wood(document, "P", (height, 400, 16), turned, FRAME)
    document.recompute()
    return side, door


def volume(blank: Any) -> float:
    return float(api.machined_part_of(blank).Shape.Volume)


def test_charnieres_entre_un_cote_et_une_porte(document: Any) -> None:
    side, door = cabinet_side_and_door(document)
    joint = api.make_hinges(side, door)
    assert (joint.HostPart, joint.GuestPart, joint.Count) == (side, door, 0)  # nombre automatique
    assert volume(door) == pytest.approx(DOOR - 2 * CUP)
    assert volume(side) == pytest.approx(SIDE - 4 * PILOT)
    assert joint.Shape.Volume == pytest.approx(2 * CUP)
    assert (joint.CupDiameter.Value, joint.EdgeDistance.Value, joint.ScrewPitch.Value) == (
        35,
        5,
        32,
    )
    assert stale_or_invalid(document) == []


def test_trois_charnieres_pour_une_porte_haute(document: Any) -> None:
    side, door = cabinet_side_and_door(document, height=1200)
    joint = api.make_hinges(side, door)
    assert joint.isValid()
    assert volume(door) == pytest.approx(1200 * 400 * 16 - 3 * CUP)
    joint.Count = 2
    joint.EndDistance = 150
    document.recompute()
    assert joint.isValid() and volume(door) == pytest.approx(1200 * 400 * 16 - 2 * CUP)
    assert stale_or_invalid(document) == []


def test_cuvette_trop_profonde_en_erreur(document: Any) -> None:
    side, door = cabinet_side_and_door(document)
    joint = api.make_hinges(side, door)
    joint.CupDepth = 14
    document.recompute()
    assert not joint.isValid()
    assert "trop profonde" in joint.getStatusString()


def test_charnieres_reference_du_catalogue(document: Any) -> None:
    side, door = cabinet_side_and_door(document)
    joint = api.make_hinges(side, door, reference="charniere-cuvette-35")
    assert (joint.CupDiameter.Value, joint.CupDepth.Value) == (35, 13)
    assert (joint.EdgeDistance.Value, joint.ScrewPitch.Value) == (5, 32)
    assert joint.HardwareReference == "charniere-cuvette-35"


def test_charnieres_dans_la_liste_de_debit(document: Any) -> None:
    side, door = cabinet_side_and_door(document)
    api.make_hinges(side, door, reference="charniere-cuvette-35")
    [item] = api.cut_list_of(document).hardware
    assert (item.kind.value, item.diameter, item.length, item.quantity) == ("Hinge", 35, 13, 2)
    assert item.reference == "charniere-cuvette-35"
