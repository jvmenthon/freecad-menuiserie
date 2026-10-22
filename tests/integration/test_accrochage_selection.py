# SPDX-License-Identifier: LGPL-2.1-or-later
"""Accrochage à la sélection (J6d, critères T1 à T5) côté document, dans ``freecadcmd``.

La commande lit la sélection de l'interface (``gui/selection.py``) ; ces tests construisent
directement les éléments sélectionnés (:class:`PickedElement`), comme le fait la commande, puis
rejouent la suite d'appels du panneau : ``read_targets``, ``new_session``, ``snap_part``.
"""

from __future__ import annotations

from typing import Any

import pytest

from freecad.menuiserie.core.geometry import CONTACT_TOLERANCE_MM, Vec3
from freecad.menuiserie.core.snap import Turn
from tests.integration.bureau import Bureau

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
Part = pytest.importorskip("Part")
api = pytest.importorskip("freecad.menuiserie.api")
picked = pytest.importorskip("freecad.menuiserie.features.picked")
placement_module = pytest.importorskip("freecad.menuiserie.features.placement")
geometry = pytest.importorskip("freecad.menuiserie.features.snap_geometry")
targets = pytest.importorskip("freecad.menuiserie.features.snap_targets")

PickedElement = picked.PickedElement
ABOVE = Vec3(0, 0, 1)
OVERLAP_MM3 = 1.0
Normal = tuple[float, float, float]


# --- Aides -------------------------------------------------------------------------------------


def find_face(obj: Any, normal: Normal, coordinate: float | None = None) -> str:
    """``FaceN`` plane de ``obj`` dont la normale sortante est ``normal`` et dont le centre a pour
    produit scalaire ``coordinate`` avec elle (position du plan le long de la normale)."""
    shape = geometry.global_shape(obj)
    wanted = App.Vector(*normal)
    for index, face in enumerate(shape.Faces, start=1):
        if not isinstance(face.Surface, Part.Plane):
            continue
        u, v = face.Surface.parameter(face.CenterOfMass)
        if face.normalAt(u, v).getAngle(wanted) > 1e-6:
            continue
        if coordinate is None or abs(face.CenterOfMass.dot(wanted) - coordinate) < 1e-6:
            return f"Face{index}"
    raise AssertionError(f"aucune face de normale {normal} sur {obj.Label}")


def pick(root: Any, subname: str, point: Vec3 | None = None) -> Any:
    return PickedElement(root, subname, point)


def box(doc: Any, size: tuple[float, float, float], at: tuple[float, float, float]) -> Any:
    obj = doc.addObject("Part::Box", "Bloc")
    obj.Length, obj.Width, obj.Height = size
    obj.Placement = App.Placement(App.Vector(*at), App.Rotation())
    doc.recompute()
    return obj


def new_part(doc: Any, session: Any) -> Any:
    """Pièce par défaut créée comme par la commande, dans son conteneur, puis accrochée."""
    obj = api.make_wood_part(doc=doc)
    placement_module.add_to_container(obj, session.container)
    placement_module.snap_part(obj, session)
    doc.recompute()
    return obj


def snapped(doc: Any, *elements: Any, view: Vec3 = ABOVE) -> tuple[Any, Any, Any]:
    """(pièce, session, lecture) pour les ``elements`` sélectionnés dans cet ordre."""
    reading = targets.read_targets(list(elements), view)
    session = targets.new_session(reading, geometry_dimensions(doc))
    return new_part(doc, session), session, reading


def geometry_dimensions(doc: Any) -> Any:
    wood_part = pytest.importorskip("freecad.menuiserie.features.wood_part")
    return wood_part.DEFAULT_DIMENSIONS


def distance(obj: Any, shape: Any) -> float:
    return float(geometry.global_shape(obj).distToShape(shape)[0])


def overlap(obj: Any, shape: Any) -> float:
    return float(geometry.global_shape(obj).common(shape).Volume)


def element_shape(root: Any, subname: str) -> Any:
    return Part.getShape(root, subname, needSubElement=True)


def assert_touching(obj: Any, session: Any) -> None:
    """La pièce touche chaque élément retenu (T3)."""
    assert session.targets
    for shape in session.shapes:
        assert distance(obj, shape) <= CONTACT_TOLERANCE_MM


