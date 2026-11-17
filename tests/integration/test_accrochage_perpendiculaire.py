# SPDX-License-Identifier: LGPL-2.1-or-later
"""Pièce créée contre une face de pièce de bois (#136) : perpendiculaire, mêmes largeur et
épaisseur. Rejoue la suite d'appels de la commande : ``read_targets``, ``perpendicular_start``,
``make_wood_part``, ``new_session``, ``snap_part``."""

from __future__ import annotations

from typing import Any

import pytest

from freecad.menuiserie.core.geometry import Vec3

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
Part = pytest.importorskip("Part")
api = pytest.importorskip("freecad.menuiserie.api")
picked = pytest.importorskip("freecad.menuiserie.features.picked")
perpendicular = pytest.importorskip("freecad.menuiserie.features.perpendicular")
placement_module = pytest.importorskip("freecad.menuiserie.features.placement")
geometry = pytest.importorskip("freecad.menuiserie.features.snap_geometry")
targets = pytest.importorskip("freecad.menuiserie.features.snap_targets")
wood_part = pytest.importorskip("freecad.menuiserie.features.wood_part")
pieces_galbees = pytest.importorskip("tests.integration.pieces_galbees")
cadre = pytest.importorskip("tests.integration.cadre")
types_assemblages = pytest.importorskip("tests.integration.types_assemblages")

ABOVE = Vec3(0, 0, 1)


@pytest.fixture
def board(document: Any) -> Any:
    """Pièce de bois 800 x 100 x 30 en (0, 0, 0)."""
    obj = api.make_wood_part(800, 100, 30, doc=document)
    document.recompute()
    return obj


def face_at(obj: Any, normal: tuple[float, float, float], coordinate: float) -> str:
    shape = geometry.global_shape(obj)
    wanted = App.Vector(*normal)
    for index, face in enumerate(shape.Faces, start=1):
        u, v = face.Surface.parameter(face.CenterOfMass)
        if (
            face.normalAt(u, v).getAngle(wanted) < 1e-6
            and abs(face.CenterOfMass.dot(wanted) - coordinate) < 1e-6
        ):
            return f"Face{index}"
    raise AssertionError("face introuvable")


def create_against(
    document: Any, root: Any, subname: str, click: Vec3 | None = None
) -> tuple[Any, Any]:
    """(pièce créée, départ perpendiculaire) comme le fait la commande ; ``click`` : point cliqué
    (coordonnées globales)."""
    reading = targets.read_targets([picked.PickedElement(root, subname, click)], ABOVE)
    start = perpendicular.perpendicular_start(reading)
    assert start is not None
    part = api.make_wood_part(width=start.width, thickness=start.thickness, doc=document)
    session = targets.new_session(start.reading, wood_part.dimensions_of(part), start.orientation)
    placement_module.snap_part(part, session)
    document.recompute()
    return part, start


def test_extremite_angle_droit_avec_la_piece(document: Any, board: Any) -> None:
    part, start = create_against(document, board, face_at(board, (1, 0, 0), 800))
    assert (start.width, start.thickness) == (100, 30)
    box = geometry.global_shape(part).BoundBox
    assert round(box.XMin, 6) == 800  # appuyée sur l'extrémité
    assert round(box.XMax - box.XMin, 6) == 30  # son épaisseur part de la face
    assert round(box.ZMax - box.ZMin, 6) == 800  # longueur selon l'épaisseur de l'autre pièce
    assert (round(box.YMin, 6), round(box.YMax, 6)) == (0, 100)  # largeur parallèle


def test_grande_face_dresse_la_piece(document: Any, board: Any) -> None:
    part, _start = create_against(document, board, face_at(board, (0, 0, 1), 30))
    box = geometry.global_shape(part).BoundBox
    assert round(box.ZMin, 6) == 30  # posée sur la face, longueur vers le haut
    assert round(box.ZMax - box.ZMin, 6) == 800
    assert round(box.YMax - box.YMin, 6) == 100  # largeur parallèle à celle de la pièce
    assert round(box.XMax - box.XMin, 6) == 30


