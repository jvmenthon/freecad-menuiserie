# SPDX-License-Identifier: LGPL-2.1-or-later
"""Pièces usinées et tenons-mortaises dans le document (J3b, critères O1 à O7)."""

from __future__ import annotations

from typing import Any

import pytest

from tests.integration.cadre import (
    NOT_TOUCHING,
    PAIRS,
    RAIL_VOLUME,
    STILE_VOLUME,
    Cadre,
    assert_follow_blanks,
    build_frame,
    touched,
)

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
api = pytest.importorskip("freecad.menuiserie.api")
base = pytest.importorskip("freecad.menuiserie.features.joints.base")
joints = pytest.importorskip("freecad.menuiserie.features.joints.factories")
machined_part = pytest.importorskip("freecad.menuiserie.features.machined_part")
mortise_tenon = pytest.importorskip("freecad.menuiserie.features.joints.mortise_tenon")
wood_part = pytest.importorskip("freecad.menuiserie.features.wood_part")

LENGTH = "App::PropertyLength"
DISTANCE = "App::PropertyDistance"


def assert_frame_volumes(cadre: Cadre) -> None:
    """Volumes de O1 pour les quatre pièces usinées."""
    for mark in ("M1", "M2"):
        assert cadre.volume(mark) == pytest.approx(STILE_VOLUME)
    for mark in ("T1", "T2"):
        assert cadre.volume(mark) == pytest.approx(RAIL_VOLUME)


# --- O1 : cadre de référence -------------------------------------------------------------


def test_cadre_en_un_seul_recalcul(cadre: Cadre) -> None:
    doc = cadre.doc
    for host, guest in PAIRS:
        joints.create_mortise_tenon(doc, cadre.parts[host], cadre.parts[guest])
    doc.recompute()
    machined = [obj for obj in doc.Objects if machined_part.is_machined_part(obj)]
    assert len(machined) == 4
    assert len([obj for obj in doc.Objects if base.is_joint(obj)]) == 4
    for obj in machined:
        assert obj.isValid()
        assert len(obj.Shape.Solids) == 1
        assert obj.Shape.isValid()
        assert obj.Placement == obj.Base.Placement
        assert obj.Base.Visibility is False
    assert_frame_volumes(cadre)
    assert touched(doc) == []


def test_forme_des_assemblages_vide(cadre_assemble: Cadre) -> None:
    for joint in cadre_assemble.joints.values():
        assert joint.isValid()
        assert joint.Shape.isNull()
        assert joint.Placement == joint.HostPart.Placement


# --- O2 : propriétés ---------------------------------------------------------------------

MACHINED_PROPERTIES = [
    ("Base", "App::PropertyLink", "Pièce", ["ReadOnly"]),
    ("Joints", "App::PropertyLinkList", "Pièce", ["ReadOnly"]),
    ("Version", "App::PropertyInteger", "Base", ["Hidden"]),
]
JOINT_PROPERTIES = [
    ("HostPart", "App::PropertyLink", "Assemblage", [], None),
    ("GuestPart", "App::PropertyLink", "Assemblage", [], None),
    ("Version", "App::PropertyInteger", "Base", ["Hidden"], 1),
    ("TenonThickness", LENGTH, "Tenon", [], 0.0),
    ("TenonWidth", LENGTH, "Tenon", [], 0.0),
    ("TenonLength", LENGTH, "Tenon", [], 0.0),
    ("WidthOffset", DISTANCE, "Tenon", [], 0.0),
    ("ThicknessOffset", DISTANCE, "Tenon", [], 0.0),
    ("Through", "App::PropertyBool", "Tenon", [], False),
    ("MortiseClearance", LENGTH, "Mortaise", [], 2.0),
]


def value_of(obj: Any, name: str) -> object:
    value = getattr(obj, name)
    return getattr(value, "Value", value)


@pytest.mark.parametrize(("name", "type_id", "group", "mode"), MACHINED_PROPERTIES)
def test_proprietes_de_la_piece_usinee(
    cadre_assemble: Cadre, name: str, type_id: str, group: str, mode: list[str]
) -> None:
    obj = cadre_assemble.machined("M1")
    assert obj.getTypeIdOfProperty(name) == type_id
    assert obj.getGroupOfProperty(name) == group
    assert obj.getDocumentationOfProperty(name)
    assert obj.getEditorMode(name) == mode
    assert obj.Version == 1


