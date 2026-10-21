# SPDX-License-Identifier: LGPL-2.1-or-later
"""Gabarit « Caisson » dans le document (J4d, critères K3 à K5 de ``docs/specs/J4-ensembles.md``).

Création en un recalcul, suivi des cotes, sous-ensemble du bureau, une seule entrée
d'annulation, refus avant création, redimensionnements successifs, réouverture.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from freecad.menuiserie.core.geometry import Vec3
from tests.integration.bureau import Bureau
from tests.integration.cadre import stale_or_invalid

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
api = pytest.importorskip("freecad.menuiserie.api")

EDGES = ("Left", "Right", "Front", "Back", "Bottom", "Top")
KEYS = {  # libellé → clé du gabarit
    "Côté gauche": "left",
    "Côté droit": "right",
    "Dessous": "bottom",
    "Dessus": "top",
    "Fond": "back",
    "Étagère": "shelf",
}
FIXED = {  # K1 : options explicites du gabarit
    "left": {"Left", "Front", "Back", "Bottom", "Top"},
    "right": {"Right", "Front", "Back", "Bottom", "Top"},
    "bottom": {"Left", "Right", "Front", "Back", "Bottom"},
    "top": {"Left", "Right", "Front", "Back", "Top"},
    "back": {"Left", "Right", "Back", "Bottom", "Top"},
    "shelf": {"Left", "Right", "Front", "Back"},
}
BOUNDS = {  # K1 : étendues (X, Y, Z) du caisson de référence
    "left": ((0, 18), (0, 400), (0, 720)),
    "right": ((582, 600), (0, 400), (0, 720)),
    "bottom": ((18, 582), (0, 400), (0, 18)),
    "top": ((18, 582), (0, 400), (702, 720)),
    "back": ((8, 592), (392, 400), (8, 712)),
    "shelf": ((19, 581), (0, 391), (351, 369)),
}


@dataclass
class Caisson:
    """Ensemble créé par le gabarit et ses objets, par clé."""

    doc: Any
    furniture: Any
    notices: tuple[str, ...]

    def members(self) -> list[Any]:
        return [o for o in self.furniture.InList if getattr(o, "Furniture", None) == self.furniture]

    @property
    def parts(self) -> dict[str, Any]:
        return {key_of(str(o.Label)): o for o in self.members()}

    def objects(self, name: str) -> list[Any]:
        """Objets du document dont le nom interne commence par ``name``."""
        return [o for o in self.doc.Objects if o.Name.startswith(name)]

    def bounds(self, key: str) -> tuple[tuple[float, float], ...]:
        box = self.parts[key].Shape.BoundBox
        return tuple(
            (round(lo, 3), round(hi, 3))
            for lo, hi in ((box.XMin, box.XMax), (box.YMin, box.YMax), (box.ZMin, box.ZMax))
        )

    def dowel_counts(self) -> list[int]:
        return [len(joint.Shape.Solids) for joint in self.objects("Dowels")]


def key_of(label: str) -> str:
    """Clé du gabarit d'après le libellé (« Étagère001 » : FreeCAD rend les libellés uniques)."""
    return "shelf" if label.startswith("Étagère") else KEYS[label]


def make(doc: Any, **values: Any) -> Caisson:
    furniture, notices = api.make_carcass(doc, **values)
    return Caisson(doc, furniture, notices)


def fixed(part: Any) -> set[str]:
    return {edge for edge in EDGES if getattr(part, f"Fixed{edge}")}


def engine(obj: Any) -> dict[str, str]:
    return {path.lstrip("."): text for path, text in obj.ExpressionEngine}


# --- K3 : création ---------------------------------------------------------------------------


def test_creation_du_caisson_de_reference(document: Any) -> None:
    caisson = make(document)
    furniture = caisson.furniture
    assert (furniture.Name, furniture.Label, furniture.Template) == (
        "Furniture",
        "Caisson",
        "Carcass",
    )
    sizes = [furniture.Width.Value, furniture.Depth.Value, furniture.Height.Value]
    assert sizes == pytest.approx([600, 400, 720])
    assert caisson.notices == ()
    assert sorted(caisson.parts) == sorted(FIXED)
    assert len(caisson.objects("WoodPart")) == 6
    assert len(caisson.objects("Rabbet")) == 4
    assert caisson.dowel_counts() == [4, 4, 4, 4]
    machined = {api.blank_of(o).Label for o in caisson.objects("MachinedPart")}
    assert machined == set(KEYS) - {"Étagère"}  # l'étagère reste une brute
    for key, part in caisson.parts.items():
        assert fixed(part) == FIXED[key], key
        assert part.PositionMode == "Stay", key
        assert dict(part.FurnitureBindings) == engine(part), key
        assert part.MaterialId == "cp-bouleau", key
        assert caisson.bounds(key) == BOUNDS[key], key
    assert engine(caisson.parts["back"])["Placement.Base.y"] == (
        "<<Caisson>>.Origin.y + <<Caisson>>.Depth - 8 mm"
    )
    assert stale_or_invalid(document) == []


def test_aucun_objet_gabarit_garde(document: Any) -> None:
    """ADR 0010 : seulement des pièces, des pièces usinées, des assemblages et l'ensemble."""
    caisson = make(document, shelf_count=2, joinery="None")
    types = {o.Proxy.TYPE for o in document.Objects}
    assert types == {
        "Menuiserie::WoodPart",
        "Menuiserie::MachinedPart",
        "Menuiserie::Rabbet",
        "Menuiserie::Furniture",
    }
    assert caisson.dowel_counts() == []
    assert len(caisson.parts) == 6  # les deux étagères ont le même libellé de départ
    assert len(caisson.objects("WoodPart")) == 7


