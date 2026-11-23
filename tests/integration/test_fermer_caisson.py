# SPDX-License-Identifier: LGPL-2.1-or-later
"""« Fermer le caisson » dans le document (ADR 0064, critères FC4 à FC6 et FC10 de
``docs/specs/fermer-le-caisson.md``) : onglet, ancre tournée, ancre membre d'un ensemble,
liste de débit, pièces lisibles hors de l'atelier, refus avant création."""

from __future__ import annotations

from typing import Any

import pytest

from tests.integration.bureau import Bureau
from tests.integration.cadre import stale_or_invalid
from tests.integration.debit import marks_of
from tests.integration.pieces_galbees import curved_rail

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
api = pytest.importorskip("freecad.menuiserie.api")

X_AXIS = App.Vector(1, 0, 0)
ALL_ELEMENTS = frozenset(api.ClosingElement)


def anchor_part(doc: Any, size: tuple[float, float, float] = (600, 400, 18)) -> Any:
    """Dessous de référence (critère FC1), à plat en (0, 0, 0)."""
    part = api.make_wood_part(*size, "cp-bouleau", mark="Base", doc=doc)
    doc.recompute()
    return part


def members(furniture: Any) -> list[Any]:
    """Pièces brutes membres de ``furniture``."""
    return [o for o in furniture.InList if getattr(o, "Furniture", None) == furniture]


def by_label(furniture: Any) -> dict[str, Any]:
    """Pièces membres, par libellé sans suffixe d'unicité FreeCAD."""
    return {str(o.Label).split(" (")[0]: o for o in members(furniture)}


def bounds(obj: Any, *, world: bool = False) -> tuple[tuple[float, float], ...]:
    """Étendue (X, Y, Z) arrondie ; la forme est dans le repère du Std Part, sauf avec ``world``."""
    shape = obj.Shape.copy()
    if world:
        shape.Placement = obj.getGlobalPlacement()
    box = shape.BoundBox
    pairs = ((box.XMin, box.XMax), (box.YMin, box.YMax), (box.ZMin, box.ZMax))
    return tuple((round(lo, 3), round(hi, 3)) for lo, hi in pairs)


def sizes(part: Any) -> tuple[float, float, float]:
    return tuple(round(float(getattr(part, n).Value), 6) for n in ("Length", "Width", "Thickness"))  # type: ignore[return-value]


def dims_and_placement(part: Any) -> tuple[Any, ...]:
    """Cotes et position **dans le document** (le Std Part du caisson peut porter une rotation)."""
    base = part.getGlobalPlacement().Base
    return (*sizes(part), round(base.x, 6), round(base.y, 6), round(base.z, 6))


# --- Création de référence (FC1 dans le document) ---------------------------------------------


def test_fermer_le_caisson_de_reference(document: Any) -> None:
    anchor = anchor_part(document)
    before = dims_and_placement(anchor)
    furniture, notices = api.make_closed_carcass(anchor)
    assert notices == ()
    assert (furniture.Label, furniture.Template) == ("Caisson", "ClosedCarcass")
    sizes_box = [furniture.Width.Value, furniture.Depth.Value, furniture.Height.Value]
    assert sizes_box == pytest.approx([600, 400, 720])
    pieces = by_label(furniture)
    assert sorted(pieces) == ["Base", "Côté droit", "Côté gauche", "Dessus", "Fond"]
    assert pieces["Base"] == anchor
    assert dims_and_placement(anchor) == before  # l'ancre n'a ni bougé ni changé de cotes
    assert bounds(pieces["Côté gauche"]) == ((0, 18), (0, 400), (18, 702))
    assert bounds(pieces["Dessus"]) == ((0, 600), (0, 400), (702, 720))
    assert len(document.getObjectsByLabel("Tourillons")) == 0  # libellés « Tourillons : … »
    assert sum(o.Name.startswith("Dowels") for o in document.Objects) == 4
    assert sum(o.Name.startswith("Rabbet") for o in document.Objects) == 4
    assert stale_or_invalid(document) == []
    assert all(o.Shape.isValid() for o in members(furniture))