@pytest.mark.parametrize(("name", "type_id", "group", "mode", "default"), JOINT_PROPERTIES)
def test_proprietes_du_tenon_mortaise(
    cadre_assemble: Cadre, name: str, type_id: str, group: str, mode: list[str], default: object
) -> None:
    obj = cadre_assemble.joints["M1", "T1"]
    assert obj.getTypeIdOfProperty(name) == type_id
    assert obj.getGroupOfProperty(name) == group
    assert obj.getDocumentationOfProperty(name)
    assert obj.getEditorMode(name) == mode
    if default is not None:
        assert value_of(obj, name) == default


def test_chaque_parametre_a_sa_propriete(cadre_assemble: Cadre) -> None:
    obj = cadre_assemble.joints["M1", "T1"]
    names = {spec.name for spec in mortise_tenon.MortiseTenonJoint.specs()}
    assert names == {row[0] for row in JOINT_PROPERTIES}
    assert set(obj.PropertiesList) >= names


def test_piece_de_bois_inchangee(cadre_assemble: Cadre) -> None:
    blank = cadre_assemble.parts["M1"]
    reference = api.make_wood_part(doc=cadre_assemble.doc)
    assert blank.Version == 2
    assert sorted(blank.PropertiesList) == sorted(reference.PropertiesList)


# --- O3 : graphe -------------------------------------------------------------------------


def names(objects: list[Any]) -> set[str]:
    return {obj.Name for obj in objects}


def test_graphe_des_dependances(cadre_assemble: Cadre) -> None:
    for (host, guest), joint in cadre_assemble.joints.items():
        assert names(joint.OutList) == names(
            [cadre_assemble.parts[host], cadre_assemble.parts[guest]]
        )
    for mark, blank in cadre_assemble.parts.items():
        machined = cadre_assemble.machined(mark)
        expected = [blank, *(j for pair, j in cadre_assemble.joints.items() if mark in pair)]
        assert names(machined.OutList) == names(expected)
        assert names(machined.Joints) == names(expected[1:])
    for obj in cadre_assemble.doc.Objects:
        assert obj.Name not in names(obj.OutListRecursive)
    assert touched(cadre_assemble.doc) == []


def test_ordre_inverse_memes_volumes(document: Any) -> None:
    cadre = build_frame(document)
    cadre.assemble(tuple(reversed(PAIRS)))
    assert_frame_volumes(cadre)


# --- O4 : le cadre suit (variante pilotée) -----------------------------------------------


def drive(cadre: Cadre) -> None:
    """Expressions natives de la variante pilotée du § 3."""
    m1, m2, t1, t2 = (cadre.parts[mark] for mark in ("M1", "M2", "T1", "T2"))
    m2.setExpression("Placement.Base.y", "400 mm - Width")
    m2.setExpression("Width", f"{m1.Name}.Width")
    for rail in (t1, t2):
        rail.setExpression("Placement.Base.y", f"{m1.Name}.Width")
        rail.setExpression("Length", f"400 mm - 2 * {m1.Name}.Width")
    t1.setExpression("Placement.Base.x", "Width")
    t2.setExpression("Width", f"{t1.Name}.Width")
    cadre.doc.recompute()


def test_le_cadre_suit_les_cotes(cadre_assemble: Cadre) -> None:
    drive(cadre_assemble)
    assert_frame_volumes(cadre_assemble)
    cadre_assemble.parts["M1"].Width = 80
    cadre_assemble.doc.recompute()
    assert touched(cadre_assemble.doc) == []
    assert cadre_assemble.parts["T1"].Placement.Base.y == pytest.approx(80)
    assert_follow_blanks(cadre_assemble)
    assert cadre_assemble.parts["T1"].Length.Value == pytest.approx(240)
    for mark in ("T1", "T2"):
        assert cadre_assemble.volume(mark) == pytest.approx(240 * 60 * 22 + 2 * 53 * 40 * 7)
    for mark in ("M1", "M2"):
        assert cadre_assemble.volume(mark) == pytest.approx(600 * 80 * 22 - 2 * 55 * 40 * 7)
    cadre_assemble.parts["T1"].Width = 80
    cadre_assemble.doc.recompute()
    assert touched(cadre_assemble.doc) == []
    assert cadre_assemble.volume("T1") == pytest.approx(240 * 80 * 22 + 2 * 53 * 54 * 7)
    assert cadre_assemble.parts["T1"].Placement.Base.x == pytest.approx(80)
    assert_follow_blanks(cadre_assemble)