# --- T1 à T3 : face, arête, sommet d'une pièce de bois ------------------------------------------


@pytest.fixture
def block(document: Any) -> Any:
    """Pièce de bois M1 600 x 300 x 22, posée en (100, 50, 30)."""
    obj = api.make_wood_part(600, 300, 22, "chene", mark="M1", doc=document)
    obj.Placement = App.Placement(App.Vector(100, 50, 30), App.Rotation())
    document.recompute()
    return obj


def test_face_d_une_piece_de_bois(document: Any, block: Any) -> None:
    top = find_face(block, (0, 0, 1), 52)
    obj, session, reading = snapped(document, pick(block, top))
    assert reading.ignored == ()
    assert_touching(obj, session)
    assert overlap(obj, block.Shape) < OVERLAP_MM3
    box_ = geometry.global_shape(obj).BoundBox
    assert (round(box_.ZMin, 6), round(box_.ZMax, 6)) == (52, 74)  # à plat sur le dessus


def test_point_clique_choisit_le_coin(document: Any, block: Any) -> None:
    top = find_face(block, (0, 0, 1), 52)
    corner = Vec3(700, 350, 52)  # coin (x max, y max) du dessus
    obj, session, _reading = snapped(document, pick(block, top, Vec3(690, 340, 52)))
    assert_touching(obj, session)
    assert distance(obj, Part.Vertex(App.Vector(corner.x, corner.y, corner.z))) < 1e-6
    assert overlap(obj, block.Shape) < OVERLAP_MM3


def test_arete_d_une_piece_de_bois(document: Any, block: Any) -> None:
    shape = geometry.global_shape(block)
    wanted = [
        index
        for index, edge in enumerate(shape.Edges, start=1)
        if abs(edge.valueAt(edge.FirstParameter).z - 52) < 1e-6
        and abs(edge.valueAt(edge.LastParameter).z - 52) < 1e-6
        and abs(edge.valueAt(edge.FirstParameter).y - 50) < 1e-6
        and abs(edge.valueAt(edge.LastParameter).y - 50) < 1e-6
    ]
    assert len(wanted) == 1
    obj, session, _reading = snapped(document, pick(block, f"Edge{wanted[0]}"))
    assert_touching(obj, session)
    assert overlap(obj, block.Shape) < OVERLAP_MM3


def test_sommet_d_une_piece_de_bois_sans_chevauchement(document: Any, block: Any) -> None:
    shape = geometry.global_shape(block)
    index = next(
        i
        for i, vertex in enumerate(shape.Vertexes, start=1)
        if vertex.Point.isEqual(App.Vector(700, 350, 52), 1e-6)
    )
    obj, session, _reading = snapped(document, pick(block, f"Vertex{index}"))
    assert_touching(obj, session)
    assert overlap(obj, block.Shape) < OVERLAP_MM3  # l'octant libre a été choisi


# --- T3 : objets d'autres ateliers --------------------------------------------------------------


def test_face_d_un_cube_part_box(document: Any) -> None:
    cube = box(document, (200, 200, 200), (0, 0, 0))
    obj, session, _reading = snapped(document, pick(cube, find_face(cube, (1, 0, 0), 200)))
    assert_touching(obj, session)
    assert overlap(obj, cube.Shape) < OVERLAP_MM3


def test_face_cylindrique_d_un_part_cylinder(document: Any) -> None:
    cylinder = document.addObject("Part::Cylinder", "Cylindre")
    cylinder.Radius, cylinder.Height = 50, 300
    document.recompute()
    lateral = next(
        f"Face{i}"
        for i, face in enumerate(cylinder.Shape.Faces, start=1)
        if not isinstance(face.Surface, Part.Plane)
    )
    element = pick(cylinder, lateral, Vec3(50, 0, 150))
    obj, session, reading = snapped(document, element)
    assert reading.targets[0].planar is False
    assert_touching(obj, session)


def test_arete_libre_d_une_esquisse(document: Any) -> None:
    sketch = document.addObject("Sketcher::SketchObject", "Esquisse")
    sketch.addGeometry(Part.LineSegment(App.Vector(0, 0, 0), App.Vector(300, 0, 0)))
    document.recompute()
    obj, session, _reading = snapped(document, pick(sketch, "Edge1"))
    assert_touching(obj, session)


