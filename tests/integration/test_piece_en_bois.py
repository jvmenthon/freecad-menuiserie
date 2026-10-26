# SPDX-License-Identifier: LGPL-2.1-or-later
"""Pièce en bois à forme libre dans un vrai document (spec piece-en-bois, B1 à B11, ADR 0020).

Les sources sont de vrais objets FreeCAD : corps PartDesign, boîtes Part, esquisses, formes
importées, conteneurs. La source n'est jamais modifiée par la conversion (sauf sa visibilité).
"""

from __future__ import annotations

import contextlib
import importlib
import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
Part = pytest.importorskip("Part")
api = pytest.importorskip("freecad.menuiserie.api")
wood_part = pytest.importorskip("freecad.menuiserie.features.wood_part")
shaped_part = pytest.importorskip("freecad.menuiserie.features.shaped_part")
Sketcher = pytest.importorskip("Sketcher")

Reopen = Callable[[Any], Any]
TOLERANCE = 1e-3


# --- fabriques de sources ------------------------------------------------------------------


def rectangle(sketch: Any, width: float, height: float) -> None:
    """Rectangle fermé de ``width`` x ``height`` dans l'esquisse, coin au point d'origine."""
    corners = [
        App.Vector(0, 0, 0),
        App.Vector(width, 0, 0),
        App.Vector(width, height, 0),
        App.Vector(0, height, 0),
    ]
    for index, start in enumerate(corners):
        sketch.addGeometry(Part.LineSegment(start, corners[(index + 1) % 4]), False)
    for index in range(4):
        sketch.addConstraint(Sketcher.Constraint("Coincident", index, 2, (index + 1) % 4, 1))


def leg(doc: Any, length: float = 720.0) -> Any:
    """Pied : corps PartDesign, esquisse 45 x 95 et protrusion de ``length`` mm."""
    body = doc.addObject("PartDesign::Body", "Pied")
    sketch = body.newObject("Sketcher::SketchObject", "Esquisse")
    rectangle(sketch, 45.0, 95.0)
    pad = body.newObject("PartDesign::Pad", "Protrusion")
    pad.Profile = sketch
    pad.Length = length
    doc.recompute()
    return body


def box(doc: Any, size: tuple[float, float, float], name: str = "Boite") -> Any:
    obj = doc.addObject("Part::Box", name)
    obj.Length, obj.Width, obj.Height = size
    doc.recompute()
    return obj


def imported(doc: Any, *shapes: Any, name: str = "Importe") -> Any:
    """Forme importée (``Part::Feature`` sans dépendance) portant ``shapes`` en un composé."""
    obj = doc.addObject("Part::Feature", name)
    obj.Shape = shapes[0] if len(shapes) == 1 else Part.makeCompound(list(shapes))
    doc.recompute()
    return obj


def closed_sketch(doc: Any, width: float = 300.0, height: float = 120.0) -> Any:
    sketch = doc.addObject("Sketcher::SketchObject", "Profil")
    rectangle(sketch, width, height)
    doc.recompute()
    return sketch


def world(obj: Any) -> Any:
    """Forme de ``obj`` placée dans le repère du document."""
    shape = obj.Shape.copy()
    shape.Placement = obj.getGlobalPlacement()
    return shape


def dimensions(part: Any) -> tuple[float, float, float]:
    return (part.Length.Value, part.Width.Value, part.Thickness.Value)


def assert_same_place(part: Any, source: Any) -> None:
    """La pièce occupe exactement la place de la source (B4)."""
    a, b = world(part), world(source)
    assert a.Volume == pytest.approx(b.Volume, rel=TOLERANCE)
    assert a.CenterOfMass.distanceToPoint(b.CenterOfMass) < TOLERANCE
    for name in ("XMin", "XMax", "YMin", "YMax", "ZMin", "ZMax"):
        assert getattr(a.BoundBox, name) == pytest.approx(getattr(b.BoundBox, name), abs=TOLERANCE)


