# SPDX-License-Identifier: LGPL-2.1-or-later
"""Perçage LR32 et taquets de tablette (ADR 0033) : colonnes de trous au pas de 32 mm."""

from __future__ import annotations

from dataclasses import replace

import pytest

from freecad.menuiserie.core.geometry import Box, Cylinder, JointError, PlacedBlock, Vec3
from freecad.menuiserie.core.joints import MAX_PLAN_SOLIDS, JointKind, JointPlan, strategy_for
from freecad.menuiserie.core.joints.shelf_pins import (
    Neighbor,
    ShelfPinsParams,
    facing_side,
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
    pins = cylinders(inserts)  # taquets ronds d'un tenant : tige de 12 + saillie de 7
    assert len(pins) == 4 and not boxes(inserts)
    assert all(p.height == 19.0 and p.radius == 2.5 for p in pins)
    assert all(p.base.z == 19.0 - 12.0 and p.axis.sign > 0 for p in pins)  # du fond du trou
    assert values.pin_top(8) == 339.0 + 2.5  # le dessous de la tablette repose dessus
    assert {round(720.0 - p.base.x, 6) for p in pins} == {339.0, 467.0}


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
    pins = cylinders(SHELF_PINS.plan(wall, wall, ShelfPinsParams(neighbors=cabinet(360.0))).inserts)
    pin_tops = {round(720.0 - p.base.x + p.radius, 6) for p in pins}  # haut du taquet rond
    assert pin_tops == {round(values.pin_top(8), 6)}


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


def other_side(x: float, z: float = 0.0) -> PlacedBlock:
    """Côté debout parallèle à :func:`side`, à ``x`` (document), son haut à ``z``."""
    return placed((720.0, 500.0, 19.0), rotation_y(90.0), (x, 0.0, z))


def test_montant_oppose_en_face_de_la_face_percee() -> None:
    shelf = block((600.0, 500.0, 19.0), (19.0, 0.0, -400.0))  # tablette : pas un côté debout
    far, near = other_side(900.0), other_side(619.0, 19.0)
    found = facing_side(side(), "plus", (shelf, far, near))
    assert found is not None
    index, face, low = found
    # le plus proche ; sa face -Z regarde le premier côté ; son bas 19 mm plus haut
    assert (index, face) == (2, "minus") and low == pytest.approx(19.0)


def test_pas_de_montant_oppose_de_l_autre_cote_ni_decale() -> None:
    assert facing_side(side(), "minus", (other_side(619.0),)) is None
    assert facing_side(side(), "plus", (other_side(619.0, 600.0),)) is None  # recouvre trop peu


def test_pas_trop_petit_refuse() -> None:
    wall = side()
    with pytest.raises(JointError, match="trop petit"):
        SHELF_PINS.plan(wall, wall, ShelfPinsParams(pitch=1.0))  # trous de 5 mm qui se chevauchent
    SHELF_PINS.plan(wall, wall, ShelfPinsParams(pitch=7.0))  # 5 mm + 2 mm de matière


def test_un_seul_perçage_pour_les_deux_montants() -> None:
    wall, other = side(), other_side(619.0)
    shelf = Neighbor(block((600.0, 500.0, 19.0), (19.0, 0.0, -360.0)), False)
    params = ShelfPinsParams(neighbors=(shelf,), guest_neighbors=(shelf,))
    plan = SHELF_PINS.plan(wall, other, params)
    single = SHELF_PINS.plan(wall, wall, params)
    assert len(plan.guest_cuts) == len(single.host_cuts) and plan.host_cuts == single.host_cuts
    assert all(hole.base.z == 0.0 for hole in cylinders(plan.guest_cuts))  # face -Z du montant
    assert len(plan.inserts) == 2 * len(single.inserts)  # taquets des deux côtés
    values = SHELF_PINS.resolve(wall, other, params)
    assert values.count == 4 and values.hole_count == 2 * len(single.host_cuts)
    alone = SHELF_PINS.plan(wall, other, replace(params, both_sides=False))
    assert alone.guest_cuts == ()


def test_plan_plafonne_le_nombre_de_formes() -> None:
    hole = Box(Vec3(0.0, 0.0, 0.0), Vec3(1.0, 1.0, 1.0))
    JointPlan(host_cuts=(hole,) * MAX_PLAN_SOLIDS)
    with pytest.raises(JointError, match="formes d'usinage"):
        JointPlan(host_cuts=(hole,) * MAX_PLAN_SOLIDS, inserts=(hole,))


def test_taquets_du_montant_oppose_au_niveau_de_ceux_du_cote() -> None:
    """Retour de jv : le montant opposé posé plus haut (19 mm) garde ses taquets au niveau de
    ceux du côté, sous la même tablette."""
    wall, other = side(), other_side(619.0, 19.0)
    shelf = Neighbor(block((600.0, 500.0, 19.0), (19.0, 0.0, -360.0)), False)
    params = ShelfPinsParams(neighbors=(shelf,), guest_neighbors=(shelf,))
    plan = SHELF_PINS.plan(wall, other, params)
    pins = cylinders(plan.inserts)  # tous dans le repère du côté : x = 720 - hauteur
    host_levels = {round(p.base.x, 6) for p in pins if p.base.z < 19.0 + 1e-6}
    guest_levels = {round(p.base.x, 6) for p in pins if p.base.z > 600.0}
    assert len(pins) == 4 and host_levels == guest_levels


def test_trous_du_montant_oppose_gardes_dans_sa_zone_libre() -> None:
    """Fond assemblé au montant opposé seulement : ses trous alignés sur ceux du côté
    s'arrêtent à 64 mm du fond (le premier rang du côté, à 64 mm du bas, n'y est pas percé)."""
    wall, other = side(), other_side(619.0)
    bottom = Neighbor(block((600.0, 500.0, 19.0), (19.0, 0.0, -720.0)), True)
    params = ShelfPinsParams(guest_neighbors=(bottom,))
    plan = SHELF_PINS.plan(wall, other, params)
    assert len(plan.host_cuts) == 38 and len(plan.guest_cuts) == 36