def test_face_d_un_corps_partdesign_dans_un_std_part(document: Any) -> None:
    part = document.addObject("App::Part", "Meuble")
    body = document.addObject("PartDesign::Body", "Corps")
    part.addObject(body)
    path = picked.PickedElement(part, "Corps.Face1")
    assert picked.container_of(path) == part  # jamais le corps
    assert picked.container_of(picked.PickedElement(body, "Face1")) is None


def test_objet_entier_et_objet_sans_forme_sont_ignores(document: Any, block: Any) -> None:
    sheet = document.addObject("Spreadsheet::Sheet", "Feuille")
    document.recompute()
    reading = targets.read_targets(
        [pick(block, ""), pick(sheet, "Face1"), pick(block, "Face99")], ABOVE
    )
    assert reading.targets == ()
    assert len(reading.ignored) == 3
    session = targets.new_session(reading, geometry_dimensions(document))
    assert session.targets == ()
    obj = new_part(document, session)  # comportement sans sélection : à l'origine
    assert obj.Placement.Base.isEqual(App.Vector(0, 0, 0), 1e-9)


# --- T2 : côté extérieur ------------------------------------------------------------------------


def test_face_sans_solide_cote_de_l_observateur(document: Any) -> None:
    plane = document.addObject("Part::Plane", "Plan")
    plane.Length, plane.Width = 400, 300
    document.recompute()
    above, _s, _r = snapped(document, pick(plane, "Face1"), view=Vec3(0, 0, 1))
    assert geometry.global_shape(above).BoundBox.ZMin == pytest.approx(0, abs=1e-6)
    assert geometry.global_shape(above).BoundBox.ZMax == pytest.approx(22, abs=1e-6)
    below, _s, _r = snapped(document, pick(plane, "Face1"), view=Vec3(0, 0, -1))
    assert geometry.global_shape(below).BoundBox.ZMax == pytest.approx(0, abs=1e-6)


def test_normale_des_faces_d_un_solide_vers_l_exterieur(document: Any) -> None:
    cube = box(document, (100, 100, 100), (0, 0, 0))
    for normal, coordinate in (((0, 0, 1), 100), ((0, 0, -1), 0), ((-1, 0, 0), 0)):
        face = find_face(cube, normal, coordinate)
        target = targets.target_of(pick(cube, face), Vec3(0, 0, -1))  # observateur dessous
        assert (target.frame.z.x, target.frame.z.y, target.frame.z.z) == pytest.approx(normal)


# --- T4 : conteneur -----------------------------------------------------------------------------


def test_std_part_tourne_et_deplace(document: Any) -> None:
    part = document.addObject("App::Part", "Meuble")
    part.Placement = App.Placement(App.Vector(1000, 500, 0), App.Rotation(App.Vector(0, 0, 1), 90))
    cube = box(document, (200, 100, 150), (0, 0, 0))
    part.addObject(cube)
    document.recompute()
    face = find_face(cube, (0, 0, 1), 150)
    obj, session, _reading = snapped(document, pick(part, f"Bloc.{face}"))
    assert session.container == part
    assert obj.getParentGeoFeatureGroup() == part
    assert_touching(obj, session)  # vérifié en coordonnées globales
    assert overlap(obj, geometry.global_shape(cube)) < OVERLAP_MM3
    local = placement_module.local_placement(obj.getGlobalPlacement(), part.getGlobalPlacement())
    assert local.Base.isEqual(obj.Placement.Base, 1e-6)


def test_element_vu_a_travers_un_lien_reste_a_cote_de_la_copie(document: Any) -> None:
    cube = box(document, (200, 100, 150), (0, 0, 0))
    link = document.addObject("App::Link", "Copie")
    link.LinkedObject = cube
    link.Placement = App.Placement(App.Vector(2000, 0, 0), App.Rotation())
    document.recompute()
    element = pick(link, "Face6")
    assert picked.container_of(element) is None  # jamais dans l'original
    obj, session, _reading = snapped(document, element)
    assert obj.getParentGeoFeatureGroup() is None
    assert geometry.global_shape(obj).BoundBox.XMin >= 2000 - 1e-6  # à côté de la copie
    assert_touching(obj, session)