def test_largeur_et_epaisseur_restent_modifiables(document: Any, board: Any) -> None:
    part, _start = create_against(document, board, face_at(board, (1, 0, 0), 800))
    part.Width = 60
    document.recompute()
    assert part.Width.Value == 60


def test_aucun_depart_pour_un_objet_d_un_autre_atelier(document: Any) -> None:
    cube = document.addObject("Part::Box", "Bloc")
    document.recompute()
    reading = targets.read_targets([picked.PickedElement(cube, "Face6", None)], ABOVE)
    assert perpendicular.perpendicular_start(reading) is None


def converted_rail(document: Any, placement: Any) -> Any:
    """Pièce en bois (corps converti) de la traverse galbée, posée au ``placement``."""
    rail = pieces_galbees.shaped(pieces_galbees.curved_rail(document))
    rail.Placement = placement
    document.recompute()
    return rail


def test_piece_convertie_extremite_perpendiculaire(document: Any) -> None:
    rail = converted_rail(document, App.Placement(App.Vector(100, 50, 0), App.Rotation()))
    xmax = geometry.global_shape(rail).BoundBox.XMax
    part, start = create_against(document, rail, face_at(rail, (1, 0, 0), xmax))
    assert (round(start.width, 6), round(start.thickness, 6)) == (95, 45)
    box = geometry.global_shape(part).BoundBox
    assert round(box.XMin, 6) == round(xmax, 6)
    assert round(box.XMax - box.XMin, 6) == 45  # son épaisseur part de la face
    # longueur (par défaut) selon l'épaisseur de la traverse
    assert round(box.ZMax - box.ZMin, 6) == round(part.Length.Value, 6)


def test_piece_convertie_tournee_perpendiculaire(document: Any) -> None:
    turned = App.Placement(App.Vector(0, 0, 0), App.Rotation(App.Vector(0, 0, 1), 90))
    rail = converted_rail(document, turned)
    ymax = geometry.global_shape(rail).BoundBox.YMax
    part, _start = create_against(document, rail, face_at(rail, (0, 1, 0), ymax))
    box = geometry.global_shape(part).BoundBox
    assert round(box.YMin, 6) == round(ymax, 6)  # appuyée sur l'extrémité tournée
    assert round(box.ZMax - box.ZMin, 6) == round(part.Length.Value, 6)


def test_piece_convertie_section_de_la_face_selectionnee(document: Any) -> None:
    """Bout plus étroit que l'encombrement (pièce en L) : la nouvelle pièce prend la largeur de la
    face sélectionnée, pas celle de la pièce, et reste sur la face."""
    solid = Part.makeBox(400, 100, 50).cut(Part.makeBox(200, 60, 50, App.Vector(200, 40, 0)))
    source = document.addObject("Part::Feature", "EnL")
    source.Shape = solid
    document.recompute()
    angle = pieces_galbees.shaped(source)
    assert round(angle.Width.Value, 6) == 100
    xmax = geometry.global_shape(angle).BoundBox.XMax
    part, start = create_against(document, angle, face_at(angle, (1, 0, 0), xmax))
    assert (round(start.width, 6), round(start.thickness, 6)) == (40, 50)
    box = geometry.global_shape(part).BoundBox
    assert round(box.XMin, 6) == round(xmax, 6)
    assert round(box.YMax - box.YMin, 6) == 40
    face_box = geometry.global_shape(angle).BoundBox
    assert round(box.YMin - face_box.YMin, 6) == 0  # alignée sur la face étroite (y de 0 à 40)