def test_le_caisson_qui_descend_depuis_le_dessus(document: Any) -> None:
    anchor = anchor_part(document)
    furniture, _ = api.make_closed_carcass(anchor, role=api.ClosingRole.TOP)
    pieces = by_label(furniture)
    assert bounds(pieces["Côté gauche"]) == ((0, 18), (0, 400), (-684, 0))
    assert bounds(pieces["Dessous"]) == ((0, 600), (0, 400), (-702, -684))
    assert tuple(furniture.Origin) == pytest.approx((0, 0, -702))
    assert bounds(anchor) == ((0, 600), (0, 400), (0, 18))
    assert stale_or_invalid(document) == []


def test_elements_desactives_et_avant(document: Any) -> None:
    anchor = anchor_part(document)
    elements = {api.ClosingElement.LEFT, api.ClosingElement.FRONT}
    furniture, _ = api.make_closed_carcass(anchor, elements=elements)
    assert sorted(by_label(furniture)) == ["Avant", "Base", "Côté gauche"]
    assert bounds(by_label(furniture)["Avant"]) == ((18, 600), (0, 18), (18, 720))
    assert stale_or_invalid(document) == []


# --- FC4 : onglet -----------------------------------------------------------------------------


def test_fc4_onglet_aux_angles(document: Any) -> None:
    anchor = anchor_part(document)
    before = dims_and_placement(anchor)
    furniture, _ = api.make_closed_carcass(anchor, joinery=api.ClosingJoinery.MITER)
    pieces = by_label(furniture)
    assert sizes(pieces["Côté gauche"]) == (720, 400, 18)
    assert bounds(pieces["Côté gauche"]) == ((0, 18), (0, 400), (0, 720))
    assert sum(o.Name.startswith("Miter") for o in document.Objects) == 4
    assert dims_and_placement(anchor) == before  # l'ancre garde Length, Width, Thickness, Placement
    machined = api.machined_part_of(anchor)
    assert machined is not None
    assert machined.Shape.Volume < anchor.Shape.Volume  # seule sa pièce usinée est coupée
    for part in (pieces["Côté gauche"], pieces["Dessus"]):
        assert api.machined_part_of(part).Shape.Volume < part.Shape.Volume
    assert stale_or_invalid(document) == []


@pytest.mark.parametrize(
    "joinery",
    [api.ClosingJoinery.DOVETAIL, api.ClosingJoinery.RABBET, api.ClosingJoinery.NONE],
)
def test_autres_assemblages_des_angles(document: Any, joinery: Any) -> None:
    anchor = anchor_part(document)
    furniture, _ = api.make_closed_carcass(anchor, joinery=joinery)
    names = {"Dovetail": "Dovetail", "Rabbet": "Rabbet", "None": ""}[joinery.value]
    count = sum(o.Name.startswith(names) for o in document.Objects) if names else 0
    assert count == {"Dovetail": 4, "Rabbet": 8, "None": 0}[joinery.value]  # feuillures du fond
    assert stale_or_invalid(document) == []
    assert all(o.Shape.isValid() for o in members(furniture))
    assert not [o for o in document.Objects if "Invalid" in o.State]
    assert furniture.Template == "ClosedCarcass"


@pytest.mark.parametrize("back", [api.BackJoinery.GROOVE, api.BackJoinery.NONE])
def test_fond_en_rainure_ou_pose(document: Any, back: Any) -> None:
    anchor = anchor_part(document)
    api.make_closed_carcass(anchor, back_joinery=back)
    grooves = sum(o.Name.startswith("TongueGroove") for o in document.Objects)
    assert grooves == (4 if back is api.BackJoinery.GROOVE else 0)
    assert stale_or_invalid(document) == []


# --- FC5 : ancre tournée ----------------------------------------------------------------------


