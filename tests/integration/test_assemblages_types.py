# SPDX-License-Identifier: LGPL-2.1-or-later
"""Rainure-languette, feuillure et tourillons dans le document (J3c : R1, R2, T3, T4)."""

from __future__ import annotations

from typing import Any

import pytest

from tests.integration.cadre import stale_or_invalid
from tests.integration.types_assemblages import (
    DOWEL_HOLE_VOLUME,
    DOWEL_VOLUME,
    DOWELS,
    SCENARIOS,
    TONGUE_GROOVE,
    Montage,
    Scenario,
    build,
    wood,
)

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
api = pytest.importorskip("freecad.menuiserie.api")

LENGTH = "App::PropertyLength"
DISTANCE = "App::PropertyDistance"
BOOL = "App::PropertyBool"
COMMON = {"HostPart", "GuestPart", "Version"}
Row = tuple[str, str, str, object]
# Propriétés propres à chaque type : nom, type, groupe, défaut (§ 4.3.3 et 4.4.3).
PROPERTIES: dict[str, list[Row]] = {
    "make_tongue_groove": [
        ("TongueThickness", LENGTH, "Languette", 0.0),
        ("TongueLength", LENGTH, "Languette", 10.0),
        ("ThicknessOffset", DISTANCE, "Languette", 0.0),
        ("GrooveClearance", LENGTH, "Rainure", 1.0),
        ("ThroughGroove", BOOL, "Rainure", True),
    ],
    "make_rabbet": [("Through", BOOL, "Feuillure", True)],
    "make_dowels": [
        ("Diameter", LENGTH, "Tourillons", 0.0),
        ("DowelLength", LENGTH, "Tourillons", 0.0),
        ("HostDepth", LENGTH, "Tourillons", 0.0),
        ("Count", "App::PropertyIntegerConstraint", "Tourillons", 0),
        ("EdgeDistance", LENGTH, "Tourillons", 0.0),
        ("ThicknessOffset", DISTANCE, "Tourillons", 0.0),
        ("HoleClearance", LENGTH, "Tourillons", 1.0),
    ],
}


def value_of(obj: Any, name: str) -> object:
    value = getattr(obj, name)
    return getattr(value, "Value", value)


# --- R1 et T3 : objets, propriétés, volumes ----------------------------------------------


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda s: s.name)
def test_volumes_et_placements(document: Any, scenario: Scenario) -> None:
    montage = build(document, scenario)
    montage.assert_expected()
    assert montage.joint.isValid()
    assert montage.joint.Placement == montage.host.Placement
    assert montage.host.Visibility is False
    assert stale_or_invalid(document) == []


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda s: s.name)
def test_proprietes_par_type(document: Any, scenario: Scenario) -> None:
    joint = build(document, scenario).joint
    rows = PROPERTIES[scenario.factory]
    for name, type_id, group, default in rows:
        assert joint.getTypeIdOfProperty(name) == type_id, name
        assert joint.getGroupOfProperty(name) == group, name
        assert joint.getDocumentationOfProperty(name), name
        assert joint.getEditorMode(name) == [], name
        assert value_of(joint, name) == default, name
    joint_class = type(joint.Proxy)
    assert {spec.name for spec in joint_class.specs()} == COMMON | {row[0] for row in rows}
    assert joint_class.TYPE.startswith("Menuiserie::")


def test_tourillons_forme_de_l_assemblage(document: Any) -> None:
    joint = build(document, DOWELS).joint
    shape = joint.Shape
    assert len(shape.Solids) == 2
    assert shape.Volume == pytest.approx(2 * DOWEL_VOLUME)
    assert all(
        any(face.Surface.TypeId == "Part::GeomCylinder" for face in solid.Faces)
        for solid in shape.Solids
    )
    # Dans le repère de M1 : Ø 10 à x = 20 et 40, de y = 40 à 80.
    local = shape.copy()
    local.Placement = joint.HostPart.Placement.inverse().multiply(local.Placement)
    box = local.BoundBox
    bounds = (box.XMin, box.XMax, box.YMin, box.YMax, box.ZMin, box.ZMax)
    assert bounds == pytest.approx((15, 45, 40, 80, 6, 16))


def test_parametres_saisis_dans_le_document(document: Any) -> None:
    montage = build(document, TONGUE_GROOVE, tongue_thickness=8, through_groove=False)
    assert montage.joint.TongueThickness.Value == 8
    host, guest = montage.volumes()
    assert host == pytest.approx(1000 * 100 * 22 - 1000 * 11 * 8)
    assert guest == pytest.approx(1000 * 100 * 22 + 1000 * 10 * 8)


def test_parametre_refuse_avant_creation(document: Any) -> None:
    count = len(document.Objects)
    with pytest.raises(ValueError, match="count = 51"):
        build(document, DOWELS, count=51)
    assert len(document.Objects) == count + 2  # les deux pièces brutes seules


