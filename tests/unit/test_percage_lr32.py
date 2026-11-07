# SPDX-License-Identifier: LGPL-2.1-or-later
"""Perçage LR32 et taquets de tablette (ADR 0033) : colonnes de trous au pas de 32 mm."""

from __future__ import annotations

import pytest

from freecad.menuiserie.core.geometry import Box, Cylinder, JointError, PlacedBlock, Vec3
from freecad.menuiserie.core.joints import JointKind, strategy_for
from freecad.menuiserie.core.joints.shelf_pins import (
    Neighbor,
    ShelfPinsParams,
    picked_choice,
    pin_rests,
)
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
    return [solid for solid in solids if isinstance(solid, Cylinder)]


def boxes(solids: tuple[object, ...]) -> list[Box]:
    return [solid for solid in solids if isinstance(solid, Box)]


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
    inserts = SHELF_PINS.plan(wall, wall, params).inserts
    assert len(cylinders(inserts)) == 4 and all(p.height == 12.0 for p in cylinders(inserts))
    ledges = boxes(inserts)  # partie saillante, à dessus plat
    assert len(ledges) == 4 and all(b.size(2) == 7.0 and b.size(0) == 5.0 for b in ledges)
    assert values.pin_top(8) == 339.0 + 2.5  # le dessous de la tablette repose dessus
    top = {round(b.hi(0), 6) for b in ledges}  # repère du côté : le haut est vers x décroissant
    assert top == {720.0 - 339.0 + 2.5, 720.0 - 467.0 + 2.5} or top == {
        720.0 - 339.0 - 2.5,
        720.0 - 467.0 - 2.5,
    }


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


def test_zone_du_clic_entre_deux_pieces_assemblees() -> None:
    wall = side()
    middle = panel(-720.0 + 400.0)  # séparation fixe au milieu (de 400 à 419 mm)
    neighbors = (*cabinet(), middle)
    lower = SHELF_PINS.resolve(wall, wall, ShelfPinsParams(neighbors=neighbors))
    assert lower.heights[0] == 83.0 and lower.heights[-1] <= 400.0 - 64.0  # zone la plus grande
    # clic à 550 mm du bas, sur la face +Z : zone du haut, de 419 à 701 mm
    face, height = picked_choice(wall, Vec3(720.0 - 550.0, 250.0, 19.0))
    assert (face, height) == ("plus", 550.0)
    upper = SHELF_PINS.resolve(
        wall, wall, ShelfPinsParams(neighbors=neighbors, face=face, zone_height=height)
    )
    assert upper.heights[0] == 419.0 + 64.0 and upper.heights[-1] <= 701.0 - 64.0
    assert upper.zone_height == (419.0 + 701.0) / 2 and upper.face == "plus"
    assert picked_choice(wall, Vec3(100.0, 250.0, 0.0))[0] == "minus"


def test_appuis_d_aimantation_a_chaque_rang() -> None:
    wall = side()
    values = SHELF_PINS.resolve(wall, wall, ShelfPinsParams(neighbors=cabinet(360.0)))
    rests = pin_rests(wall, values)
    assert len(rests) == 2 * values.rows
    # repère du côté : le haut est vers x décroissant, la face haute de l'appui est en lo(0)
    tops = sorted({round(720.0 - r.lo(0), 6) for r in rests})
    assert tops == [round(values.pin_top(i), 6) for i in range(values.rows)]
    ledges = boxes(SHELF_PINS.plan(wall, wall, ShelfPinsParams(neighbors=cabinet(360.0))).inserts)
    assert {round(720.0 - b.lo(0), 6) for b in ledges} == {round(values.pin_top(8), 6)}


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