# --- K4 : le caisson suit ses cotes ----------------------------------------------------------


def test_profondeur_500(document: Any) -> None:
    caisson = make(document)
    api.resize_furniture(caisson.furniture, depth=500)
    for key in ("left", "right", "bottom", "top"):
        assert caisson.bounds(key)[1] == (0, 500), key
    assert caisson.bounds("back")[1] == (492, 500)
    assert caisson.bounds("shelf")[1] == (0, 491)
    assert caisson.dowel_counts() == [5, 5, 5, 5]
    assert stale_or_invalid(document) == []


@pytest.mark.parametrize(("mode", "shelf"), [("Stay", (351, 369)), ("Proportional", (391, 409))])
def test_hauteur_800(document: Any, mode: str, shelf: tuple[float, float]) -> None:
    caisson = make(document)
    api.set_member_options(caisson.parts["shelf"], mode=mode)
    api.resize_furniture(caisson.furniture, height=800)
    assert caisson.bounds("left")[2] == (0, 800)
    assert caisson.bounds("top")[2] == (782, 800)
    assert caisson.bounds("back")[2] == (8, 792)
    assert caisson.bounds("shelf")[2] == shelf
    assert stale_or_invalid(document) == []


def test_cotes_changees_plusieurs_fois_restent_valides(document: Any) -> None:
    """Le caisson change de cotes (API, puis éditeur de propriétés) et reste valide."""
    caisson = make(document, shelf_count=2)
    furniture = caisson.furniture
    for sizes in ({"width": 900}, {"depth": 300, "height": 1000}, {"width": 450}):
        api.resize_furniture(furniture, **sizes)
        assert stale_or_invalid(document) == [], sizes
    furniture.Width = 1200  # éditeur de propriétés (Q4 : appliqué)
    document.recompute()
    assert stale_or_invalid(document) == []
    assert caisson.bounds("right")[0] == (1182, 1200)
    assert caisson.bounds("top")[0] == (18, 1182)
    assert caisson.bounds("back") == ((8, 1192), (292, 300), (8, 992))
    assert caisson.dowel_counts() == [4, 4, 4, 4]  # contact de 300 mm


# --- K5 : sous-ensemble du bureau ------------------------------------------------------------


def test_caisson_sous_ensemble_du_bureau(bureau: Bureau) -> None:
    doc = bureau.doc
    furniture, notices = api.make_carcass(
        doc, width=400, depth=400, height=300, origin=Vec3(40, 0, 0), furniture=bureau.furniture
    )
    assert notices == ()
    assert api.furniture_of(furniture) == bureau.furniture
    assert fixed(furniture) == set(EDGES)  # options par défaut (F3, Q7) vis-à-vis du bureau
    assert engine(furniture)["Depth"] == "<<Bureau>>.Depth - 200 mm"
    assert dict(furniture.FurnitureBindings) == engine(furniture)
    assert tuple(furniture.Origin) == pytest.approx((40, 0, 0))
    assert stale_or_invalid(doc) == []
    api.resize_furniture(bureau.furniture, depth=800)
    assert furniture.Depth.Value == pytest.approx(600)
    caisson = Caisson(doc, furniture, notices)
    assert caisson.bounds("left") == ((40, 58), (0, 600), (0, 300))
    assert caisson.bounds("back")[1] == (592, 600)
    assert bureau.bounds("V")[1] == (641, 659)
    assert stale_or_invalid(doc) == []


# --- Annuler, refus, réouverture ------------------------------------------------------------


def test_une_seule_entree_d_annulation(document: Any) -> None:
    document.UndoMode = 1
    document.openTransaction("Créer un caisson")
    make(document)
    document.commitTransaction()
    assert document.UndoNames == ["Créer un caisson"]
    count = len(document.Objects)
    document.undo()
    assert document.Objects == []
    document.redo()
    document.recompute()
    assert len(document.Objects) == count
    assert stale_or_invalid(document) == []


@pytest.mark.parametrize(
    ("values", "error", "message"),
    [
        ({"material_id": "inconnu"}, ValueError, "matériau des panneaux inconnu"),
        ({"thickness": 300}, ValueError, "épaisseur des panneaux = 300 mm"),
        ({"width": -1}, ValueError, "largeur"),
        ({"couleur": "rouge"}, TypeError, "couleur"),
    ],
)
def test_refus_avant_toute_creation(
    document: Any, values: dict[str, Any], error: type[Exception], message: str
) -> None:
    with pytest.raises(error, match=message):
        api.make_carcass(document, **values)
    assert document.Objects == []


def test_refus_d_un_parent_qui_n_est_pas_un_ensemble(document: Any) -> None:
    piece = api.make_wood_part(doc=document)
    with pytest.raises(TypeError, match="n'est pas un ensemble"):
        api.make_carcass(document, furniture=piece)
    assert [o.Name for o in document.Objects] == [piece.Name]
    with pytest.raises(TypeError, match="pas les deux"):
        api.make_carcass(document, api.CarcassParams(), width=800)


def test_reouverture(document: Any, rouvrir: Any) -> None:
    caisson = make(document)
    before = {key: engine(part) for key, part in caisson.parts.items()}
    reopened = rouvrir(document)
    furniture = reopened.getObject("Furniture")
    again = Caisson(reopened, furniture, ())
    assert furniture.Template == "Carcass"
    assert {key: engine(part) for key, part in again.parts.items()} == before
    assert stale_or_invalid(reopened) == []