def test_fc5_ancre_debout_tournee_de_90_degres_autour_de_x(document: Any) -> None:
    anchor = anchor_part(document)
    anchor.Placement = App.Placement(App.Vector(100, 50, 30), App.Rotation(X_AXIS, 90))
    document.recompute()
    before = dims_and_placement(anchor)
    placement = App.Placement(anchor.Placement)
    furniture, _ = api.make_closed_carcass(anchor)
    std = furniture.getParentGeoFeatureGroup()
    assert std.Placement.isSame(placement, 1e-9)  # l'ensemble porte la rotation de l'ancre
    for label in ("Base", "Dessus"):  # les pièces à plat ont la rotation de l'ancre
        part = by_label(furniture)[label]
        assert part.getGlobalPlacement().Rotation.isSame(placement.Rotation, 1e-9), label
    assert dims_and_placement(anchor) == before
    assert anchor.getGlobalPlacement().isSame(placement, 1e-9)  # l'ancre n'a pas bougé
    left = by_label(furniture)["Côté gauche"]
    shape = left.Shape.copy()  # vu dans le repère de l'ancre
    shape.Placement = placement.inverse().multiply(left.getGlobalPlacement())
    low = shape.BoundBox
    assert (round(low.XMin, 3), round(low.XMax, 3)) == (0, 18)
    assert (round(low.YMin, 3), round(low.YMax, 3)) == (0, 400)
    assert (round(low.ZMin, 3), round(low.ZMax, 3)) == (18, 702)
    assert stale_or_invalid(document) == []


def test_avant_tourne_d_un_quart_de_tour(document: Any) -> None:
    anchor = anchor_part(document)
    furniture, _ = api.make_closed_carcass(anchor, front_turns=1, elements=ALL_ELEMENTS)
    assert [furniture.Width.Value, furniture.Depth.Value] == pytest.approx([400, 600])
    std = furniture.getParentGeoFeatureGroup()
    assert std.Placement.Rotation.Angle == pytest.approx(1.5707963, abs=1e-6)  # +90° autour de Z
    front = by_label(furniture)["Avant"]
    assert bounds(front, world=True)[0] == (582, 600)  # l'avant est le bord X = 600 de l'ancre
    assert bounds(front, world=True)[1] == (18, 382)
    assert bounds(anchor, world=True) == ((0, 600), (0, 400), (0, 18))
    assert stale_or_invalid(document) == []


# --- FC6 : ancre membre d'un ensemble ---------------------------------------------------------


def test_fc6_l_ancre_sort_de_son_ensemble_et_le_caisson_devient_un_sous_ensemble(
    bureau: Bureau,
) -> None:
    doc = bureau.doc
    doc.UndoMode = 1
    anchor = bureau.parts["P"]  # plateau, membre du bureau
    assert api.furniture_of(anchor) == bureau.furniture
    objects_before = {o.Name for o in doc.Objects}
    dims = dims_and_placement(anchor)
    doc.openTransaction("Fermer le caisson")
    furniture, notices = api.make_closed_carcass(
        anchor, role=api.ClosingRole.TOP, height=200, elements={api.ClosingElement.LEFT}
    )
    doc.commitTransaction()
    assert notices == ()
    assert api.furniture_of(furniture) == bureau.furniture  # sous-ensemble du bureau
    assert api.furniture_of(anchor) == furniture  # l'ancre en est membre, plus du bureau
    assert dims_and_placement(anchor) == dims  # même cotes, même place dans le document
    assert stale_or_invalid(doc) == []
    assert doc.UndoNames == ["Fermer le caisson"]
    doc.undo()  # une seule annulation remet tout
    assert {o.Name for o in doc.Objects} == objects_before
    assert api.furniture_of(anchor) == bureau.furniture
    doc.recompute()
    assert dims_and_placement(anchor) == dims
    assert stale_or_invalid(doc) == []


# --- FC10 : liste de débit et pièces ordinaires -----------------------------------------------