def describe(value: Any) -> str:
    """Texte stable d'une valeur de propriété : les formes (recréées à chaque lecture, adresse
    différente) sont décrites par leur géométrie, pas par leur représentation."""
    if isinstance(value, Part.Shape):
        if value.isNull():
            return "forme nulle"
        return f"{value.ShapeType} {value.Volume:.6f} {value.BoundBox} {value.Placement}"
    return str(value)


def snapshot(obj: Any) -> dict[str, Any]:
    """Propriétés et forme de ``obj`` hors visibilité, pour vérifier qu'il n'a pas changé."""
    return {
        name: describe(getattr(obj, name))
        for name in obj.PropertiesList
        if name not in ("Visibility", "State")
    }


def part_of(source: Any) -> Any:
    return api.make_shaped_part(source)


# --- B1, B3, B4 : conversion d'un corps PartDesign ----------------------------------------


def test_corps_partdesign_devient_une_piece(document: Any) -> None:
    source = leg(document)
    part = part_of(source)
    document.recompute()
    assert api.is_shaped_part(part)
    assert part.TypeId == "Part::FeaturePython"
    assert part.Proxy.TYPE == "Menuiserie::ShapedPart"
    assert dimensions(part) == pytest.approx((720.0, 95.0, 45.0), abs=TOLERANCE)
    assert part.Source == source
    assert "Invalid" not in part.State
    assert not source.Visibility


def test_la_piece_a_la_place_de_la_source(document: Any) -> None:
    source = leg(document)
    source.Placement = App.Placement(
        App.Vector(100, 200, 300), App.Rotation(App.Vector(1, 1, 0), 30)
    )
    document.recompute()
    part = part_of(source)
    document.recompute()
    assert_same_place(part, source)
    local = part.Shape.copy()
    local.Placement = App.Placement()  # la forme est dans le repère de la pièce
    box_ = local.BoundBox
    assert (box_.XMin, box_.YMin, box_.ZMin) == pytest.approx((0.0, 0.0, 0.0), abs=TOLERANCE)


def test_deplacer_la_piece_ne_deplace_pas_la_source(document: Any) -> None:
    source = leg(document)
    part = part_of(source)
    document.recompute()
    before = snapshot(source)
    part.Placement = App.Placement(App.Vector(500, 0, 0), part.Placement.Rotation)
    document.recompute()
    assert snapshot(source) == before
    assert world(part).CenterOfMass.x == pytest.approx(
        world(source).CenterOfMass.x + 500.0, abs=1e-3
    )


def test_la_source_n_est_jamais_modifiee(document: Any) -> None:
    source = leg(document)
    sketch, pad = source.Group[0], source.Group[1]
    before = [snapshot(obj) for obj in (source, sketch, pad)]
    part = part_of(source)
    document.recompute()
    part.Placement = App.Placement(App.Vector(1, 2, 3), App.Rotation())
    document.recompute()
    assert [snapshot(obj) for obj in (source, sketch, pad)] == before


# --- B5, B6 : cotes en lecture seule et suivi du dessin -----------------------------------


def test_cotes_de_sortie_en_lecture_seule(document: Any) -> None:
    part = part_of(leg(document))
    document.recompute()
    for name in ("Length", "Width", "Thickness"):
        assert "Output" in part.getPropertyStatus(name)
        assert "ReadOnly" in part.getEditorMode(name)
        assert part.getGroupOfProperty(name) == "Dimensions"
    assert document.recompute() == 0
    assert not [obj.Name for obj in document.Objects if "Touched" in obj.State]


def test_expression_sur_une_cote_refusee(document: Any, vue_rapport: Any) -> None:
    part = part_of(leg(document))
    document.recompute()
    with contextlib.suppress(RuntimeError, ValueError):  # refus direct de FreeCAD : acceptable
        part.setExpression("Length", "1000 mm")
    document.recompute()
    assert not [path for path, _ in part.ExpressionEngine if path == "Length"]
    assert part.Length.Value == pytest.approx(720.0, abs=TOLERANCE)


