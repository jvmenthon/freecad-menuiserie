# SPDX-License-Identifier: LGPL-2.1-or-later
"""Membres d'un ensemble : ajout, retrait, refus, « Relier », sous-ensembles (J4b', N8, N11)."""

from __future__ import annotations

from typing import Any

import pytest

from tests.integration.bureau import EXPRESSIONS, LAYOUT, Bureau, build_parts
from tests.integration.cadre import stale_or_invalid

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
api = pytest.importorskip("freecad.menuiserie.api")

MEMBER_PROPERTIES = {
    "Furniture",
    "PositionMode",
    "FixedLeft",
    "FixedRight",
    "FixedFront",
    "FixedBack",
    "FixedBottom",
    "FixedTop",
    "FurnitureBindings",
}


def snapshot(bureau: Bureau) -> dict[str, Any]:
    """Propriétés et expressions de l'ensemble et de ses pièces, boîtes des pièces."""
    objects = {"F": bureau.furniture, **bureau.parts}
    result: dict[str, Any] = {
        name: (sorted(obj.PropertiesList), list(obj.ExpressionEngine))
        for name, obj in objects.items()
    }
    result["boxes"] = [str(part.Shape.BoundBox) for part in bureau.parts.values()]
    return result


# --- N8 : ajout et retrait ------------------------------------------------------------------


def test_ajout_sans_toucher_aux_membres_presents(document: Any) -> None:
    bureau = build_parts(document)
    furniture, _ = api.make_furniture([bureau.parts[m] for m in ("P", "JG", "JD")], "Bureau")
    api.set_member_options(bureau.parts["JG"], fixed={"Back": False})
    joue = bureau.expressions("JG")
    assert api.add_to_furniture(furniture, [bureau.parts["V"]]) == ()
    assert bureau.expressions("JG") == joue
    assert bureau.parts["JG"].FixedBack is False
    assert bureau.expressions("V") == EXPRESSIONS["V"]
    assert api.furniture_of(bureau.parts["V"]) == furniture


def test_retrait_des_seules_liaisons_de_l_atelier(document: Any) -> None:
    bureau = build_parts(document)
    names = set(bureau.parts["P"].PropertiesList)
    furniture, _ = api.make_furniture(list(bureau.parts.values()), "Bureau")
    plateau = bureau.parts["P"]
    plateau.setExpression("Thickness", "<<Bureau>>.Height / 25")
    document.recompute()
    before = (str(plateau.Shape.BoundBox), plateau.Shape.Volume)
    api.remove_from_furniture([plateau])
    assert set(plateau.PropertiesList) == names
    assert bureau.expressions("P") == {"Thickness": "<<Bureau>>.Height / 25"}
    assert (str(plateau.Shape.BoundBox), plateau.Shape.Volume) == before
    assert api.furniture_of(plateau) is None
    furniture.Depth = 800
    document.recompute()
    assert bureau.sizes("P") == (1200, 600, 30)
    with pytest.raises(ValueError, match="« Plateau » n'est membre d'aucun ensemble"):
        api.remove_from_furniture([bureau.parts["JG"], plateau])
    assert api.furniture_of(bureau.parts["JG"]) == furniture


def test_refus_avant_modification(bureau: Bureau, document: Any) -> None:
    before = snapshot(bureau)
    other = App.newDocument("TestPieceDeBoisAutre")
    try:
        stranger = api.make_wood_part(doc=other)
        with pytest.raises(ValueError, match="appartient à un autre document"):
            api.add_to_furniture(bureau.furniture, [stranger])
    finally:
        App.closeDocument(other.Name)
    box = document.addObject("Part::Box", "Boite")
    with pytest.raises(TypeError, match="« Boite » n'est ni une pièce de bois"):
        api.add_to_furniture(bureau.furniture, [box])
    with pytest.raises(ValueError, match="« Plateau » est déjà membre de l'ensemble « Bureau »"):
        api.make_furniture([bureau.parts["P"]])
    part = document.addObject("App::Part", "Conteneur")
    loose = api.make_wood_part(doc=document)
    part.addObject(loose)
    with pytest.raises(ValueError, match="n'est pas dans le même conteneur"):
        api.add_to_furniture(bureau.furniture, [loose])
    with pytest.raises(ValueError, match="Choisissez au moins une pièce"):
        api.make_furniture([])
    with pytest.raises(ValueError, match="Libellé d'ensemble inutilisable"):
        api.make_furniture([loose], label="a>b")
    with pytest.raises(ValueError, match="Mode de position inconnu"):
        api.set_member_options(bureau.parts["P"], mode="Fixed")
    with pytest.raises(ValueError, match="Option « fixe » inconnue"):
        api.set_member_options(bureau.parts["P"], fixed={"Middle": True})
    assert snapshot(bureau) == before
    assert len([o for o in document.Objects if o.Name.startswith("Furniture")]) == 1