def test_fc10_liste_de_debit_et_pieces_lisibles_hors_de_l_atelier(document: Any) -> None:
    anchor = anchor_part(document)
    furniture, _ = api.make_closed_carcass(anchor)
    cut_list = api.cut_list_of(document)
    assert marks_of(cut_list) == {"Base", "Côté gauche", "Côté droit", "Dessus", "Fond"}
    assert sum(line.quantity for line in cut_list.lines) == 5
    for part in members(furniture):
        assert part.TypeId == "Part::FeaturePython"  # Part::Feature lisible partout
        assert part.isDerivedFrom("Part::Feature")
        assert part.Shape.isValid() and part.Shape.Solids
    for obj in document.Objects:
        if obj.Name.startswith(("WoodPart", "MachinedPart")):
            assert obj.Shape.isValid() and not obj.Shape.isNull()


# --- Refus avant toute création ---------------------------------------------------------------


def test_refus_de_plusieurs_pieces_ou_d_un_autre_objet(document: Any) -> None:
    from freecad.menuiserie.features.closing import anchor_blank

    first, second = anchor_part(document), anchor_part(document)
    for objects in ([], [first, second]):
        with pytest.raises(ValueError, match="une seule pièce"):
            anchor_blank(objects)
    other = document.addObject("Part::Box", "Boite")
    with pytest.raises(ValueError, match="pas une pièce de bois"):
        anchor_blank([other])


@pytest.mark.parametrize(
    ("values", "error", "message"),
    [
        ({"height": 30}, ValueError, "hauteur hors tout"),
        ({"thickness": 10}, ValueError, "12 mm pour des tourillons"),
        ({"material_id": "inconnu"}, ValueError, "matériau des côtés inconnu"),
        ({"couleur": "rouge"}, TypeError, "couleur"),
    ],
)
def test_refus_avant_toute_creation(
    document: Any, values: dict[str, Any], error: type[Exception], message: str
) -> None:
    anchor = anchor_part(document)
    names = [o.Name for o in document.Objects]
    with pytest.raises(error, match=message):
        api.make_closed_carcass(anchor, **values)
    assert [o.Name for o in document.Objects] == names
    assert api.furniture_of(anchor) is None


def test_refus_d_une_piece_dessinee(document: Any) -> None:
    from freecad.menuiserie.features.closing import anchor_blank

    shaped = api.make_shaped_part(curved_rail(document), "chene", mark="Dessinee")
    with pytest.raises(ValueError, match="pièce dessinée"):
        anchor_blank([shaped])


def test_refus_des_assemblages_impossibles_avant_creation(document: Any) -> None:
    anchor = anchor_part(document, (600, 400, 40))
    names = [o.Name for o in document.Objects]
    with pytest.raises(ValueError, match="trop profond"):
        api.make_closed_carcass(anchor, thickness=18, height=100)  # côtés de 42 mm sur 40 + 18
    assert [o.Name for o in document.Objects] == names


def test_params_et_mots_cles_ne_se_melangent_pas(document: Any) -> None:
    anchor = anchor_part(document)
    params = api.closing_params(anchor)
    with pytest.raises(TypeError, match="pas les deux"):
        api.make_closed_carcass(anchor, params, height=500)
    furniture, _ = api.make_closed_carcass(anchor, params)
    assert furniture.Height.Value == 720


def test_annuler_ne_laisse_rien(document: Any) -> None:
    document.UndoMode = 1
    anchor = anchor_part(document)
    before = {o.Name for o in document.Objects}
    document.openTransaction("Fermer le caisson")
    api.make_closed_carcass(anchor)
    document.abortTransaction()
    assert {o.Name for o in document.Objects} == before
    assert dims_and_placement(anchor)[:3] == (600, 400, 18)


def test_le_caisson_se_redimensionne_comme_tout_ensemble(document: Any) -> None:
    anchor = anchor_part(document)
    furniture, _ = api.make_closed_carcass(anchor)
    api.resize_furniture(furniture, height=500)
    pieces = by_label(furniture)
    assert bounds(pieces["Dessus"])[2] == (482, 500)
    assert bounds(pieces["Côté gauche"])[2] == (18, 482)
    assert stale_or_invalid(document) == []


# --- Ancre dans un Std Part de l'utilisateur, ancre usinée --------------------------------------