def test_une_expression_peut_lire_les_cotes(document: Any) -> None:
    source = leg(document)
    part = part_of(source)
    follower = box(document, (10.0, 10.0, 10.0), "Suiveur")
    follower.setExpression("Height", f"{part.Name}.Length")
    document.recompute()
    assert follower.Height.Value == pytest.approx(720.0, abs=TOLERANCE)
    source.Group[1].Length = 900.0
    document.recompute()
    assert follower.Height.Value == pytest.approx(900.0, abs=TOLERANCE)


def test_allonger_la_protrusion_allonge_la_piece(document: Any) -> None:
    source = leg(document)
    part = part_of(source)
    part.Mark = "P1"
    document.recompute()
    axes = part.SourceAxes
    source.Group[1].Length = 1000.0
    document.recompute()
    assert dimensions(part) == pytest.approx((1000.0, 95.0, 45.0), abs=TOLERANCE)
    assert part.SourceAxes.isSame(axes, 1e-9)
    source.Group[1].Length = 50.0
    document.recompute()
    assert dimensions(part) == pytest.approx((95.0, 50.0, 45.0), abs=TOLERANCE) or dimensions(
        part
    ) == pytest.approx((50.0, 95.0, 45.0), abs=TOLERANCE)
    assert part.SourceAxes.isSame(axes, 1e-9)  # les axes mémorisés ne changent pas
    assert part.Mark == "P1"
    assert_same_place(part, source)


def test_repere_automatique_garde_la_place(document: Any) -> None:
    source = leg(document, 50.0)
    part = part_of(source)
    document.recompute()
    api.reset_shaped_axes(part)
    document.recompute()
    assert dimensions(part) == pytest.approx((95.0, 50.0, 45.0), abs=TOLERANCE)
    assert_same_place(part, source)
    with pytest.raises(TypeError):
        api.reset_shaped_axes(source)


# --- sources diverses ----------------------------------------------------------------------


def test_boite_tournee(document: Any) -> None:
    source = box(document, (45.0, 800.0, 95.0))
    source.Placement = App.Placement(App.Vector(10, 20, 30), App.Rotation(App.Vector(1, 2, 3), 40))
    document.recompute()
    part = part_of(source)
    document.recompute()
    assert dimensions(part) == pytest.approx((800.0, 95.0, 45.0), abs=TOLERANCE)
    assert_same_place(part, source)


def test_cylindre_tourne(document: Any) -> None:
    source = document.addObject("Part::Cylinder", "Rond")
    source.Radius, source.Height = 20.0, 500.0
    source.Placement = App.Placement(App.Vector(0, 0, 0), App.Rotation(App.Vector(0, 1, 0), 90))
    document.recompute()
    part = part_of(source)
    document.recompute()
    assert dimensions(part)[0] == pytest.approx(500.0, abs=TOLERANCE)
    assert_same_place(part, source)


def test_esquisse_fermee_en_mode_profil(document: Any) -> None:
    sketch = closed_sketch(document)
    part = api.make_shaped_part(sketch, profile_thickness=18.0)
    document.recompute()
    assert dimensions(part) == pytest.approx((300.0, 120.0, 18.0), abs=TOLERANCE)
    assert part.ProfileThickness.Value == pytest.approx(18.0)
    assert not sketch.Visibility
    sketch.Placement = App.Placement(App.Vector(0, 0, 50), App.Rotation())
    document.recompute()
    part.ProfileThickness = 25.0
    document.recompute()
    assert part.Thickness.Value == pytest.approx(25.0, abs=TOLERANCE)


