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
    joint = api.make_foot(panel, foot_material="wood")
    assert joint.HostPart == joint.GuestPart == panel
    assert volume(panel) == pytest.approx(PANEL - 4 * math.pi * 5**2 * 12)
    assert joint.Shape.Volume > 0  # embases et tiges rapportées
    assert joint.Columns == 0 and joint.Rows == 0  # automatique
    joint.Columns = 3
    document.recompute()
    assert volume(panel) == pytest.approx(PANEL - 6 * math.pi * 5**2 * 12)
    assert api.machined_part_of(panel).Joints == [joint]
    assert stale_or_invalid(document) == []


def test_matiere_des_pieds(document: Any) -> None:
    panel = wood(document, "F", (600, 500, 19), (0, 0, 0))
    document.recompute()
    joint = api.make_foot(panel, foot_material="wood")
    assert joint.FootMaterial == "wood"
    assert volume(panel) < PANEL  # tige percée dans le panneau
    other = wood(document, "G", (600, 500, 19), (0, 900, 0))
    document.recompute()
    plastic = api.make_foot(other)
    assert plastic.FootMaterial == "plastic"
    assert volume(other) == pytest.approx(PANEL)  # vissé : le panneau n'est pas percé
    joint.FootMaterial = "plastic"
    document.recompute()
    assert joint.isValid() and volume(panel) == pytest.approx(PANEL)


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


def upright_side(document: Any, thickness: float = 19) -> Any:
    """Côté de caisson debout : 720 de haut (longueur de la pièce, tournée sur sa tranche)."""
    where = App.Placement(App.Vector(thickness, 0, 720), App.Rotation(App.Vector(0, 1, 0), 90))
    side = wood(document, "S", (720, 500, thickness), where)
    document.recompute()
    return side


def shelf(document: Any, height: float) -> Any:
    """Planche horizontale contre la face intérieure du côté (x = 19), dessous à ``height`` du
    bas du côté (le côté va de z = -720 à 0)."""
    where = App.Placement(App.Vector(19, 0, -720 + height), App.Rotation())
    board = wood(document, "T", (600, 500, 19), where)
    document.recompute()
    return board


def test_percage_lr32_seul(document: Any) -> None:
    side = upright_side(document)
    joint = api.make_shelf_pins(side)
    assert joint.HostPart == joint.GuestPart == side
    assert (joint.Rows, joint.PinRow, joint.WithPins, joint.Face) == (0, 0, True, "auto")
    hole = math.pi * 2.5**2 * 12
    assert volume(side) == pytest.approx(720 * 500 * 19 - 38 * hole)  # 19 rangs, 2 colonnes
    joint.Rows = 5
    document.recompute()
    assert joint.isValid() and volume(side) == pytest.approx(720 * 500 * 19 - 10 * hole)
    assert api.machined_part_of(side).Joints == [joint]
    assert stale_or_invalid(document) == []


def test_taquets_sous_chaque_tablette(document: Any) -> None:
    side = upright_side(document)
    board = shelf(document, 360)
    joint = api.make_shelf_pins(side)
    assert board in joint.Neighbors
    pin = math.pi * 2.5**2 * (12 + 7)
    assert joint.Shape.Volume == pytest.approx(2 * pin)  # deux taquets sous la tablette
    board.Placement = App.Placement(App.Vector(19, 0, -720 + 424), App.Rotation())  # monte de 64
    document.recompute()
    assert joint.isValid() and joint.Shape.Volume == pytest.approx(2 * pin)
    joint.WithPins = False
    document.recompute()
    assert not joint.Shape.Solids  # plus de taquets
    assert stale_or_invalid(document) == []


def test_percage_lr32_refuse_sur_panneau_couche(document: Any) -> None:
    panel = wood(document, "F", (600, 500, 19), (0, 0, 0))
    document.recompute()
    joint = api.make_shelf_pins(panel)
    assert not joint.isValid()
    assert "debout" in joint.getStatusString()


def test_percage_lr32_reference_du_catalogue(document: Any) -> None:
    joint = api.make_shelf_pins(upright_side(document), reference="taquet-tablette-8")
    assert joint.HoleDiameter.Value == 8


def sides(document: Any, gap: float = 12.7) -> tuple[Any, Any]:
    host = wood(document, "C", (500, 300, 19), (0, 0, 0), FRAME)
    where = App.Placement(App.Vector(0, 50, 19 + gap), App.Rotation())
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


def test_cotes_qui_se_touchent_acceptes_puis_ecartes_en_reduisant_le_tiroir(
    document: Any,
) -> None:
    host, guest = sides(document, gap=0.0)
    joint = api.make_drawer_slide(host, guest)
    assert joint.isValid()
    assert api.slide_shortfall(joint) == pytest.approx(12.7)
    before = guest.Placement.Base
    api.make_room_for_slide(joint, "drawer")
    assert api.slide_shortfall(joint) == 0.0
    assert (guest.Placement.Base - before).Length == pytest.approx(12.7)
    assert stale_or_invalid(document) == []


def test_cotes_qui_se_touchent_puis_ecartes_en_elargissant_le_meuble(document: Any) -> None:
    host, guest = sides(document, gap=0.0)
    joint = api.make_drawer_slide(host, guest)
    before = host.Placement.Base
    api.make_room_for_slide(joint, "cabinet")
    assert api.slide_shortfall(joint) == 0.0
    assert (host.Placement.Base - before).Length == pytest.approx(12.7)
    assert stale_or_invalid(document) == []


def test_jeu_suffisant_rien_a_ecarter(document: Any) -> None:
    host, guest = sides(document)
    joint = api.make_drawer_slide(host, guest)
    assert api.slide_shortfall(joint) == 0.0
    assert api.make_room_for_slide(joint, "drawer") == []
    with pytest.raises(ValueError, match="drawer"):
        api.make_room_for_slide(joint, "autre")
