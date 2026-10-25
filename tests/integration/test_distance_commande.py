# SPDX-License-Identifier: LGPL-2.1-or-later
"""``api.set_distance`` : déplacer une pièce pour fixer la distance entre deux éléments (DI-b,
critères E3 et E4, scénarios de E6, ADR 0022)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from tests.elements_choisis import element_name
from tests.integration.bureau import build_desk, build_parts

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
api = pytest.importorskip("freecad.menuiserie.api")

Point = tuple[float, float, float]
Pick = Callable[[Any, str, Point], Any]
TOLERANCE = 1e-6
PLATEAU_BAS: Point = (400, 100, 700)
ETAGERE_HAUT: Point = (300, 100, 122)


@pytest.fixture
def pick() -> Pick:
    """``pick(objet, "Face", (x, y, z))`` : l'élément (face, arête ou sommet) de l'objet dont le
    centre est le plus proche du point donné (coordonnées globales)."""

    def choose(obj: Any, kind: str, near: Point) -> Any:
        return api.PickedElement(obj, element_name(obj, kind, near))

    return choose


def part(doc: Any, size: Point, base: Point, label: str) -> Any:
    obj = api.make_wood_part(*size, "chene", doc=doc)
    obj.Label = label
    obj.Placement = App.Placement(App.Vector(*base), App.Rotation())
    doc.recompute()
    return obj


def position(obj: Any) -> Point:
    base = obj.Placement.Base
    return (round(base.x, 6), round(base.y, 6), round(base.z, 6))


def reference_box(doc: Any, base: Point, size: float = 50) -> Any:
    """Cube de Part (autre atelier), jamais déplacé."""
    box = doc.addObject("Part::Box", "Reference")
    box.Length = box.Width = box.Height = size
    box.Placement = App.Placement(App.Vector(*base), App.Rotation())
    doc.recompute()
    return box


def shelf_and_top(doc: Any) -> tuple[Any, Any]:
    return (
        part(doc, (800, 200, 22), (0, 0, 700), "Plateau"),
        part(doc, (600, 200, 22), (0, 0, 100), "Étagère"),
    )


def invalid_objects(doc: Any) -> list[str]:
    return [o.Name for o in doc.Objects if "Invalid" in o.State]


# --- E6 : trois scénarios de la recette -------------------------------------------------------


def test_face_face_etagere_sous_le_plateau(document: Any, pick: Pick) -> None:
    plateau, etagere = shelf_and_top(document)
    api.set_distance(pick(plateau, "Face", PLATEAU_BAS), pick(etagere, "Face", ETAGERE_HAUT), 320)
    assert position(etagere) == (0, 0, 358)  # dessus de l'étagère à 700 - 320 = 380
    assert position(plateau) == (0, 0, 700)
    assert not invalid_objects(document)


def test_sommet_face_tourillon_a_30_mm_du_bout(document: Any, pick: Pick) -> None:
    planche = part(document, (800, 200, 22), (0, 0, 0), "Planche")
    tourillon = part(document, (100, 20, 20), (500, 50, 30), "Tourillon")
    end = pick(planche, "Face", (800, 100, 11))
    corner = pick(tourillon, "Vertex", (500, 50, 30))
    api.set_distance(end, corner, 30)
    assert position(tourillon) == (770, 50, 30)


def test_arete_arete_traverse_alignee_a_0_mm(document: Any, pick: Pick) -> None:
    montant = part(document, (800, 100, 22), (0, 0, 0), "Montant")
    traverse = part(document, (800, 100, 22), (0, 150, 40), "Traverse")
    reference = pick(montant, "Edge", (400, 0, 22))  # arête du dessus, le long de X
    moved = pick(traverse, "Edge", (400, 150, 62))  # arête parallèle de la traverse
    api.set_distance(reference, moved, 0)
    assert position(traverse) == (0, 0, 0)  # arêtes confondues


# --- E3 : pièce déplacée -----------------------------------------------------------------------


def test_la_piece_du_second_element_bouge_par_defaut(document: Any, pick: Pick) -> None:
    plateau, etagere = shelf_and_top(document)
    api.set_distance(pick(etagere, "Face", ETAGERE_HAUT), pick(plateau, "Face", PLATEAU_BAS), 320)
    assert position(etagere) == (0, 0, 100)
    assert position(plateau) == (0, 0, 442)  # dessous du plateau à 320 mm du dessus de l'étagère


def test_inverser_la_piece_deplacee(document: Any, pick: Pick) -> None:
    plateau, etagere = shelf_and_top(document)
    under_top = pick(plateau, "Face", PLATEAU_BAS)
    api.set_distance(under_top, pick(etagere, "Face", ETAGERE_HAUT), 320, moving=under_top)
    assert position(etagere) == (0, 0, 100)
    assert position(plateau) == (0, 0, 442)


def test_une_reference_d_un_autre_atelier_ne_bouge_jamais(document: Any, pick: Pick) -> None:
    planche = part(document, (800, 200, 22), (0, 0, 0), "Planche")
    cube = reference_box(document, (900, 0, 0))
    # La planche est seconde, le cube premier : la planche bouge.
    api.set_distance(pick(cube, "Face", (900, 25, 25)), pick(planche, "Face", (800, 100, 11)), 0)
    assert position(cube) == (900, 0, 0)
    assert position(planche) == (100, 0, 0)
    # Cube second : il ne peut pas bouger, la planche (premier élément) bouge.
    api.set_distance(pick(planche, "Face", (900, 100, 11)), pick(cube, "Face", (900, 25, 25)), 10)
    assert position(cube) == (900, 0, 0)
    assert position(planche) == (90, 0, 0)  # bout à 890 : recule de la référence


def test_aucune_piece_de_l_atelier_refus_sans_changement(document: Any, pick: Pick) -> None:
    first = reference_box(document, (0, 0, 0))
    second = reference_box(document, (200, 0, 0))
    with pytest.raises(ValueError, match="Choisissez au moins une pièce de l'atelier"):
        api.set_distance(pick(first, "Face", (50, 25, 25)), pick(second, "Face", (200, 25, 25)), 10)
    assert position(first) == (0, 0, 0)
    assert position(second) == (200, 0, 0)


def test_piece_deplacee_explicite_invalide(document: Any, pick: Pick) -> None:
    planche = part(document, (800, 200, 22), (0, 0, 0), "Planche")
    cube = reference_box(document, (900, 0, 0))
    wood = pick(planche, "Face", (800, 100, 11))
    other = pick(cube, "Face", (900, 25, 25))
    with pytest.raises(ValueError, match="Choisissez au moins une pièce de l'atelier"):
        api.set_distance(wood, other, 10, moving=other)
    with pytest.raises(ValueError, match="doit porter l'un des deux éléments"):
        api.set_distance(wood, other, 10, moving=pick(planche, "Face", (0, 100, 11)))


def test_deux_elements_du_meme_objet_refuses(document: Any, pick: Pick) -> None:
    planche = part(document, (800, 200, 22), (0, 0, 0), "Planche")
    with pytest.raises(ValueError, match="deux objets différents"):
        api.set_distance(
            pick(planche, "Face", (0, 100, 11)), pick(planche, "Face", (800, 100, 11)), 5
        )


def test_la_piece_usinee_deplace_la_brute(document: Any, pick: Pick) -> None:
    bureau = build_parts(document)
    joue = bureau.parts["JG"]  # face extérieure à x = 0, bout vers +Z
    api.make_dowels(joue, bureau.parts["V"])
    machined = api.machined_part_of(joue)
    assert machined is not None
    cube = reference_box(document, (-500, 0, 0))
    wall = pick(cube, "Face", (-450, 25, 25))  # face du cube vers +X, à x = -450
    outside = pick(machined, "Face", (0, 280, 360))
    api.set_distance(wall, outside, 100)
    assert position(joue)[0] == pytest.approx(-328)  # face extérieure à x = -350
    assert machined.Placement == joue.Placement


# --- Axes et membres ---------------------------------------------------------------------------


def test_sommet_sommet_directe_puis_sur_un_axe(document: Any, pick: Pick) -> None:
    fixed = part(document, (100, 100, 20), (0, 0, 0), "Fixe")
    moved = part(document, (100, 100, 20), (300, 40, 0), "Mobile")
    first = pick(fixed, "Vertex", (0, 0, 0))
    second = pick(moved, "Vertex", (300, 40, 0))
    api.set_distance(first, second, 50, axis="X")
    assert position(moved) == (50, 40, 0)  # X seul ; Y inchangé
    api.set_distance(first, pick(moved, "Vertex", (50, 40, 0)), 0)  # directe
    assert position(moved) == (0, 0, 0)


def test_axe_inconnu(document: Any, pick: Pick) -> None:
    fixed = part(document, (100, 100, 20), (0, 0, 0), "Fixe")
    moved = part(document, (100, 100, 20), (300, 40, 0), "Mobile")
    with pytest.raises(ValueError, match="X, Y ou Z"):
        api.set_distance(
            pick(fixed, "Vertex", (0, 0, 0)), pick(moved, "Vertex", (300, 40, 0)), 5, axis="W"
        )
    assert position(moved) == (300, 40, 0)


def test_les_axes_sont_ceux_du_conteneur(document: Any, pick: Pick) -> None:
    container = document.addObject("App::Part", "Meuble")
    container.Placement = App.Placement(App.Vector(0, 0, 0), App.Rotation(App.Vector(0, 0, 1), 90))
    fixed = part(document, (100, 100, 20), (0, 0, 0), "Fixe")
    moved = part(document, (100, 100, 20), (0, 0, 0), "Mobile")
    container.addObject(moved)
    document.recompute()
    first = pick(fixed, "Vertex", (0, 0, 0))
    inside = pick(moved, "Vertex", (0, 0, 0)).subname
    second = api.PickedElement(container, f"{moved.Name}.{inside}")  # chemin de la sélection
    api.set_distance(first, second, 70, axis="X")  # X du Std Part = Y du document
    assert moved.getGlobalPlacement().Base.y == pytest.approx(70)
    assert moved.getGlobalPlacement().Base.x == pytest.approx(0)
    assert position(moved) == (70, 0, 0)  # placement local


def test_non_parallele_refuse(document: Any, pick: Pick) -> None:
    first = part(document, (800, 200, 22), (0, 0, 0), "A")
    second = part(document, (800, 200, 22), (0, 300, 0), "B")
    with pytest.raises(ValueError, match="ne sont pas parallèles"):
        api.set_distance(pick(first, "Face", (0, 100, 11)), pick(second, "Face", (400, 400, 22)), 5)
    assert position(second) == (0, 300, 0)


def test_arete_courbe_refusee(document: Any, pick: Pick) -> None:
    planche = part(document, (800, 200, 22), (0, 0, 0), "Planche")
    cylinder = document.addObject("Part::Cylinder", "Rond")
    cylinder.Placement = App.Placement(App.Vector(1000, 0, 0), App.Rotation())
    document.recompute()
    curved = next(
        i for i, e in enumerate(cylinder.Shape.Edges, 1) if e.Curve.TypeId != "Part::GeomLine"
    )
    with pytest.raises(ValueError, match="arête courbe"):
        api.set_distance(
            pick(planche, "Edge", (400, 0, 22)), api.PickedElement(cylinder, f"Edge{curved}"), 5
        )
    assert position(planche) == (0, 0, 0)


def test_formule_de_l_utilisateur_sur_l_axe_refusee(document: Any, pick: Pick) -> None:
    plateau, etagere = shelf_and_top(document)
    etagere.setExpression("Placement.Base.z", "100 mm")  # formule de l'utilisateur
    document.recompute()
    with pytest.raises(ValueError, match="piloté par une formule"):
        api.set_distance(
            pick(plateau, "Face", PLATEAU_BAS), pick(etagere, "Face", ETAGERE_HAUT), 320
        )
    assert position(etagere) == (0, 0, 100)
    expressions = {path.lstrip("."): text for path, text in etagere.ExpressionEngine}
    assert expressions["Placement.Base.z"] == "100 mm"


def test_une_formule_sur_un_autre_axe_n_empeche_pas(document: Any, pick: Pick) -> None:
    plateau, etagere = shelf_and_top(document)
    etagere.setExpression("Placement.Base.x", "0 mm")
    document.recompute()
    api.set_distance(pick(plateau, "Face", PLATEAU_BAS), pick(etagere, "Face", ETAGERE_HAUT), 320)
    assert position(etagere) == (0, 0, 358)


def test_membre_d_un_ensemble_est_relie(document: Any, pick: Pick) -> None:
    bureau = build_desk(document)
    plateau = bureau.parts["P"]
    cube = reference_box(document, (0, 0, 1000))
    below = pick(cube, "Face", (25, 25, 1000))  # dessous du cube, à z = 1000
    under = pick(plateau, "Face", (600, 300, 720))  # dessous du plateau, à z = 720
    api.set_distance(below, under, 100)  # le plateau descend : dessous à 900
    assert position(plateau)[2] == pytest.approx(900)
    document.recompute()  # une liaison oubliée ramènerait le plateau à sa place
    assert position(plateau)[2] == pytest.approx(900)
    assert not invalid_objects(document)