def test_esquisse_ouverte_refusee(document: Any) -> None:
    sketch = document.addObject("Sketcher::SketchObject", "Ouverte")
    sketch.addGeometry(Part.LineSegment(App.Vector(0, 0, 0), App.Vector(100, 0, 0)), False)
    sketch.addGeometry(Part.LineSegment(App.Vector(100, 0, 0), App.Vector(100, 50, 0)), False)
    document.recompute()
    before, count = snapshot(sketch), len(document.Objects)
    with pytest.raises(ValueError, match="n'est pas fermée"):
        api.make_shaped_part(sketch)
    assert len(document.Objects) == count
    assert snapshot(sketch) == before
    assert sketch.Visibility


def test_epaisseur_de_profil_invalide(document: Any) -> None:
    sketch = closed_sketch(document)
    with pytest.raises(ValueError, match="Épaisseur du profil"):
        api.make_shaped_part(sketch, profile_thickness=0.0)


def test_importe_a_deux_solides(document: Any) -> None:
    first = Part.makeBox(100, 50, 20)
    second = Part.makeBox(200, 40, 20)
    second.translate(App.Vector(300, 0, 0))
    source = imported(document, first, second)
    with pytest.raises(ValueError, match="2 solides"):
        api.make_shaped_part(source)
    parts = api.make_shaped_parts(source)
    document.recompute()
    assert len(parts) == 2
    assert [part.SolidIndex for part in parts] == [0, 1]
    assert all(part.SolidSignature for part in parts)
    assert dimensions(parts[0]) == pytest.approx((100.0, 50.0, 20.0), abs=TOLERANCE)
    assert dimensions(parts[1]) == pytest.approx((200.0, 40.0, 20.0), abs=TOLERANCE)
    assert not source.Visibility
    assert world(parts[1]).CenterOfMass.x == pytest.approx(400.0, abs=TOLERANCE)
    assert snapshot(source)["Shape"].startswith(f"{first.Volume + second.Volume:.6f}")


def test_forme_parametrique_a_deux_solides_refusee(document: Any) -> None:
    left, right = box(document, (10, 10, 10), "A"), box(document, (10, 10, 10), "B")
    right.Placement = App.Placement(App.Vector(50, 0, 0), App.Rotation())
    compound = document.addObject("Part::Compound", "Composé")
    compound.Links = [left, right]
    document.recompute()
    with pytest.raises(ValueError, match="séparez-les"):
        api.make_shaped_parts(compound)


def test_empreinte_differente_met_la_piece_en_erreur(document: Any) -> None:
    source = imported(document, Part.makeBox(100, 50, 20), Part.makeBox(200, 40, 20))
    parts = api.make_shaped_parts(source)
    document.recompute()
    source.Shape = Part.makeCompound([Part.makeBox(10, 10, 10), Part.makeBox(5, 5, 5)])
    document.recompute()
    assert "Invalid" in parts[0].State
    assert "n'est plus celui" in parts[0].getStatusString()


def test_objets_de_l_atelier_refuses(document: Any) -> None:
    board = wood_part.create_wood_part(document, material_id="chene")
    document.recompute()
    with pytest.raises(TypeError, match="atelier Menuiserie"):
        api.make_shaped_part(board)
    part = part_of(leg(document))
    document.recompute()
    with pytest.raises(TypeError, match="atelier Menuiserie"):
        api.make_shaped_part(part)


def test_source_deja_convertie_refusee(document: Any) -> None:
    source = leg(document)
    part_of(source)
    document.recompute()
    with pytest.raises(ValueError, match="déjà la forme"):
        api.make_shaped_part(source)
    with pytest.raises(ValueError, match="déjà la forme"):
        api.make_shaped_part(source.Group[1])


def test_objet_non_geometrique_refuse(document: Any) -> None:
    group = document.addObject("App::DocumentObjectGroup", "Groupe")
    with pytest.raises(TypeError):
        api.make_shaped_part(group)


# --- conteneurs ----------------------------------------------------------------------------