def test_piece_convertie_largeur_a_l_endroit_du_clic(document: Any) -> None:
    """Dessus d'une pièce en L : cliqué sur le bras étroit (y de 0 à 40), la nouvelle pièce prend
    40 de large et s'y cale ; cliqué sur la partie large, elle prend 100."""
    solid = Part.makeBox(400, 100, 50).cut(Part.makeBox(200, 60, 50, App.Vector(200, 40, 0)))
    source = document.addObject("Part::Feature", "EnL")
    source.Shape = solid
    document.recompute()
    angle = pieces_galbees.shaped(source)
    top = geometry.global_shape(angle).BoundBox
    face = face_at(angle, (0, 0, 1), top.ZMax)
    narrow, _ = create_against(document, angle, face, Vec3(top.XMin + 350, top.YMin + 20, top.ZMax))
    box = geometry.global_shape(narrow).BoundBox
    assert round(box.YMax - box.YMin, 6) == 40
    assert (round(box.YMin - top.YMin, 6), round(box.ZMin - top.ZMax, 6)) == (0, 0)
    wide, _ = create_against(document, angle, face, Vec3(top.XMin + 100, top.YMin + 70, top.ZMax))
    assert round(geometry.global_shape(wide).BoundBox.YMax - top.YMin, 6) == 100


def test_piece_usinee_largeur_mesuree_sur_la_brute(document: Any) -> None:
    """Chant d'un montant mortaisé aux deux bouts : les mortaises coupent la face usinée, mais la
    pièce se cale sur le rectangle de la brute (x de 0 à 600), pas entre les mortaises."""
    frame = cadre.build_frame(document)
    frame.assemble()
    stile = frame.machined("M1")
    chant = face_at(stile, (0, 1, 0), 60)
    part, _start = create_against(document, stile, chant, Vec3(300, 60, 11))
    box = geometry.global_shape(part).BoundBox
    assert round(box.YMin, 6) == 60  # sur le chant
    assert round(box.XMin, 6) == 0  # calée au coin de la brute, pas au bord d'une mortaise


def test_largeur_mesuree_sur_la_face_exterieure_de_la_brute(document: Any) -> None:
    """Feuillure au bord du dessous (y de 290 à 300, 6 mm de profondeur) : cliqué dans la feuillure,
    à 5 mm de l'arête du bord (y = 300), la pièce suit cette arête : sa largeur est la longueur de
    l'arête (600), pas la largeur de la feuillure (10), calée sur la face extérieure (y = 290)."""
    montage = types_assemblages.build(document, types_assemblages.RABBET, App.Placement())
    host = api.machined_part_of(montage.host)
    recessed = face_at(host, (0, 0, -1), -6)
    part, start = create_against(document, host, recessed, Vec3(300, 295, 6))
    assert round(start.width, 6) == 600
    box = geometry.global_shape(part).BoundBox
    assert (round(box.XLength, 6), round(box.YMax, 6)) == (600, 290)


def triangle(document: Any) -> Any:
    """Prisme triangulaire isocèle (base 400, hauteur 100, épaisseur 50), converti en pièce."""
    points = [App.Vector(*xy, 0) for xy in ((0, 0), (400, 0), (200, 100), (0, 0))]
    source = document.addObject("Part::Feature", "Triangle")
    source.Shape = Part.Face(Part.makePolygon(points)).extrude(App.Vector(0, 0, 50))
    document.recompute()
    return pieces_galbees.shaped(source)


@pytest.mark.parametrize("click", [(100, 10), (200, 50), (5, 1), (395, 1)])
def test_face_triangulaire_la_piece_reste_dans_la_face(
    document: Any, click: tuple[float, float]
) -> None:
    """Face triangulaire (arêtes obliques) : la nouvelle pièce, calée au coin le plus proche du
    clic, ne déborde pas de la face."""
    angle = triangle(document)
    face = face_at(angle, (0, 0, 1), 50)
    part, _start = create_against(document, angle, face, Vec3(click[0], click[1], 50))
    top = next(f for f in geometry.global_shape(angle).Faces if abs(f.CenterOfMass.z - 50) < 1e-6)
    box = geometry.global_shape(part).BoundBox
    slab = Part.makeBox(box.XLength, box.YLength, 1, App.Vector(box.XMin, box.YMin, 49))
    assert slab.cut(top.extrude(App.Vector(0, 0, -1))).Volume < 1e-2