# --- O5 : paramètres de l'assemblage -----------------------------------------------------


def test_epaisseur_saisie_puis_automatique(cadre_assemble: Cadre) -> None:
    doc = cadre_assemble.doc
    for joint in cadre_assemble.joints.values():
        joint.TenonThickness = 8
    doc.recompute()
    assert cadre_assemble.volume("T1") == pytest.approx(280 * 60 * 22 + 2 * 40 * 40 * 8)
    assert cadre_assemble.volume("M1") == pytest.approx(600 * 60 * 22 - 2 * 42 * 40 * 8)
    for joint in cadre_assemble.joints.values():
        joint.TenonThickness = 0
    doc.recompute()
    assert_frame_volumes(cadre_assemble)


def test_tenon_traversant(cadre_assemble: Cadre) -> None:
    cadre_assemble.joints["M1", "T1"].Through = True
    cadre_assemble.doc.recompute()
    assert cadre_assemble.volume("T1") == pytest.approx(280 * 60 * 22 + 40 * 40 * 7 + 60 * 40 * 7)
    assert cadre_assemble.volume("M1") == pytest.approx(600 * 60 * 22 - 42 * 40 * 7 - 60 * 40 * 7)
    cadre_assemble.joints["M1", "T1"].Through = False
    cadre_assemble.doc.recompute()
    assert_frame_volumes(cadre_assemble)


def test_expression_sur_l_epaisseur(cadre_assemble: Cadre) -> None:
    joint = cadre_assemble.joints["M1", "T1"]
    joint.setExpression("TenonThickness", "<<T1>>.Thickness / 2")
    cadre_assemble.doc.recompute()
    assert joint.TenonThickness.Value == pytest.approx(11)
    assert cadre_assemble.volume("T1") == pytest.approx(280 * 60 * 22 + 40 * 40 * 11 + 40 * 40 * 7)
    assert touched(cadre_assemble.doc) == []


# --- O6 : erreurs ------------------------------------------------------------------------


def test_pieces_ecartees_puis_remises(cadre_assemble: Cadre) -> None:
    doc, rail = cadre_assemble.doc, cadre_assemble.parts["T1"]
    # Épaisseur de 22 mm : la traverse posée à z = 27 est 5 mm au-dessus des montants.
    rail.Placement.Base.z = 27
    rail.Placement = rail.Placement
    doc.recompute()
    joint = cadre_assemble.joints["M1", "T1"]
    assert "Invalid" in joint.State
    assert NOT_TOUCHING in joint.getStatusString()
    machined = cadre_assemble.machined("T1")
    assert "Invalid" in machined.State or "Touched" in machined.State
    assert machined.Shape.Volume == pytest.approx(RAIL_VOLUME)  # jamais de forme partielle
    rail.Placement.Base.z = 0
    rail.Placement = rail.Placement
    doc.recompute()
    assert touched(doc) == []
    assert_frame_volumes(cadre_assemble)
    assert_follow_blanks(cadre_assemble)


def count_and_raise(doc: Any, error: type[Exception], host: Any, guest: Any) -> None:
    before = len(doc.Objects)
    with pytest.raises(error) as raised:
        api.make_mortise_tenon(host, guest)
    assert str(raised.value)
    assert len(doc.Objects) == before


def test_refus_avant_creation(cadre: Cadre) -> None:
    doc, m1, t1 = cadre.doc, cadre.parts["M1"], cadre.parts["T1"]
    box = doc.addObject("Part::Box", "Boite")
    count_and_raise(doc, TypeError, box, t1)
    count_and_raise(doc, TypeError, m1, box)
    count_and_raise(doc, ValueError, m1, m1)
    with pytest.raises(ValueError, match="tenon_thickness"):
        api.make_mortise_tenon(m1, t1, tenon_thickness=-1)
    with pytest.raises(TypeError):
        api.make_mortise_tenon(m1, t1, inconnu=1)
    assert machined_part.machined_part_of(m1) is None