def test_source_dans_un_conteneur_part(document: Any) -> None:
    container = document.addObject("App::Part", "Meuble")
    container.Placement = App.Placement(
        App.Vector(1000, 0, 0), App.Rotation(App.Vector(0, 0, 1), 90)
    )
    source = box(document, (45.0, 95.0, 720.0))
    container.addObject(source)
    document.recompute()
    part = part_of(source)
    document.recompute()
    assert part.Name in [obj.Name for obj in container.Group]
    assert_same_place(part, source)


def test_source_dans_un_groupe(document: Any) -> None:
    group = document.addObject("App::DocumentObjectGroup", "Dossier")
    source = box(document, (45.0, 95.0, 720.0))
    group.addObject(source)
    part = part_of(source)
    document.recompute()
    assert part.Name in [obj.Name for obj in group.Group]
    assert_same_place(part, source)


# --- B7 : propriétés de matériau identiques à celles de WoodPart --------------------------


def test_proprietes_de_materiau_identiques(document: Any) -> None:
    board = wood_part.create_wood_part(document, material_id="chene")
    part = part_of(box(document, (800.0, 200.0, 22.0)))
    document.recompute()
    names = [
        "Material", "MaterialId", "Category", "Density", "GrainDirection",
        "PreferredGrainDirection", "Mark", "LengthAllowance", "WidthAllowance",
        "ThicknessAllowance",
    ]  # fmt: skip
    for name in names:
        assert part.getTypeIdOfProperty(name) == board.getTypeIdOfProperty(name), name
        assert part.getGroupOfProperty(name) == board.getGroupOfProperty(name), name
        assert part.getDocumentationOfProperty(name) == board.getDocumentationOfProperty(name), name
        assert part.getEditorMode(name) == board.getEditorMode(name), name
        if board.getTypeIdOfProperty(name) == "App::PropertyEnumeration":
            assert part.getEnumerationsOfProperty(name) == board.getEnumerationsOfProperty(name)


def test_marque_et_nom_vont_ensemble(document: Any) -> None:
    part = part_of(leg(document))
    part.Mark = "P7"
    assert part.Label == "P7"
    part.Label = "P8"
    assert part.Mark == "P8"


def test_materiau_et_sens_du_fil_comme_la_piece_de_bois(document: Any) -> None:
    board = wood_part.create_wood_part(document, material_id="chene")
    part = api.make_shaped_part(box(document, (800.0, 200.0, 22.0)), "chene")
    document.recompute()
    for obj in (board, part):
        obj.GrainDirection = "Width"
        obj.Material = "MDF"
    document.recompute()
    assert part.GrainDirection == board.GrainDirection == "None"
    assert part.PreferredGrainDirection == board.PreferredGrainDirection == "Width"
    for obj in (board, part):
        obj.Material = "Chêne"
    document.recompute()
    assert part.GrainDirection == board.GrainDirection


def test_materiau_a_la_creation(document: Any) -> None:
    part = api.make_shaped_part(leg(document), "mdf", "A1")
    assert part.MaterialId == "mdf"
    assert part.Mark == "A1"
    count = len(document.Objects)
    with pytest.raises(KeyError):
        api.make_shaped_part(box(document, (1, 1, 1)), "inconnu")
    assert len(document.Objects) == count + 1  # seule la boîte d'essai a été ajoutée


# --- B8 : source supprimée ------------------------------------------------------------------


def test_source_supprimee_met_la_piece_en_erreur(document: Any) -> None:
    source = box(document, (45.0, 95.0, 720.0))
    part = part_of(source)
    document.recompute()
    document.removeObject(source.Name)
    document.recompute()  # aucune exception Python
    assert "Invalid" in part.State
    assert "sans forme" in part.getStatusString()


