# SPDX-License-Identifier: LGPL-2.1-or-later
"""« Fermer le caisson » (ADR 0064) : passe du testeur, cas limites dans un vrai document.

Valeurs limites (hauteur, épaisseurs), éléments tous décochés, ancre tournée ou retournée,
sauvegarde puis réouverture, annuler et rétablir, recalcul après modification, refus sans trace.
"""

from __future__ import annotations

from typing import Any

import pytest

from tests.integration.cadre import stale_or_invalid
from tests.integration.test_fermer_caisson import (
    X_AXIS,
    anchor_part,
    bounds,
    by_label,
    dims_and_placement,
    members,
)

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
api = pytest.importorskip("freecad.menuiserie.api")

JOINT_PREFIXES = ("Dowels", "Rabbet", "Miter", "TongueGroove", "Dovetail")


def signature(furniture: Any) -> dict[str, tuple[Any, ...]]:
    """Libellé → (cotes et place dans le document, étendue dans le document) de chaque membre."""
    return {
        str(o.Label): (*dims_and_placement(o), bounds(o, world=True)) for o in members(furniture)
    }


def object_names(doc: Any) -> set[str]:
    return {o.Name for o in doc.Objects}


def joint_names(doc: Any) -> list[str]:
    return sorted(o.Name for o in doc.Objects if o.Name.startswith(JOINT_PREFIXES))


def closed_carcass(doc: Any) -> Any:
    """L'unique ensemble « ClosedCarcass » du document."""
    found = [o for o in doc.Objects if getattr(o, "Template", "") == "ClosedCarcass"]
    assert len(found) == 1
    return found[0]


# --- Valeurs limites ----------------------------------------------------------------------------


def test_hauteur_minimale_acceptee_et_juste_en_dessous_refusee(document: Any) -> None:
    anchor = anchor_part(document)
    before = object_names(document)
    with pytest.raises(ValueError, match="hauteur hors tout"):
        api.make_closed_carcass(anchor, height=36.999)  # ancre 18 + dessus 18 + 1 mm d'intérieur
    assert object_names(document) == before  # refus sans aucune trace
    furniture, _ = api.make_closed_carcass(anchor, height=37, joinery=api.ClosingJoinery.NONE)
    assert bounds(by_label(furniture)["Côté gauche"])[2] == (18, 19)
    assert stale_or_invalid(document) == []
    assert all(o.Shape.isValid() for o in members(furniture))


@pytest.mark.parametrize("height", [0, -5, float("nan"), float("inf"), 1e12])
def test_hauteurs_invalides_refusees_sans_trace(document: Any, height: float) -> None:
    anchor = anchor_part(document)
    before = object_names(document)
    with pytest.raises(ValueError, match="hauteur hors tout"):
        api.make_closed_carcass(anchor, height=height)
    assert object_names(document) == before


@pytest.mark.parametrize("thickness", [0, -3, 200, 250])
def test_epaisseur_des_cotes_hors_bornes_refusee(document: Any, thickness: float) -> None:
    anchor = anchor_part(document)
    before = object_names(document)
    with pytest.raises(ValueError, match="épaisseur des côtés"):
        api.make_closed_carcass(anchor, thickness=thickness)
    assert object_names(document) == before


def test_epaisseur_des_cotes_juste_sous_la_moitie_de_la_plus_petite_cote(document: Any) -> None:
    anchor = anchor_part(document)
    furniture, _ = api.make_closed_carcass(
        anchor, thickness=199.9, joinery=api.ClosingJoinery.NONE, height=1000
    )
    assert bounds(by_label(furniture)["Côté gauche"])[0] == (0, 199.9)
    assert stale_or_invalid(document) == []
    assert all(o.Shape.isValid() for o in members(furniture))


def test_epaisseurs_minces_sans_assemblage(document: Any) -> None:
    anchor = anchor_part(document, (600, 400, 3))
    furniture, _ = api.make_closed_carcass(anchor, joinery=api.ClosingJoinery.NONE, height=300)
    assert bounds(by_label(furniture)["Dessus"])[2] == (297, 300)
    assert stale_or_invalid(document) == []
    assert all(o.Shape.isValid() for o in members(furniture))