def test_feuillure_non_filante(document: Any) -> None:
    host = wood(document, "C", (600, 300, 18), (0, 0, 0))
    guest = wood(document, "F", (200, 400, 6), (100, 290, 0))
    document.recompute()
    joint = api.make_rabbet(host, guest)
    assert api.machined_part_of(host).Shape.Volume == pytest.approx(600 * 300 * 18 - 600 * 60)
    joint.Through = False
    document.recompute()
    assert api.machined_part_of(host).Shape.Volume == pytest.approx(600 * 300 * 18 - 200 * 60)


def test_feuillure_refusee_sans_chevauchement(document: Any) -> None:
    montage = build(document, TONGUE_GROOVE)
    joint = api.make_rabbet(montage.host, montage.guest)
    assert not joint.isValid()
    assert "ne se chevauchent pas" in joint.getStatusString()


def test_traverse_de_45_tout_automatique(document: Any) -> None:
    """Contact trop court pour deux tourillons (revue J3c, B1) : un seul, au milieu."""
    stile = wood(document, "M", (600, 60, 22), (0, 0, 0))
    rail = wood(document, "T", (280, 45, 22), (45, 60, 90))
    document.recompute()
    joint = api.make_dowels(stile, rail)
    assert joint.isValid()
    assert len(joint.Shape.Solids) == 1
    assert joint.Shape.BoundBox.Center.x == pytest.approx(22.5)
    volumes = [api.machined_part_of(part).Shape.Volume for part in (stile, rail)]
    assert volumes == pytest.approx(
        [600 * 60 * 22 - DOWEL_HOLE_VOLUME, 280 * 45 * 22 - DOWEL_HOLE_VOLUME]
    )
    assert stale_or_invalid(document) == []


# --- R2 : panneau en rainure-languette dans un montant -----------------------------------


def panel_in_stile(document: Any) -> Montage:
    """Montant M 600 x 60 x 22 ; panneau P 300 x 200 x 10 contre son chant, centré dans
    l'épaisseur, languette de 10 mm d'épaisseur (le panneau entier)."""
    stile = wood(document, "M", (600, 60, 22), (0, 0, 0))
    panel = wood(document, "P", (300, 200, 10), (0, 60, 0))
    panel.Placement.Base.z = 6
    document.recompute()
    joint = api.make_tongue_groove(stile, panel, tongue_thickness=10)
    return Montage(TONGUE_GROOVE, stile, panel, joint)


def test_panneau_en_rainure(document: Any) -> None:
    montage = panel_in_stile(document)
    assert montage.volumes() == pytest.approx(
        (600 * 60 * 22 - 600 * 11 * 10, 300 * 200 * 10 + 300 * 10 * 10)
    )
    groove = api.machined_part_of(montage.host).Shape
    assert groove.isValid()
    assert stale_or_invalid(document) == []


def test_la_rainure_suit_le_panneau(document: Any) -> None:
    montage = panel_in_stile(document)
    montage.joint.ThroughGroove = False
    montage.guest.setExpression("Length", "<<M>>.Length / 2")
    document.recompute()
    assert montage.volumes() == pytest.approx(
        (600 * 60 * 22 - 300 * 11 * 10, 300 * 200 * 10 + 300 * 10 * 10)
    )
    montage.host.Length = 800
    document.recompute()
    assert montage.volumes() == pytest.approx(
        (800 * 60 * 22 - 400 * 11 * 10, 400 * 200 * 10 + 400 * 10 * 10)
    )
    montage.joint.ThroughGroove = True
    document.recompute()
    assert montage.volumes()[0] == pytest.approx(800 * 60 * 22 - 800 * 11 * 10)
    assert stale_or_invalid(document) == []


# --- T4 : le nombre de tourillons suit le contact ----------------------------------------


def dowel_count(joint: Any) -> int:
    return len(joint.Shape.Solids)


def test_le_nombre_de_tourillons_suit(document: Any) -> None:
    montage = build(document, DOWELS, frame=App.Placement())
    rail, joint = montage.guest, montage.joint
    rail.setExpression("Placement.Base.x", "Width")
    rail.setExpression("Width", "<<H>>.Length / 2")
    document.recompute()
    assert rail.Width.Value == 300
    assert dowel_count(joint) == 4
    host, guest = montage.volumes()
    assert host == pytest.approx(600 * 60 * 22 - 4 * DOWEL_HOLE_VOLUME)
    assert guest == pytest.approx(280 * 300 * 22 - 4 * DOWEL_HOLE_VOLUME)
    joint.Count = 3
    document.recompute()
    assert dowel_count(joint) == 3
    montage.host.Length = 500
    document.recompute()
    assert rail.Width.Value == 250
    assert dowel_count(joint) == 3
    assert montage.volumes()[0] == pytest.approx(500 * 60 * 22 - 3 * DOWEL_HOLE_VOLUME)
    assert stale_or_invalid(document) == []


def test_tourillons_impossibles_en_erreur(document: Any) -> None:
    montage = build(document, DOWELS)
    montage.joint.Count = 50
    document.recompute()
    assert not montage.joint.isValid()
    assert "ne tiennent pas" in montage.joint.getStatusString()
    montage.joint.Count = 0
    document.recompute()
    montage.assert_expected()