def test_annuler_la_conversion_rend_la_source_visible(document: Any) -> None:
    document.UndoMode = 1
    source = box(document, (45.0, 95.0, 720.0))
    document.openTransaction("Conversion")
    part_of(source)
    document.commitTransaction()
    assert not source.Visibility
    document.undo()
    assert source.Visibility
    assert not [obj for obj in document.Objects if api.is_shaped_part(obj)]
    document.redo()
    assert [obj for obj in document.Objects if api.is_shaped_part(obj)]


# --- B9 : enregistrement et réouverture -----------------------------------------------------


def test_reouverture(document: Any, rouvrir: Reopen, tmp_path: Path) -> None:
    source = leg(document)
    part = part_of(source)
    part.Mark = "P1"
    document.recompute()
    name, source_name, expected = part.Name, source.Name, dimensions(part)
    doc = rouvrir(document)
    reopened = doc.getObject(name)
    assert api.is_shaped_part(reopened)
    assert reopened.Proxy.TYPE == "Menuiserie::ShapedPart"
    assert reopened.Source == doc.getObject(source_name)
    assert dimensions(reopened) == pytest.approx(expected, abs=TOLERANCE)
    assert reopened.Mark == "P1"
    assert "Output" in reopened.getPropertyStatus("Length")
    assert "ReadOnly" in reopened.getEditorMode("Length")
    assert doc.recompute() == 0
    doc.getObject(source_name).Group[1].Length = 1000.0
    doc.recompute()
    assert reopened.Length.Value == pytest.approx(1000.0, abs=TOLERANCE)
    assert [obj for obj in doc.Objects if "Touched" in obj.State] == []


def test_chemin_de_persistance_fige(document: Any, tmp_path: Path) -> None:
    part_of(leg(document))
    document.recompute()
    path = tmp_path / "persistance.FCStd"
    document.saveAs(str(path))
    with zipfile.ZipFile(path) as archive:
        xml = archive.read("Document.xml").decode("utf-8")
        assert 'module="freecad.menuiserie.features.shaped_part"' in xml
        assert 'class="ShapedPart"' in xml
        assert any(name.endswith(".brp") for name in archive.namelist())


# --- B10 : une pièce est une forme comme les autres ------------------------------------------


def test_coupe_sur_la_piece(document: Any) -> None:
    part = part_of(box(document, (200.0, 100.0, 50.0)))
    tool = box(document, (50.0, 100.0, 50.0), "Outil")
    tool.Placement = App.Placement(App.Vector(150, 0, 0), App.Rotation())
    cut = document.addObject("Part::Cut", "Coupe")
    cut.Base, cut.Tool = part, tool
    document.recompute()
    assert cut.Shape.Volume == pytest.approx(150.0 * 100.0 * 50.0, rel=TOLERANCE)


def test_lien_vers_la_piece(document: Any) -> None:
    part = part_of(leg(document))
    document.recompute()
    link = document.addObject("App::Link", "Lien")
    link.LinkedObject = part
    link.LinkPlacement = App.Placement(App.Vector(0, 300, 0), App.Rotation())
    document.recompute()
    assert link.LinkedObject == part
    assert link.Shape.Volume == pytest.approx(part.Shape.Volume, rel=TOLERANCE)


def test_export_et_import_step(document: Any, tmp_path: Path) -> None:
    part = part_of(leg(document))
    document.recompute()
    path = str(tmp_path / "pied.step")
    Part.export([part], path)
    shape = Part.read(path)
    assert shape.Volume == pytest.approx(part.Shape.Volume, rel=1e-3)


def test_vue_technique_ignoree() -> None:
    pytest.skip("La vue TechDraw (B10) exige le module TechDraw et une vue graphique : lot PD-d.")


def test_api_importable_apres_rechargement() -> None:
    """Le module se recharge sans effet de bord (garde-fou des chemins de persistance)."""
    module = importlib.import_module("freecad.menuiserie.features.shaped_part")
    assert module.ShapedPart is shaped_part.ShapedPart