def test_refus_pieces_d_une_piece_usinee_et_de_sa_brute(cadre_assemble: Cadre) -> None:
    m1 = cadre_assemble.parts["M1"]
    count_and_raise(cadre_assemble.doc, ValueError, cadre_assemble.machined("M1"), m1)


def test_refus_documents_differents(cadre: Cadre) -> None:
    other = App.newDocument(f"{cadre.doc.Name}Autre")
    foreign = api.make_wood_part(doc=other)
    count_and_raise(cadre.doc, ValueError, cadre.parts["M1"], foreign)
    assert len(other.Objects) == 1


def test_refus_conteneurs_differents(cadre: Cadre) -> None:
    container = cadre.doc.addObject("App::Part", "Conteneur")
    container.addObject(cadre.parts["T1"])
    count_and_raise(cadre.doc, ValueError, cadre.parts["M1"], cadre.parts["T1"])


def test_meme_conteneur_accepte(cadre: Cadre) -> None:
    container = cadre.doc.addObject("App::Part", "Conteneur")
    container.addObjects([cadre.parts["M1"], cadre.parts["T1"]])
    joint = api.make_mortise_tenon(cadre.parts["M1"], cadre.parts["T1"])
    assert joint.getParentGeoFeatureGroup() == container
    assert cadre.machined("T1").getParentGeoFeatureGroup() == container
    assert cadre.volume("T1") == pytest.approx(280 * 60 * 22 + 40 * 40 * 7)


# --- O7 : pièce usinée à la place de sa brute ---------------------------------------------


def test_piece_usinee_acceptee_et_reutilisee(cadre: Cadre) -> None:
    m1, t1, t2 = (cadre.parts[mark] for mark in ("M1", "T1", "T2"))
    first = api.make_mortise_tenon(m1, t1)
    machined = api.machined_part_of(m1)
    second = api.make_mortise_tenon(machined, t2)
    assert second.HostPart == m1
    assert api.machined_part_of(m1) == machined
    assert names(machined.Joints) == {first.Name, second.Name}
    assert len([o for o in cadre.doc.Objects if api.is_machined_part(o)]) == 3
    assert api.blank_of(machined) == m1
    assert api.blank_of(m1) == m1
    with pytest.raises(TypeError):
        api.blank_of(first)


# --- La pièce usinée suit sa brute (correction de revue B1) et son libellé ----------------


def test_deplacer_la_brute_deplace_la_piece_usinee(cadre_assemble: Cadre) -> None:
    doc = cadre_assemble.doc
    for blank in cadre_assemble.parts.values():
        moved = blank.Placement
        moved.Base.x -= 50
        blank.Placement = moved
    doc.recompute()
    assert touched(doc) == []
    assert_follow_blanks(cadre_assemble)
    assert cadre_assemble.machined("M1").Placement.Base.x == pytest.approx(-50)
    assert_frame_volumes(cadre_assemble)


def test_expression_sur_le_placement_de_la_brute(cadre_assemble: Cadre) -> None:
    doc, m1 = cadre_assemble.doc, cadre_assemble.parts["M1"]
    for blank in cadre_assemble.parts.values():
        if blank != m1:
            blank.setExpression("Placement.Base.z", f"{m1.Name}.Placement.Base.z")
    m1.Placement.Base.z = 100
    m1.Placement = m1.Placement
    doc.recompute()
    assert touched(doc) == []
    assert cadre_assemble.machined("T2").Placement.Base.z == pytest.approx(100)
    assert_follow_blanks(cadre_assemble)
    assert_frame_volumes(cadre_assemble)


def test_libelle_de_la_piece_usinee(cadre_assemble: Cadre) -> None:
    for mark, blank in cadre_assemble.parts.items():
        assert blank.Label == mark
        assert cadre_assemble.machined(mark).Label == f"{mark} (usinée)"