def test_tourillons_refuses_sur_une_ancre_mince_sans_trace(document: Any) -> None:
    anchor = anchor_part(document, (600, 400, 10))
    before = object_names(document)
    with pytest.raises(ValueError, match="tourillons"):
        api.make_closed_carcass(anchor)
    assert object_names(document) == before


def test_materiau_inconnu_refuse_sans_trace(document: Any) -> None:
    anchor = anchor_part(document)
    before = object_names(document)
    with pytest.raises(ValueError, match="matériau"):
        api.make_closed_carcass(anchor, material_id="essence-imaginaire")
    assert object_names(document) == before


def test_tous_les_elements_decoches(document: Any) -> None:
    """Seule l'ancre reste : l'ensemble est valide, sans pièce ni assemblage de plus."""
    anchor = anchor_part(document)
    before = dims_and_placement(anchor)
    furniture, _ = api.make_closed_carcass(anchor, elements=frozenset())
    assert sorted(by_label(furniture)) == ["Base"]
    assert dims_and_placement(anchor) == before
    assert joint_names(document) == []
    assert stale_or_invalid(document) == []


# --- Ancre tournée, retournée, inclinée --------------------------------------------------------


@pytest.mark.parametrize(
    ("axis", "degrees"),
    [((0, 0, 1), 30), ((0, 0, 1), 90), ((1, 0, 0), 180), ((0, 1, 0), 90), ((1, 1, 0), 45)],
)
def test_caisson_dans_le_repere_d_une_ancre_tournee(
    document: Any, axis: tuple[float, float, float], degrees: float
) -> None:
    """Quelle que soit la rotation, les pièces gardent leur place relative à l'ancre."""
    anchor = anchor_part(document)
    anchor.Placement = App.Placement(
        App.Vector(100, -50, 30), App.Rotation(App.Vector(*axis), degrees)
    )
    document.recompute()
    before = dims_and_placement(anchor)
    furniture, _ = api.make_closed_carcass(anchor, role=api.ClosingRole.BOTTOM)
    pieces = by_label(furniture)
    assert dims_and_placement(anchor) == before
    frame = anchor.getGlobalPlacement()
    expected = {
        "Côté gauche": ((0, 18), (0, 400), (18, 702)),
        "Côté droit": ((582, 600), (0, 400), (18, 702)),
        "Dessus": ((0, 600), (0, 400), (702, 720)),
    }
    for label, wanted in expected.items():
        shape = pieces[label].Shape.copy()
        shape.Placement = frame.inverse().multiply(pieces[label].getGlobalPlacement())
        box = shape.BoundBox
        found = ((box.XMin, box.XMax), (box.YMin, box.YMax), (box.ZMin, box.ZMax))
        for got, want in zip(found, wanted, strict=True):
            assert got == pytest.approx(want, abs=1e-3), label
    assert stale_or_invalid(document) == []


def test_ancre_retournee_le_caisson_monte_dans_le_document(document: Any) -> None:
    """Ancre retournée (épaisseur vers -Z) : sans face choisie, elle est prise pour le dessus et
    le caisson part de son plan vers +Z du document."""
    from freecad.menuiserie.features.closing import default_role

    anchor = anchor_part(document)
    anchor.Placement = App.Placement(App.Vector(0, 0, 18), App.Rotation(X_AXIS, 180))
    document.recompute()
    role = default_role(anchor)
    assert role is api.ClosingRole.TOP
    furniture, _ = api.make_closed_carcass(anchor, role=role)
    assert bounds(by_label(furniture)["Dessous"], world=True)[2][0] >= 0
    assert stale_or_invalid(document) == []


# --- Sauvegarde, réouverture ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "options",
    [
        {},
        {"joinery": "Miter"},
        {"role": "top", "elements": {"left", "right", "front", "back", "opposite"}},
        {"thick_back": True, "back_joinery": "None", "joinery": "Rabbet"},
        {"back_joinery": "Groove", "joinery": "Dovetail"},
    ],
)
def test_sauvegarde_puis_reouverture(document: Any, rouvrir: Any, options: dict[str, Any]) -> None:
    anchor = anchor_part(document)
    anchor.Placement = App.Placement(App.Vector(10, 20, 30), App.Rotation(App.Vector(0, 0, 1), 90))
    document.recompute()
    kinds = {
        "role": api.ClosingRole,
        "joinery": api.ClosingJoinery,
        "back_joinery": api.BackJoinery,
    }
    values = {k: kinds[k](v) if k in kinds else v for k, v in options.items()}
    if "elements" in values:
        values["elements"] = {api.ClosingElement(e) for e in values["elements"]}
    expected = signature(api.make_closed_carcass(anchor, **values)[0])
    joints = joint_names(document)
    reopened = rouvrir(document)
    reopened.recompute()
    found = closed_carcass(reopened)
    assert signature(found) == expected
    assert joint_names(reopened) == joints
    assert stale_or_invalid(reopened) == []
    api.resize_furniture(found, height=500)  # l'ensemble rouvert reste pilotable
    assert stale_or_invalid(reopened) == []


