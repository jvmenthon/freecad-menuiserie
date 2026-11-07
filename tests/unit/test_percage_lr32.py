# SPDX-License-Identifier: LGPL-2.1-or-later
"""Perçage LR32 et taquets de tablette (ADR 0033) : colonnes de trous au pas de 32 mm."""

from __future__ import annotations

import pytest

from freecad.menuiserie.core.geometry import Cylinder, JointError, PlacedBlock
from freecad.menuiserie.core.joints import JointKind, strategy_for
from freecad.menuiserie.core.joints.shelf_pins import Neighbor, ShelfPinsParams
from tests.unit.aides_assemblages import block, placed, rotation_y

SHELF_PINS = strategy_for(JointKind.SHELF_PINS)


def side() -> PlacedBlock:
    """Côté de caisson debout : 720 de haut (longueur locale X), 500 de profondeur, 19 d'épais ;
    sa face intérieure est la face +Z locale (x = 19 dans le document)."""
    return placed((720.0, 500.0, 19.0), rotation_y(90.0), (0.0, 0.0, 0.0))


def panel(z: float, x: float = 19.0, fixed: bool = True) -> Neighbor:
    """Planche horizontale de 19 mm contre la face intérieure du côté, dont le dessous est à
    ``z`` (document)."""
    return Neighbor(block((600.0, 500.0, 19.0), (x, 0.0, z)), fixed)


def cabinet(*shelves: float) -> tuple[Neighbor, ...]:
    """Fond et dessus assemblés au côté, plus des tablettes libres (dessous à la hauteur
    donnée au-dessus du fond, en mm)."""
    return (panel(-720.0), panel(-19.0), *(panel(-720.0 + h, fixed=False) for h in shelves))


def cylinders(solids: tuple[object, ...]) -> list[Cylinder]:
    assert all(isinstance(solid, Cylinder) for solid in solids)
    return [solid for solid in solids if isinstance(solid, Cylinder)]


def test_percage_limite_aux_pieces_assemblees() -> None:
    wall = side()
    params = ShelfPinsParams(neighbors=cabinet())
    values = SHELF_PINS.resolve(wall, wall, params)
    # zone libre de 19 à 701 mm, 64 mm de marge : de 83 à 637 mm, 18 rangs au pas de 32
    assert (values.rows, values.hole_count) == (18, 36)
    assert values.heights[0] == 83.0 and values.heights[-1] == 83.0 + 17 * 32
    assert (values.edge_distance, values.end_margin, values.count) == (37.0, 64.0, 0)
    holes = cylinders(SHELF_PINS.plan(wall, wall, params).host_cuts)
    assert len(holes) == 36
    assert {round(h.base.y, 6) for h in holes} == {37.0, 463.0}
    assert all(h.radius == 2.5 and h.height == 12.0 and h.base.z == 19.0 for h in holes)
    levels = sorted({round(h.base.x, 6) for h in holes})  # repère du côté : bas à x = 720
    assert levels[-1] == 720.0 - 83.0 and levels[0] == 720.0 - 83.0 - 17 * 32


def test_sans_voisines_tout_le_cote_est_perce_sans_taquet() -> None:
    wall = side()
    values = SHELF_PINS.resolve(wall, wall, ShelfPinsParams())
    assert (values.rows, values.heights[0], values.count) == (19, 64.0, 0)


def test_taquet_sous_chaque_tablette() -> None:
    wall = side()
    params = ShelfPinsParams(neighbors=cabinet(360.0, 500.0))
    values = SHELF_PINS.resolve(wall, wall, params)
    assert values.pin_rows == (8, 12) and values.count == 4  # 83 + 32 x 8 = 339, 83 + 32 x 12 = 467
    pins = cylinders(SHELF_PINS.plan(wall, wall, params).inserts)
    assert len(pins) == 4 and all(p.height == 12.0 + 7.0 for p in pins)
    assert values.pin_top(8) == 339.0 + 2.5  # le dessous de la tablette repose dessus


def test_taquets_au_rang_choisi_ou_absents() -> None:
    wall = side()
    near = ShelfPinsParams(neighbors=cabinet(360.0), pin_row=1)
    values = SHELF_PINS.resolve(wall, wall, near)
    assert (values.pin_rows, values.pin_row) == ((0,), 1)
    bare = ShelfPinsParams(neighbors=cabinet(360.0), with_pins=False)
    plan = SHELF_PINS.plan(wall, wall, bare)
    assert not plan.inserts and SHELF_PINS.resolve(wall, wall, bare).count == 0


def test_face_interieure_automatique_ou_choisie() -> None:
    wall = side()
    inside = cylinders(SHELF_PINS.plan(wall, wall, ShelfPinsParams(neighbors=cabinet())).host_cuts)
    assert inside[0].base.z == 19.0
    outside = (panel(-720.0, x=-600.0), panel(-19.0, x=-600.0))  # planches de l'autre côté
    other = ShelfPinsParams(neighbors=outside)
    assert cylinders(SHELF_PINS.plan(wall, wall, other).host_cuts)[0].base.z == 0.0
    forced = ShelfPinsParams(neighbors=cabinet(), face="minus")
    assert cylinders(SHELF_PINS.plan(wall, wall, forced).host_cuts)[0].base.z == 0.0


def test_valeurs_automatiques_a_zero() -> None:
    wall = side()
    values = SHELF_PINS.resolve(wall, wall, ShelfPinsParams(hole_diameter=0, hole_depth=0))
    assert (values.hole_diameter, values.hole_depth) == (5.0, 12.0)


def test_refus() -> None:
    flat = block((720.0, 500.0, 19.0))
    with pytest.raises(JointError, match="debout"):
        SHELF_PINS.plan(flat, flat, ShelfPinsParams())
    wall = side()
    with pytest.raises(JointError, match="trop petit"):
        SHELF_PINS.plan(wall, wall, ShelfPinsParams(rows=30))
    with pytest.raises(JointError, match="trop petit"):
        SHELF_PINS.plan(wall, wall, ShelfPinsParams(edge_distance=250))
    with pytest.raises(JointError, match="rang"):
        SHELF_PINS.plan(wall, wall, ShelfPinsParams(rows=5, pin_row=6))
    thin = placed((720.0, 500.0, 12.0), rotation_y(90.0), (0.0, 0.0, 0.0))
    with pytest.raises(JointError, match="trop profond"):
        SHELF_PINS.plan(thin, thin, ShelfPinsParams())
    with pytest.raises(JointError, match="invalide"):
        ShelfPinsParams(rows=-1)
    with pytest.raises(JointError, match="strictement positifs"):
        ShelfPinsParams(pitch=0)