@pytest.mark.parametrize("click", [(200, 99.99), (399.9, 0.01), (0.05, 0.02)])
def test_clic_pres_d_une_pointe_pas_de_depart_perpendiculaire(
    document: Any, click: tuple[float, float]
) -> None:
    """À moins de 0,1 mm d'un sommet aigu il ne reste pas la place d'une pièce : pas de départ
    perpendiculaire (l'accrochage habituel s'applique), la pièce ne déborde pas de la face."""
    angle = triangle(document)
    face = face_at(angle, (0, 0, 1), 50)
    reading = targets.read_targets(
        [picked.PickedElement(angle, face, Vec3(click[0], click[1], 50))], ABOVE
    )
    assert perpendicular.perpendicular_start(reading) is None


def inside(part: Any, owner: Any, normal: tuple[float, float, float], coordinate: float) -> bool:
    """La pièce posée ne déborde pas de la face ``normal`` = ``coordinate`` de ``owner``."""
    face = next(
        f
        for f in geometry.global_shape(owner).Faces
        if abs(f.normalAt(*f.Surface.parameter(f.CenterOfMass)).dot(App.Vector(*normal))) > 0.999
        and abs(f.CenterOfMass.dot(App.Vector(*normal)) - coordinate) < 1e-6
    )
    box = geometry.global_shape(part).BoundBox
    bound = face.BoundBox
    return (
        box.XMin >= bound.XMin - 1e-6
        and box.XMax <= bound.XMax + 1e-6
        and box.YMin >= bound.YMin - 1e-6
        and box.YMax <= bound.YMax + 1e-6
    )


@pytest.mark.parametrize(
    ("click", "width"),
    [
        ((400, 5, 30), 800),  # arête longue la plus proche : la largeur la longe
        ((400, 95, 30), 800),
        ((5, 50, 30), 100),  # arête courte (bout) la plus proche
        ((795, 50, 30), 100),
        ((5, 5, 30), 100),  # coin : 5 de chaque côté, égalité
        ((795, 95, 30), 100),
        ((400, 50, 30), 800),  # milieu : l'arête longue (50) est bien plus proche du bout (400)
        ((50, 50, 30), 100),  # égalité stricte (50 du bord, 50 du bout) : le bout l'emporte
    ],
)
def test_grande_face_largeur_selon_l_arete_la_plus_proche(
    document: Any, board: Any, click: tuple[float, float, float], width: float
) -> None:
    part, start = create_against(document, board, face_at(board, (0, 0, 1), 30), Vec3(*click))
    assert round(start.width, 6) == width
    assert round(start.thickness, 6) == 30
    assert inside(part, board, (0, 0, 1), 30)
    box = geometry.global_shape(part).BoundBox
    assert round(box.ZMin, 6) == 30


def test_grande_face_clic_proche_du_bout_meme_distance_que_l_arete_longue(
    document: Any, board: Any
) -> None:
    """Égalité stricte (10 du bout et 10 du bord) : le résultat est stable d'un appel à l'autre."""
    face = face_at(board, (0, 0, 1), 30)
    first, a = create_against(document, board, face, Vec3(10, 10, 30))
    second, b = create_against(document, board, face, Vec3(10, 10, 30))
    assert (a.width, a.thickness) == (b.width, b.thickness)
    assert (
        geometry.global_shape(first).BoundBox.XLength
        == geometry.global_shape(second).BoundBox.XLength
    )


@pytest.mark.parametrize("click", [(400, 0.2, 30), (0.2, 50, 30), (400, 99.8, 30)])
def test_clic_tres_pres_du_bord(
    document: Any, board: Any, click: tuple[float, float, float]
) -> None:
    part, _start = create_against(document, board, face_at(board, (0, 0, 1), 30), Vec3(*click))
    assert inside(part, board, (0, 0, 1), 30)


def test_chant_etroit_la_piece_reste_sur_le_chant(document: Any, board: Any) -> None:
    """Chant (y = 100, 800 x 30) : clic près du bout ou près du bord, jamais de débord."""
    chant = face_at(board, (0, 1, 0), 100)
    for click in ((400, 100, 3), (400, 100, 27), (3, 100, 15), (797, 100, 15)):
        part, start = create_against(document, board, chant, Vec3(*click))
        box = geometry.global_shape(part).BoundBox
        assert round(box.YMin, 6) == 100
        assert box.XMin >= -1e-6 and box.XMax <= 800 + 1e-6
        assert box.ZMin >= -1e-6 and box.ZMax <= 30 + 1e-6
        assert start.thickness <= 100 + 1e-6


