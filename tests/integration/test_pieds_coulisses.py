# SPDX-License-Identifier: LGPL-2.1-or-later
"""Pieds de caisson et coulisses de tiroir dans le document (issue #159, ADR 0033)."""

from __future__ import annotations

import math
from typing import Any

import pytest

from tests.integration.cadre import stale_or_invalid
from tests.integration.types_assemblages import FRAME, wood

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
api = pytest.importorskip("freecad.menuiserie.api")

PANEL = 600 * 500 * 19
SIDE = 500 * 300 * 19
DRAWER_SIDE = 450 * 150 * 16
PILOT_HOLE = math.pi * 1.5**2 * 8  # Ø3 x 8 dans le côté du tiroir


def volume(blank: Any) -> float:
    return float(api.machined_part_of(blank).Shape.Volume)


def test_pieds_sous_un_panneau(document: Any) -> None:
    panel = wood(document, "F", (600, 500, 19), (0, 0, 0))
    document.recompute()
    joint = api.make_foot(panel)
    assert joint.HostPart == joint.GuestPart == panel
    assert volume(panel) == pytest.approx(PANEL - 4 * math.pi * 5**2 * 12)
    assert joint.Shape.Volume > 0  # embases et tiges rapportées
    joint.Columns = 3
    document.recompute()
    assert volume(panel) == pytest.approx(PANEL - 6 * math.pi * 5**2 * 12)
    assert api.machined_part_of(panel).Joints == [joint]
    assert stale_or_invalid(document) == []


def test_pieds_refuses_sur_panneau_pose_en_biais(document: Any) -> None:
    panel = wood(document, "F", (600, 500, 19), (0, 0, 0), FRAME)
    document.recompute()
    joint = api.make_foot(panel)
    assert not joint.isValid()
    assert "couché" in joint.getStatusString()


def test_pieds_reference_du_catalogue(document: Any) -> None:
    panel = wood(document, "F", (600, 500, 19), (0, 0, 0))
    document.recompute()
    joint = api.make_foot(panel, reference="pied-caisson-m8-40")
    assert (joint.StemDiameter.Value, joint.BaseDiameter.Value, joint.Height.Value) == (8, 40, 12)


def sides(document: Any) -> tuple[Any, Any]:
    host = wood(document, "C", (500, 300, 19), (0, 0, 0), FRAME)
    where = App.Placement(App.Vector(0, 50, 31.7), App.Rotation())
    guest = wood(document, "T", (450, 150, 16), where, FRAME)
    document.recompute()
    return host, guest


def test_coulisse_entre_deux_cotes(document: Any) -> None:
    host, guest = sides(document)
    joint = api.make_drawer_slide(host, guest)
    assert volume(host) == pytest.approx(SIDE - 3 * math.pi * 2.5**2 * 12)
    assert volume(guest) == pytest.approx(DRAWER_SIDE - 3 * PILOT_HOLE)
    assert joint.Shape.Volume == pytest.approx(450 * 45 * 12.7)
    joint.Length = 400
    document.recompute()
    assert joint.Shape.Volume == pytest.approx(400 * 45 * 12.7)
    assert stale_or_invalid(document) == []


def test_coulisse_trop_longue_en_erreur(document: Any) -> None:
    host, guest = sides(document)
    joint = api.make_drawer_slide(host, guest)
    joint.Length = 600
    document.recompute()
    assert not joint.isValid()
    assert "trop longue" in joint.getStatusString()


def test_coulisse_reference_du_catalogue(document: Any) -> None:
    host, guest = sides(document)
    joint = api.make_drawer_slide(host, guest, reference="coulisse-billes-400")
    assert (joint.Length.Value, joint.Thickness.Value) == (400, 12.7)