# --- Annuler, rétablir ----------------------------------------------------------------------------


def test_annuler_puis_retablir_deux_fois(document: Any) -> None:
    document.UndoMode = 1
    anchor = anchor_part(document)
    before_names = object_names(document)
    before_anchor = dims_and_placement(anchor)
    document.openTransaction("Fermer le caisson")
    furniture, _ = api.make_closed_carcass(anchor, joinery=api.ClosingJoinery.MITER)
    document.commitTransaction()
    after_names = object_names(document)
    expected = signature(furniture)
    for _round in range(2):
        document.undo()
        assert object_names(document) == before_names
        assert dims_and_placement(anchor) == before_anchor
        assert api.furniture_of(anchor) is None
        document.recompute()
        assert stale_or_invalid(document) == []
        document.redo()
        assert object_names(document) == after_names
        document.recompute()
        assert signature(closed_carcass(document)) == expected
        assert stale_or_invalid(document) == []


def test_annuler_rend_l_ancre_a_son_volume_d_origine(document: Any) -> None:
    """L'onglet coupe la pièce usinée de l'ancre : l'annulation la supprime, la brute reste."""
    document.UndoMode = 1
    anchor = anchor_part(document)
    volume = anchor.Shape.Volume
    document.openTransaction("Fermer le caisson")
    api.make_closed_carcass(anchor, joinery=api.ClosingJoinery.MITER)
    document.commitTransaction()
    document.undo()
    document.recompute()
    assert anchor.Shape.Volume == pytest.approx(volume)
    assert api.machined_part_of(anchor) is None


# --- Recalcul après modification ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "value"), [("Width", 800), ("Depth", 500), ("Height", 400), ("Height", 1500)]
)
def test_modifier_une_dimension_de_l_ensemble_recalcule_les_pieces(
    document: Any, name: str, value: float
) -> None:
    anchor = anchor_part(document)
    furniture, _ = api.make_closed_carcass(anchor)
    api.resize_furniture(furniture, **{name.lower(): value})
    assert getattr(furniture, name).Value == pytest.approx(value)
    axis = {"Width": 0, "Depth": 1, "Height": 2}[name]
    assert bounds(by_label(furniture)["Dessus"])[axis][1] == pytest.approx(value)
    assert stale_or_invalid(document) == []
    assert all(o.Shape.isValid() for o in members(furniture))


def test_modifier_l_epaisseur_d_un_cote_apres_coup(document: Any) -> None:
    anchor = anchor_part(document)
    furniture, _ = api.make_closed_carcass(anchor)
    left = by_label(furniture)["Côté gauche"]
    left.Thickness = 25
    document.recompute()
    assert stale_or_invalid(document) == []
    assert left.Shape.isValid()
    assert dims_and_placement(anchor)[:3] == (600, 400, 18)  # l'ancre n'a pas bougé


# --- Ancre déjà assemblée ---------------------------------------------------------------------


def test_ancre_deja_assemblee_a_une_piece_libre(document: Any) -> None:
    """Une ancre déjà assemblée à une pièce libre reste intacte et garde son assemblage."""
    anchor = anchor_part(document)
    other = api.make_wood_part(600, 100, 18, "cp-bouleau", mark="Traverse", doc=document)
    other.Placement = App.Placement(App.Vector(0, 400, 0), App.Rotation())
    document.recompute()
    api.make_dowels(other, anchor)
    document.recompute()
    before = dims_and_placement(anchor)
    joints = len(joint_names(document))
    furniture, _ = api.make_closed_carcass(anchor)
    assert dims_and_placement(anchor) == before
    assert len(joint_names(document)) >= joints
    assert stale_or_invalid(document) == []
    assert api.furniture_of(anchor) == furniture