def test_ancre_dans_un_std_part_tourne(document: Any) -> None:
    container = document.addObject("App::Part", "Meuble")
    container.Placement = App.Placement(
        App.Vector(10, 20, 30), App.Rotation(App.Vector(0, 0, 1), 90)
    )
    anchor = anchor_part(document)
    container.addObject(anchor)
    anchor.Placement = App.Placement(App.Vector(5, 5, 0), App.Rotation())
    document.recompute()
    world = App.Placement(anchor.getGlobalPlacement())
    furniture, _ = api.make_closed_carcass(anchor)
    assert furniture.getParentGeoFeatureGroup().getParentGeoFeatureGroup() == container
    assert anchor.getGlobalPlacement().isSame(world, 1e-9)
    top = by_label(furniture)["Dessus"]
    shape = top.Shape.copy()
    shape.Placement = world.inverse().multiply(top.getGlobalPlacement())
    box = shape.BoundBox  # dans le repère de l'ancre : au-dessus des côtés, emprise de l'ancre
    assert (round(box.XMin, 3), round(box.XMax, 3)) == (0, 600)
    assert (round(box.ZMin, 3), round(box.ZMax, 3)) == (702, 720)
    assert stale_or_invalid(document) == []


def test_ancre_donnee_par_sa_piece_usinee(document: Any) -> None:
    anchor = anchor_part(document)
    other = api.make_wood_part(300, 100, 18, "cp-bouleau", mark="Autre", doc=document)
    other.Placement = App.Placement(App.Vector(0, 400, 0), App.Rotation())
    document.recompute()
    api.make_dowels(anchor, other)
    machined = api.machined_part_of(anchor)
    assert machined is not None
    chosen = api.closing_params(machined, elements=frozenset())
    assert chosen.anchor.length == 600  # les cotes sont celles de la brute
    furniture, notices = api.make_closed_carcass(machined, chosen)
    assert api.furniture_of(anchor) == furniture
    # Voisine libre assemblée à l'ancre : liens globaux (ADR 0054), elle n'entre ni dans
    # l'ensemble ni dans son Std Part, et n'est plus signalée.
    assert api.furniture_of(other) is None
    assert other.getParentGeoFeatureGroup() is None
    assert notices == ()
    assert stale_or_invalid(document) == []


# --- Sens et avant par défaut -------------------------------------------------------------------


def test_sens_par_defaut_selon_la_face_ou_l_epaisseur(document: Any) -> None:
    from freecad.menuiserie.features.closing import default_front_turns, default_role

    anchor = anchor_part(document)
    assert default_role(anchor) is api.ClosingRole.BOTTOM  # épaisseur verticale vers le haut
    assert default_role(anchor, "Face6") is api.ClosingRole.BOTTOM  # face du dessus (z = 18)
    assert default_role(anchor, "Face5") is api.ClosingRole.TOP  # face du dessous (z = 0)
    assert default_role(anchor, "Face1") is api.ClosingRole.BOTTOM  # chant : règle par défaut
    anchor.Placement = App.Placement(App.Vector(0, 0, 0), App.Rotation(X_AXIS, 180))
    document.recompute()
    assert default_role(anchor) is api.ClosingRole.TOP  # épaisseur vers le bas : le dessus
    assert (
        default_role(anchor, "Face6") is api.ClosingRole.BOTTOM
    )  # sa face z = 18 regarde vers le bas
    # Observateur côté +Y (anchor retourné autour de X : son Y local regarde vers -Y)
    turns = default_front_turns(anchor, (300.0, 100000.0, 50.0))
    assert turns in (0, 2)  # un grand chant (longueur de 600), jamais un petit


def test_avant_le_plus_proche_de_la_camera(document: Any) -> None:
    from freecad.menuiserie.features.closing import default_front_turns

    anchor = anchor_part(document)
    assert default_front_turns(anchor, (300, -100000, 500)) == 0  # caméra devant (Y < 0)
    assert default_front_turns(anchor, (300, 100000, 500)) == 2
    assert (
        default_front_turns(anchor, (100000, 200, 500)) == 0
    )  # petit chant : grand chant le plus proche