def test_relier_garde_les_options(bureau: Bureau) -> None:
    joue = bureau.parts["JG"]
    joue.FixedBack = False
    joue.setExpression("Width", None)  # liaison effacée : remise par « Relier »
    bureau.parts["P"].setExpression("Width", None)
    bureau.parts["P"].Width = 650  # pièce retouchée à la main (R3)
    bureau.doc.recompute()
    assert api.rebind_furniture(bureau.furniture) == ()
    assert joue.FixedBack is False
    assert "Width" not in bureau.expressions("JG")
    assert bureau.expressions("P")["Width"] == "<<Bureau>>.Depth + 50 mm"
    assert stale_or_invalid(bureau.doc) == []


# --- N11 : sous-ensemble ------------------------------------------------------------------------


def caisson(document: Any) -> tuple[Any, dict[str, Any]]:
    """Caisson 400 x 560 x 300 posé sous le plateau du bureau, en retrait de 40 mm à
    l'arrière : deux côtés debout (x de 40 à 58 et de 422 à 440) et un dessous entre eux, en
    retrait de 20 mm à l'avant."""
    turn = App.Rotation(App.Vector(0, 1, 0), 90)  # L selon -Z, e selon +X
    pieces = {
        "CG": ((300, 560, 18), (40, 0, 700), turn),
        "CD": ((300, 560, 18), (422, 0, 700), turn),
        "CB": ((364, 540, 18), (58, 20, 400), App.Rotation()),
    }
    parts = {}
    for mark, (size, base, rotation) in pieces.items():
        part = api.make_wood_part(*size, "chene", mark=mark, doc=document)
        part.Label = mark
        part.Placement = App.Placement(App.Vector(*base), rotation)
        parts[mark] = part
    document.recompute()
    furniture, _ = api.make_furniture(list(parts.values()), label="Caisson")
    return furniture, parts


def engine(obj: Any) -> dict[str, str]:
    return {path.lstrip("."): text for path, text in obj.ExpressionEngine}


def test_sous_ensemble_qui_suit_le_bureau(document: Any) -> None:
    bureau = build_parts(document)
    sub, parts = caisson(document)
    assert [sub.Width.Value, sub.Depth.Value, sub.Height.Value] == pytest.approx([400, 560, 300])
    assert tuple(sub.Origin) == pytest.approx((40, 0, 400))
    desk = [bureau.parts[mark] for mark in ("P", "JG", "JD")]
    furniture, notices = api.make_furniture([*desk, sub], label="Bureau")
    assert notices == ()
    assert sub.Furniture == furniture
    assert engine(sub)["Depth"] == "<<Bureau>>.Depth - 40 mm"
    assert engine(sub)["Width"] == "<<Bureau>>.Width - 800 mm"
    # Membres d'un sous-ensemble (nested) : toutes leurs positions suivent son Origin.
    assert engine(parts["CD"]) == {
        "Placement.Base.x": "<<Caisson>>.Origin.x + <<Caisson>>.Width - 18 mm",
        "Placement.Base.y": "<<Caisson>>.Origin.y",
        "Placement.Base.z": "<<Caisson>>.Origin.z + <<Caisson>>.Height",
        "Length": "<<Caisson>>.Height",
        "Width": "<<Caisson>>.Depth",
    }
    furniture.Depth = 800
    document.recompute()
    assert sub.Depth.Value == pytest.approx(760)
    assert parts["CB"].Width.Value == pytest.approx(740)
    assert parts["CD"].Shape.BoundBox.YMax == pytest.approx(760)
    furniture.Width = 1400
    document.recompute()
    assert sub.Width.Value == pytest.approx(600)
    assert parts["CD"].Shape.BoundBox.XMax == pytest.approx(640)
    assert parts["CB"].Length.Value == pytest.approx(564)
    assert stale_or_invalid(document) == []


def test_controle_dans_les_sous_ensembles(document: Any) -> None:
    bureau = build_parts(document)
    sub, _ = caisson(document)
    furniture, _ = api.make_furniture([bureau.parts["P"], sub], label="Bureau")
    # Le caisson garderait 20,05 mm de profondeur, son dessous 0,05 mm de largeur.
    with pytest.raises(ValueError, match="« CB » deviendrait trop petite : Width = 0,05 mm"):
        api.resize_furniture(furniture, depth=60.05)
    assert furniture.Depth.Value == 600
    api.resize_furniture(furniture, depth=60.2)
    assert stale_or_invalid(document) == []


def test_cycle_d_ensembles_refuse(document: Any) -> None:
    bureau = build_parts(document)
    sub, _ = caisson(document)
    furniture, _ = api.make_furniture([*bureau.parts.values(), sub], label="Bureau")
    with pytest.raises(ValueError, match="déjà membre"):
        api.add_to_furniture(furniture, [sub])
    api.remove_from_furniture([sub])
    api.add_to_furniture(furniture, [sub])
    loose = api.make_wood_part(doc=document)
    outer, _ = api.make_furniture([loose], label="Meuble")
    with pytest.raises(ValueError, match="« Bureau » ne peut pas entrer dans « Caisson »"):
        api.add_to_furniture(sub, [furniture])
    api.add_to_furniture(outer, [furniture])
    with pytest.raises(ValueError, match="un ensemble ne peut pas être membre de lui-même"):
        api.add_to_furniture(sub, [outer])
    assert [m for m in LAYOUT if api.furniture_of(bureau.parts[m]) != furniture] == []