@pytest.mark.parametrize("click", [(100, 5, 15), (100, 95, 15), (100, 50, 3)])
def test_extremite_la_piece_reste_couchee_et_dans_la_face(
    document: Any, board: Any, click: tuple[float, float, float]
) -> None:
    """Extrémité (x = 800, 100 x 30) : pas de quart de tour, quelle que soit l'arête proche."""
    part, start = create_against(
        document, board, face_at(board, (1, 0, 0), 800), Vec3(800, click[1], click[2])
    )
    assert (round(start.width, 6), round(start.thickness, 6)) == (100, 30)
    box = geometry.global_shape(part).BoundBox
    assert round(box.XMin, 6) == 800
    assert box.YMin >= -1e-6 and box.YMax <= 100 + 1e-6


@pytest.mark.parametrize("click", [(400, 5, 30), (5, 50, 30), (5, 5, 30)])
def test_piece_porteuse_tournee_de_90_degres(
    document: Any, click: tuple[float, float, float]
) -> None:
    """Pièce porteuse tournée de 90° autour de Z : la règle vaut dans le repère global."""
    turned = api.make_wood_part(800, 100, 30, doc=document)
    turned.Placement = App.Placement(App.Vector(0, 0, 0), App.Rotation(App.Vector(0, 0, 1), 90))
    document.recompute()
    box = geometry.global_shape(turned).BoundBox  # x de -100 à 0, y de 0 à 800
    top = face_at(turned, (0, 0, 1), 30)
    point = Vec3(box.XMin + click[1], box.YMin + click[0], 30)
    part, start = create_against(document, turned, top, point)
    # arête la plus proche : longue (selon Y global) ou courte (selon X global)
    near_long = min(click[1], 100 - click[1]) < min(click[0], 800 - click[0])
    expected = 800 if near_long else 100
    assert round(start.width, 6) == expected
    new_box = geometry.global_shape(part).BoundBox
    assert new_box.XMin >= box.XMin - 1e-6 and new_box.XMax <= box.XMax + 1e-6
    assert new_box.YMin >= box.YMin - 1e-6 and new_box.YMax <= box.YMax + 1e-6


@pytest.mark.parametrize("click", [(100, 10), (200, 50), (300, 10), (10, 3), (390, 3)])
def test_face_triangulaire_largeur_dans_la_face(document: Any, click: tuple[float, float]) -> None:
    """Arêtes obliques : la largeur reste dans les bornes et la pièce ne dépasse pas le triangle."""
    angle = triangle(document)
    face = face_at(angle, (0, 0, 1), 50)
    part, start = create_against(document, angle, face, Vec3(click[0], click[1], 50))
    assert 0.1 <= start.width <= 400
    box = geometry.global_shape(part).BoundBox
    assert box.XMin >= -1e-6 and box.XMax <= 400 + 1e-6
    assert box.YMin >= -1e-6 and box.YMax <= 100 + 1e-6


def test_clic_pres_de_l_arete_oblique_largeur_ne_depasse_pas_la_face(document: Any) -> None:
    """Clic à 2 mm de l'hypoténuse (arête oblique), loin des deux axes : pas de débord."""
    angle = triangle(document)
    face = face_at(angle, (0, 0, 1), 50)
    top = next(f for f in geometry.global_shape(angle).Faces if abs(f.CenterOfMass.z - 50) < 1e-6)
    part, _start = create_against(document, angle, face, Vec3(100, 48, 50))
    box = geometry.global_shape(part).BoundBox
    slab = Part.makeBox(box.XLength, box.YLength, 1, App.Vector(box.XMin, box.YMin, 49))
    assert slab.cut(top.extrude(App.Vector(0, 0, -1))).Volume < 1e-2
