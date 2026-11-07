# SPDX-License-Identifier: LGPL-2.1-or-later
"""Perçage LR32 et taquets de tablette (ADR 0033) : colonnes de trous au pas de 32 mm."""

from __future__ import annotations

from itertools import pairwise

import pytest

from freecad.menuiserie.core.geometry import Cylinder, JointError, PlacedBlock
from freecad.menuiserie.core.joints import JointKind, strategy_for
from freecad.menuiserie.core.joints.shelf_pins import ShelfPinsParams
from tests.unit.aides_assemblages import block, placed, rotation_y

SHELF_PINS = strategy_for(JointKind.SHELF_PINS)


def side() -> PlacedBlock:
    """Côté de caisson debout : 720 de haut (longueur locale X), 500 de profondeur, 19 d'épais."""
    return placed((720.0, 500.0, 19.0), rotation_y(90.0), (0.0, 0.0, 0.0))


def cylinders(solids: tuple[object, ...]) -> list[Cylinder]:
    assert all(isinstance(solid, Cylinder) for solid in solids)
    return [solid for solid in solids if isinstance(solid, Cylinder)]


def test_deux_colonnes_au_pas_de_32() -> None:
    panel = side()
    values = SHELF_PINS.resolve(panel, panel, ShelfPinsParams())
    assert (values.rows, values.hole_count) == (19, 38)  # (720 - 2 x 64) / 32 = 18,5 pas
    assert (values.edge_distance, values.end_margin) == (37.0, 64.0)
    holes = cylinders(SHELF_PINS.plan(panel, panel, ShelfPinsParams()).host_cuts)
    assert len(holes) == 38
    assert {round(h.base.y, 6) for h in holes} == {37.0, 463.0}
    levels = sorted({round(h.base.x, 6) for h in holes})
    assert levels[0] == 656.0 - 18 * 32 and levels[-1] == 656.0  # premier trou à 64 du bas
    assert {round(b - a, 6) for a, b in pairwise(levels)} == {32.0}
    assert all(h.radius == 2.5 and h.height == 12.0 for h in holes)


def test_taquets_au_rang_du_milieu_puis_au_rang_choisi() -> None:
    panel = side()
    plan = SHELF_PINS.plan(panel, panel, ShelfPinsParams())
    pins = cylinders(plan.inserts)
    assert len(pins) == 2 and {round(p.base.x, 6) for p in pins} == {656.0 - 9 * 32}
    assert all(p.height == 12.0 + 7.0 for p in pins)
    low = SHELF_PINS.plan(panel, panel, ShelfPinsParams(pin_row=1))
    assert {round(p.base.x, 6) for p in cylinders(low.inserts)} == {656.0}
    values = SHELF_PINS.resolve(panel, panel, ShelfPinsParams())
    assert (values.pin_row, values.count) == (10, 2)


def test_sans_taquets_et_face_opposee() -> None:
    panel = side()
    plain = SHELF_PINS.plan(panel, panel, ShelfPinsParams(with_pins=False))
    assert not plain.inserts and len(plain.host_cuts) == 38
    assert SHELF_PINS.resolve(panel, panel, ShelfPinsParams(with_pins=False)).count == 0
    top = cylinders(SHELF_PINS.plan(panel, panel, ShelfPinsParams()).host_cuts)[0]
    back = cylinders(SHELF_PINS.plan(panel, panel, ShelfPinsParams(reversed=True)).host_cuts)[0]
    assert top.axis != back.axis and top.base.z != back.base.z


def test_refus() -> None:
    flat = block((720.0, 500.0, 19.0))
    with pytest.raises(JointError, match="debout"):
        SHELF_PINS.plan(flat, flat, ShelfPinsParams())
    panel = side()
    with pytest.raises(JointError, match="trop petit"):
        SHELF_PINS.plan(panel, panel, ShelfPinsParams(rows=30))
    with pytest.raises(JointError, match="trop petit"):
        SHELF_PINS.plan(panel, panel, ShelfPinsParams(edge_distance=250))
    with pytest.raises(JointError, match="rang"):
        SHELF_PINS.plan(panel, panel, ShelfPinsParams(rows=5, pin_row=6))
    thin = placed((720.0, 500.0, 12.0), rotation_y(90.0), (0.0, 0.0, 0.0))
    with pytest.raises(JointError, match="trop profond"):
        SHELF_PINS.plan(thin, thin, ShelfPinsParams())
    with pytest.raises(JointError, match="invalide"):
        ShelfPinsParams(rows=-1)