def test_lien_dans_un_std_part_garde_le_std_part(document: Any) -> None:
    part = document.addObject("App::Part", "Meuble")
    cube = box(document, (200, 100, 150), (0, 0, 0))
    link = document.addObject("App::Link", "Copie")
    link.LinkedObject = cube
    part.addObject(link)
    document.recompute()
    assert picked.container_of(pick(part, "Copie.Face6")) == part


# --- T3, S8, Q2 : deux joues face à face ---------------------------------------------------------


def inner_faces(bureau: Bureau) -> tuple[Any, Any]:
    left, right = bureau.shown("JG"), bureau.shown("JD")
    return (
        pick(left, find_face(left, (1, 0, 0), 22)),
        pick(right, find_face(right, (-1, 0, 0), -1178)),
    )


def test_tablette_entre_deux_joues(bureau: Bureau) -> None:
    obj, session, reading = snapped(bureau.doc, *inner_faces(bureau))
    assert reading.ignored == ()
    assert session.notices == ()
    assert obj.Length.Value == pytest.approx(1156)  # écart entre les joues (Q2)
    assert obj.Thickness.Value == pytest.approx(22)  # l'épaisseur n'est jamais étirée
    assert_touching(obj, session)
    size = geometry.global_shape(obj).BoundBox
    assert size.ZLength == pytest.approx(22)  # la tablette est horizontale
    assert size.XLength == pytest.approx(1156)


def test_la_saisie_du_menuisier_l_emporte_sur_l_etirement(bureau: Bureau) -> None:
    obj, session, _reading = snapped(bureau.doc, *inner_faces(bureau))
    obj.Length = 500
    placement_module.snap_part(obj, session)  # recalcul après la saisie (T6, T7)
    assert obj.Length.Value == pytest.approx(500)
    first = session.shapes[0]
    assert distance(obj, first) <= CONTACT_TOLERANCE_MM


def test_rotations_gardent_la_piece_accrochee(document: Any, block: Any) -> None:
    top = find_face(block, (0, 0, 1), 52)
    obj, session, _reading = snapped(document, pick(block, top))
    for turn in (Turn.X, Turn.Y, Turn.Z, Turn.X, Turn.Z, Turn.Y):
        assert placement_module.rotate_part(obj, turn, session)
        document.recompute()
        assert_touching(obj, session)
        assert overlap(obj, block.Shape) < OVERLAP_MM3


def test_face_inclinee_les_boutons_restent_coherents(document: Any) -> None:
    cube = box(document, (300, 300, 100), (0, 0, 0))
    cube.Placement = App.Placement(App.Vector(0, 0, 0), App.Rotation(App.Vector(0, 1, 0), 30))
    document.recompute()
    up = cube.Placement.Rotation.multVec(App.Vector(0, 0, 1))
    slope = pick(cube, find_face(cube, (up.x, up.y, up.z)))
    obj, session, _reading = snapped(document, slope)
    for turn in (Turn.X, Turn.Y, Turn.Z):
        placement_module.rotate_part(obj, turn, session)
        document.recompute()
        assert_touching(obj, session)


# --- T5 : ensemble ------------------------------------------------------------------------------


def test_ensemble_candidat_et_tablette_qui_suit(bureau: Bureau) -> None:
    left, right = inner_faces(bureau)
    assert picked.furniture_candidate(left) == bureau.furniture
    obj, session, _reading = snapped(bureau.doc, left, right)
    assert session.furniture == bureau.furniture
    api.add_to_furniture(session.furniture, [obj])
    api.resize_furniture(bureau.furniture, width=1300)
    bureau.doc.recompute()
    assert obj.Length.Value == pytest.approx(1256)  # la tablette suit (L + 100)


def test_pas_d_ensemble_pour_une_piece_libre(document: Any, block: Any) -> None:
    element = pick(block, find_face(block, (0, 0, 1), 52))
    assert picked.furniture_candidate(element) is None


# --- T1 : rien n'est modifié ---------------------------------------------------------------------


def snapshot(obj: Any) -> tuple[Any, ...]:
    return (
        obj.Placement.copy(),
        obj.Shape.Volume,
        len(obj.ExpressionEngine),
        sorted(obj.PropertiesList),
    )


def test_les_objets_selectionnes_ne_sont_pas_modifies(document: Any, block: Any) -> None:
    reference = snapshot(block)
    snapped(document, pick(block, find_face(block, (0, 0, 1), 52)))
    assert snapshot(block) == reference
