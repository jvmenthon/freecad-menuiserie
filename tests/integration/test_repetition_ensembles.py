# SPDX-License-Identifier: LGPL-2.1-or-later
"""Répétition et ensembles (lot R-b3, ADR 0043, ``docs/specs/repetition.md`` § 2 bis et § 3.4).

R12 copies membres d'un ensemble (options reprises, redimensionner ne casse rien), « Suivre le
redimensionnement » vrai et faux, R19 répéter un caisson (membres et assemblages copiés, le
caisson source redimensionné redimensionne la copie), R20 dissocier un ensemble copie, sélection
mixte et refus, annulation en un bloc, enregistrer et rouvrir.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

import pytest

from freecad.menuiserie.core.geometry import Vec3
from tests.integration.cadre import stale_or_invalid

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
api = pytest.importorskip("freecad.menuiserie.api")
repeat = pytest.importorskip("freecad.menuiserie.features.repeat")
container = pytest.importorskip("freecad.menuiserie.features.furniture_container")

Reopen = Callable[[Any], Any]
Y_AXIS = App.Vector(0, 1, 0)
OPTIONS = ("PositionMode", "FixedBottom", "FixedTop", "FixedLeft", "FixedRight", "Locked")
WORKSHOP = "FurnitureBindings"


def params(**values: Any) -> Any:
    """Deux copies tous les 150 mm sur Z, sauf réglage contraire."""
    return api.RepeatParams(**{"count": 2, "step": 150.0, "axis": "Z", **values})


def board(doc: Any, mark: str, size: Any, where: Any, rotation: Any = None) -> Any:
    part = api.make_wood_part(*size, "chene", mark=mark, doc=doc)
    part.Placement = App.Placement(App.Vector(*where), rotation or App.Rotation())
    return part


class Meuble:
    """Étagère entre deux côtés, un dessous et un dessus : un ensemble de 600 x 400 x 720."""

    def __init__(self, doc: Any) -> None:
        self.doc = doc
        side = App.Rotation(Y_AXIS, -90)
        self.left = board(doc, "Gauche", (720, 400, 18), (18, 0, 0), side)
        self.right = board(doc, "Droit", (720, 400, 18), (600, 0, 0), side)
        self.bottom = board(doc, "Dessous", (564, 400, 18), (18, 0, 0))
        self.top = board(doc, "Dessus", (564, 400, 18), (18, 0, 702))
        self.shelf = board(doc, "Etagere", (564, 380, 18), (18, 0, 200))
        doc.recompute()
        parts = [self.left, self.right, self.bottom, self.top, self.shelf]
        self.furniture, _ = api.make_furniture(parts, "Meuble")
        doc.recompute()

    def repeat(self, **values: Any) -> Any:
        return api.make_repeat([self.shelf], params(**values))


def corner(furniture: Any) -> tuple[float, float, float]:
    """Coin (avant, gauche, bas) de l'ensemble en coordonnées globales : le ``Placement`` de son
    Std Part (ADR 0038) appliqué à son ``Origin``."""
    std = container.std_part_of(furniture)
    base = std.getGlobalPlacement() if std is not None else App.Placement()
    point = base.multVec(furniture.Origin)
    return (round(point.x, 6), round(point.y, 6), round(point.z, 6))


def copies(rep: Any, src: Any = None) -> list[Any]:
    found: list[Any] = repeat.copies_of(rep, src)
    return found


def engine(obj: Any) -> dict[str, str]:
    return {path.lstrip("."): text for path, text in obj.ExpressionEngine}


def heights(rep: Any) -> list[float]:
    return [round(c.Placement.Base.z, 6) for c in copies(rep)]


def above(source: Any, *steps: float) -> list[float]:
    """Hauteurs de la source décalée de ``steps`` (pas fixe : les copies suivent la source)."""
    return [round(source.Placement.Base.z + step, 6) for step in steps]


@pytest.fixture
def undoable(document: Any) -> Any:
    document.UndoMode = 1
    return document


# --- R12 : source membre d'un ensemble ------------------------------------------------------


def test_les_copies_sont_membres_de_l_ensemble_avec_les_memes_options(document: Any) -> None:
    meuble = Meuble(document)
    api.set_member_options(meuble.shelf, mode="Proportional", fixed={"Top": True, "Bottom": False})
    api.set_member_options(meuble.shelf, locked=True)
    rep = meuble.repeat()
    for copy in copies(rep):
        assert api.furniture_of(copy) == meuble.furniture
        assert {name: getattr(copy, name) for name in OPTIONS} == {
            name: getattr(meuble.shelf, name) for name in OPTIONS
        }
        assert copy.getEditorMode("Furniture") == ["ReadOnly"]
    assert stale_or_invalid(document) == []


def test_les_liaisons_de_l_ensemble_n_ecrasent_pas_celles_de_la_repetition(document: Any) -> None:
    meuble = Meuble(document)
    rep = meuble.repeat()
    before = [engine(c) for c in copies(rep)]
    assert all(dict(c.FurnitureBindings) == {} for c in copies(rep))
    api.rebind_furniture(meuble.furniture)
    messages = api.set_member_options(meuble.shelf, fixed={"Front": False})
    messages += api.set_member_options(meuble.left, fixed={"Front": False})
    assert messages == ()  # aucun avertissement « formule de l'utilisateur » sur une copie
    assert [engine(c) for c in copies(rep)] == before
    assert all(dict(c.FurnitureBindings) == {} for c in copies(rep))
    api.resize_furniture(meuble.furniture, width=700, height=800)
    assert stale_or_invalid(document) == []
    assert heights(rep) == above(meuble.shelf, 150, 300)
    assert [c.Length.Value for c in copies(rep)] == [664.0, 664.0]


def test_redimensionner_l_ensemble_ne_casse_rien(document: Any) -> None:
    meuble = Meuble(document)
    rep = meuble.repeat()
    api.resize_furniture(meuble.furniture, width=700, depth=500, height=900)
    assert stale_or_invalid(document) == []
    for shelf in (meuble.shelf, *copies(rep)):
        assert (shelf.Length.Value, shelf.Width.Value) == (664.0, 480.0)
        assert shelf.Shape.isValid()
    assert heights(rep) == above(meuble.shelf, 150, 300)  # le pas est fixe
    assert round(meuble.top.Placement.Base.z, 6) == 882.0
    api.resize_furniture(meuble.furniture, width=560)
    assert [c.Length.Value for c in copies(rep)] == [524.0, 524.0]
    assert stale_or_invalid(document) == []


def test_une_copie_compte_comme_membre_pour_ses_voisines(document: Any) -> None:
    meuble = Meuble(document)
    rep = meuble.repeat(axis="X", step=10)  # recouvre le côté droit : voisines en vis-à-vis
    rep_copies = copies(rep)
    assert rep_copies
    api.resize_furniture(meuble.furniture, width=640)
    assert stale_or_invalid(document) == []
    api.rebind_furniture(meuble.furniture)
    document.recompute()
    assert stale_or_invalid(document) == []


# --- « Suivre le redimensionnement » (FollowResize) -------------------------------------------


def test_pas_fixe_par_defaut(document: Any) -> None:
    meuble = Meuble(document)
    rep = meuble.repeat()
    assert rep.FollowResize is False and "Step" not in engine(rep) and "Span" not in engine(rep)
    api.resize_furniture(meuble.furniture, height=900)
    assert rep.Step.Value == 150.0
    assert (rep.Count, len(copies(rep))) == (2, 2)


def test_le_pas_suit_la_cote_de_l_ensemble(document: Any) -> None:
    meuble = Meuble(document)
    rep = meuble.repeat(follow_resize=True)
    assert rep.FollowResize is True and rep.Spacing == "CountOnSpan" and rep.Count == 2
    name = meuble.furniture.Name  # les expressions citent l'ensemble par son nom interne
    assert engine(rep) == {"Span": f"{name}.Height - 402 mm", "Step": "(Span - 18 mm) / 2"}
    assert (rep.Span.Value, rep.Step.Value) == (318.0, 150.0)  # rien ne bouge à l'écriture
    assert heights(rep) == above(meuble.shelf, 150, 300)
    api.resize_furniture(meuble.furniture, height=900)
    assert (rep.Span.Value, rep.Step.Value) == (498.0, 240.0)
    assert heights(rep) == above(meuble.shelf, 240, 480)
    assert (rep.Count, len(copies(rep))) == (2, 2)  # le nombre ne change pas
    api.resize_furniture(meuble.furniture, height=600)
    assert rep.Step.Value == pytest.approx(90.0)
    assert heights(rep) == above(meuble.shelf, 90, 180)
    api.resize_furniture(meuble.furniture, width=800, depth=500)  # autres axes : pas inchangé
    assert rep.Step.Value == pytest.approx(90.0)
    assert stale_or_invalid(document) == []


def test_suivre_le_redimensionnement_sur_la_profondeur(document: Any) -> None:
    meuble = Meuble(document)
    rep = api.make_repeat(
        [meuble.shelf], api.RepeatParams(count=1, step=15, axis="Y", follow_resize=True)
    )
    assert engine(rep)["Span"] == f"{meuble.furniture.Name}.Depth - 5 mm"
    api.resize_furniture(meuble.furniture, depth=500)
    assert rep.Step.Value == pytest.approx(115.0)
    assert copies(rep)[0].Placement.Base.y == pytest.approx(meuble.shelf.Placement.Base.y + 115)


def test_basculer_le_suivi_avec_edit_repeat(undoable: Any) -> None:
    meuble = Meuble(undoable)
    rep = meuble.repeat()
    api.edit_repeat(rep, params(follow_resize=True))
    assert rep.FollowResize is True and set(engine(rep)) == {"Span", "Step"}
    api.resize_furniture(meuble.furniture, height=900)
    assert rep.Step.Value == 240.0
    api.edit_repeat(rep, params(step=rep.Step.Value))  # décoché : pas fixe, à sa valeur du moment
    assert rep.FollowResize is False and engine(rep) == {}
    assert rep.Step.Value == 240.0
    api.resize_furniture(meuble.furniture, height=1000)
    assert rep.Step.Value == 240.0
    assert heights(rep) == above(meuble.shelf, 240, 480)
    assert stale_or_invalid(undoable) == []


def test_suivi_refuse_sans_ensemble(document: Any) -> None:
    libre = board(document, "Libre", (300, 40, 22), (0, 0, 0))
    meuble = Meuble(document)
    document.recompute()
    count = len(document.Objects)
    with pytest.raises(ValueError, match=r"n'est membre d'aucun ensemble"):
        api.make_repeat([libre], params(follow_resize=True))
    with pytest.raises(ValueError, match=r"n'est membre d'aucun ensemble"):
        api.make_repeat([meuble.shelf, libre], params(follow_resize=True))
    assert len(document.Objects) == count
    rep = api.make_repeat([libre], params())
    with pytest.raises(ValueError, match=r"n'est membre d'aucun ensemble"):
        api.edit_repeat(rep, params(follow_resize=True))
    assert rep.FollowResize is False and len(copies(rep)) == 2


# --- R19 : répéter un caisson ---------------------------------------------------------------

MEMBER_LABELS = ["Côté droit", "Côté gauche", "Dessous", "Dessus", "Fond", "Étagère"]


def caisson(doc: Any, **values: Any) -> Any:
    """Caisson du gabarit (600 x 400 x 720, une étagère, tourillons et feuillures), recalculé."""
    furniture, _ = api.make_carcass(doc, **{"shelf_count": 1, **values})
    doc.recompute()
    return furniture


def caisson_with_inner(doc: Any) -> tuple[Any, Any]:
    """Caisson sans étagère et son sous-ensemble (200 x 300 x 200 en (100, 0, 100))."""
    source = caisson(doc, shelf_count=0)
    inner, _ = api.make_carcass(
        doc, width=200, depth=300, height=200, shelf_count=0, furniture=source,
        origin=Vec3(100, 0, 100),
    )  # fmt: skip
    doc.recompute()
    return source, inner


def row(**values: Any) -> Any:
    """Deux caissons de plus tous les 700 mm sur X, sauf réglage contraire."""
    return api.RepeatParams(**{"count": 2, "step": 700.0, "axis": "X", **values})


def members(furniture: Any) -> list[Any]:
    found = {o.Name: o for o in furniture.InList if getattr(o, "Furniture", None) == furniture}
    return sorted(found.values(), key=lambda o: o.Label)


def member(furniture: Any, label: str) -> Any:
    return next(m for m in members(furniture) if m.Label == label)


def joints(doc: Any) -> list[Any]:
    return [o for o in doc.Objects if hasattr(o, "HostPart")]


def bounds(part: Any) -> tuple[float, ...]:
    """Étendue de la pièce en coordonnées globales (le Std Part de son ensemble compris)."""
    shape = part.Shape.copy()
    shape.Placement = (
        part.getGlobalPlacement().multiply(part.Placement.inverse()).multiply(shape.Placement)
    )
    box = shape.BoundBox
    values = (box.XMin, box.XMax, box.YMin, box.YMax, box.ZMin, box.ZMax)
    return tuple(round(v, 3) for v in values)


def test_repeter_un_caisson_cree_des_ensembles_copies(document: Any) -> None:
    source = caisson(document)
    rep = api.make_repeat([source], row())
    first, second = copies(rep, source)
    assert [c.Label for c in (first, second)] == ["Caisson 2", "Caisson 3"]
    assert (first.RepeatIndex, second.RepeatIndex) == (1, 2)
    assert all(repeat.is_copy(c) and api.repeat_of(c) == rep for c in (first, second))
    for index, copy in enumerate((first, second), start=1):
        assert api.furniture_of(copy) is None  # le caisson source n'est dans aucun ensemble
        assert (copy.Width.Value, copy.Depth.Value, copy.Height.Value) == (600, 400, 720)
        assert corner(copy) == (700.0 * index, 0.0, 0.0)
        expressions = engine(copy)
        assert expressions["Width"] == f"{source.Name}.Width"
        assert (
            expressions["Origin.x"] == f"{source.Name}.Origin.x"
        )  # le décalage est dans le Std Part
        assert expressions["Origin.y"] == f"{source.Name}.Origin.y"
        std, std_source = container.std_part_of(copy), container.std_part_of(source)
        assert std is not None and std != std_source and std.Label == f"{copy.Label} (Std Part)"
        assert std.getParentGeoFeatureGroup() == std_source.getParentGeoFeatureGroup()
        placed = engine(std)
        assert placed["Placement.Base.x"].startswith(
            f"{std_source.Name}.Placement.Base.x + {index} *"
        )
        assert placed["Placement.Base.y"] == f"{std_source.Name}.Placement.Base.y"
        assert placed["Placement.Rotation"] == f"{std_source.Name}.Placement.Rotation"
        assert {m.getParentGeoFeatureGroup() for m in members(copy)} == {
            std
        }  # membres rangés dedans
        assert sorted(m.Label for m in members(copy)) == sorted(
            f"{n} {index + 1}" for n in MEMBER_LABELS
        )
        assert all(repeat.is_copy(m) and m.Repeat == rep for m in members(copy))
        assert copy.getEditorMode("RepeatIndex") == ["ReadOnly"]
    assert stale_or_invalid(document) == []
    assert not hasattr(rep, "Shape") and rep.Source == [source]


def test_les_membres_sont_copies_avec_leurs_options(document: Any) -> None:
    source = caisson(document)
    shelf = member(source, "Étagère")
    api.set_member_options(shelf, mode="Proportional", fixed={"Top": True}, locked=True)
    rep = api.make_repeat([source], row(count=1))
    (copy,) = copies(rep, source)
    twin = member(copy, "Étagère 2")
    for name in OPTIONS:
        assert getattr(twin, name) == getattr(shelf, name), name
    assert twin.RepeatSource == shelf and api.furniture_of(twin) == copy
    assert twin.Material == shelf.Material and twin.Thickness == shelf.Thickness
    left, left_twin = member(source, "Côté gauche"), member(copy, "Côté gauche 2")
    assert {n: getattr(left_twin, n) for n in OPTIONS} == {n: getattr(left, n) for n in OPTIONS}
    assert stale_or_invalid(document) == []


def test_les_cotes_pilotees_viennent_de_l_ensemble_copie(document: Any) -> None:
    source = caisson(document)
    rep = api.make_repeat([source], row(count=1))
    (copy,) = copies(rep, source)
    right, original = member(copy, "Côté droit 2"), member(source, "Côté droit")
    assert engine(right)["Length"] == f"<<{copy.Label}>>.Height"  # cote liée par l'ensemble copie
    assert engine(original)["Length"] == f"<<{source.Label}>>.Height"
    assert engine(right)["Thickness"] == f"{original.Name}.Thickness"  # non pilotée : la source
    assert engine(right)["Material"] == f"{original.Name}.Material"
    assert dict(right.FurnitureBindings)["Length"] == engine(right)["Length"]


def test_redimensionner_le_caisson_source_redimensionne_la_copie(document: Any) -> None:
    source = caisson(document)
    rep = api.make_repeat([source], row())
    api.resize_furniture(source, width=800, depth=500, height=900)
    assert stale_or_invalid(document) == []
    for index, copy in enumerate(copies(rep, source), start=1):
        assert (copy.Width.Value, copy.Depth.Value, copy.Height.Value) == (800, 500, 900)
        assert corner(copy) == (700.0 * index, 0.0, 0.0)  # le pas est fixe
        x0 = 700.0 * index
        assert bounds(member(copy, f"Côté droit {index + 1}")) == (
            x0 + 782,
            x0 + 800,
            0,
            500,
            0,
            900,
        )
        assert bounds(member(copy, f"Dessus {index + 1}")) == (x0 + 18, x0 + 782, 0, 500, 882, 900)
        assert bounds(member(copy, f"Fond {index + 1}"))[:2] == (x0 + 8, x0 + 792)
    twin = member(copies(rep, source)[0], "Étagère 2")
    assert bounds(twin)[2:] == bounds(member(source, "Étagère"))[2:]
    api.resize_furniture(source, height=700)
    assert [c.Height.Value for c in copies(rep, source)] == [700.0, 700.0]
    assert stale_or_invalid(document) == []


def test_l_epaisseur_de_la_source_est_suivie(document: Any) -> None:
    source = caisson(document)
    rep = api.make_repeat([source], row(count=1))
    (copy,) = copies(rep, source)
    shelf = member(source, "Étagère")
    shelf.Thickness = 25
    document.recompute()
    assert stale_or_invalid(document) == []
    twin = member(copy, "Étagère 2")
    assert twin.Thickness.Value == 25.0
    assert twin.Placement.Base.z == pytest.approx(shelf.Placement.Base.z)


def test_assemblages_copies_entre_les_membres(document: Any) -> None:
    source = caisson(document)
    before = joints(document)
    assert len(before) == 8
    rep = api.make_repeat([source], row())
    assert len(joints(document)) == 8 * 3
    first = copies(rep, source)[0]
    inside = {m.Name for m in members(first)}
    mine = [j for j in joints(document) if {j.HostPart.Name, j.GuestPart.Name} <= inside]
    assert len(mine) == 8
    for child in mine:
        parent = child.RepeatJoint
        assert parent in before and type(parent.Proxy) is type(child.Proxy)
        assert (child.HostPart.RepeatSource, child.GuestPart.RepeatSource) == (
            parent.HostPart,
            parent.GuestPart,
        )
    assert stale_or_invalid(document) == []
    for piece in members(first):
        machined = api.machined_part_of(piece)
        if not piece.Label.startswith(("Étagère", "Fond")):  # le fond n'est que l'invité
            assert machined is not None and machined.Shape.Volume < piece.Shape.Volume


def test_sans_recopier_les_assemblages(document: Any) -> None:
    source = caisson(document)
    api.make_repeat([source], row(copy_joints=False))
    assert len(joints(document)) == 8


def test_changer_le_nombre_de_caissons(undoable: Any) -> None:
    source = caisson(undoable)
    rep = api.make_repeat([source], row(count=1))
    base = len(undoable.Objects)
    api.edit_repeat(rep, row(count=3))
    assert [c.Label for c in copies(rep, source)] == ["Caisson 2", "Caisson 3", "Caisson 4"]
    assert len(joints(undoable)) == 8 * 4 and stale_or_invalid(undoable) == []
    assert corner(copies(rep, source)[2]) == (2100.0, 0.0, 0.0)
    api.edit_repeat(rep, row(count=1))
    assert len(undoable.Objects) == base and len(joints(undoable)) == 8 * 2
    left = [o for o in undoable.Objects if container.is_workshop(o) or container.is_std_part(o)]
    assert not [
        o for o in left if re.search(r"[34]( \(Std Part\))?$", o.Label)
    ]  # Std Parts compris
    assert stale_or_invalid(undoable) == []
    api.edit_repeat(rep, row(count=2, step=900, axis="Y", reverse=True))
    assert [corner(c) for c in copies(rep, source)] == [(0, -900, 0), (0, -1800, 0)]
    assert stale_or_invalid(undoable) == []


# --- Caisson sous-ensemble, sous-ensembles imbriqués ----------------------------------------


def test_copie_d_un_sous_ensemble_dans_le_meme_parent(bureau: Any) -> None:
    doc = bureau.doc
    source, _ = api.make_carcass(
        doc, width=300, depth=400, height=300, shelf_count=0, origin=Vec3(40, 0, 0),
        furniture=bureau.furniture,
    )  # fmt: skip
    doc.recompute()
    rep = api.make_repeat([source], row(count=2, step=320.0))
    first, second = copies(rep, source)
    for copy in (first, second):
        assert api.furniture_of(copy) == bureau.furniture  # sous-ensemble du même parent
        assert copy.getEditorMode("Furniture") == ["ReadOnly"]
        assert copy.FixedLeft == source.FixedLeft
        assert dict(copy.FurnitureBindings) == {}  # elle suit sa source, pas le bureau
        assert "Depth" in engine(copy) and engine(copy)["Depth"] == f"{source.Name}.Depth"
    assert stale_or_invalid(doc) == []
    assert corner(first) == (360.0, 0.0, 0.0)
    for other in (source, first, second):  # les liaisons du bureau sont intactes
        assert other.Depth.Value == 400.0
    api.resize_furniture(bureau.furniture, depth=800)
    assert stale_or_invalid(doc) == []
    assert [c.Depth.Value for c in (source, first, second)] == [600.0, 600.0, 600.0]
    twin = member(first, "Côté gauche 2")
    assert bounds(twin) == (360.0, 378.0, 0.0, 600.0, 0.0, 300.0)
    # les copies comptent comme membres de la rangée : les trois caissons se partagent les 100 mm
    api.resize_furniture(bureau.furniture, width=1300)
    assert source.Width.Value == pytest.approx(300 + 100 / 3)
    assert [c.Width.Value for c in (first, second)] == [source.Width.Value] * 2
    assert stale_or_invalid(doc) == []
    api.rebind_furniture(bureau.furniture)  # « Relier les pièces » ne touche pas aux copies
    assert engine(first)["Depth"] == f"{source.Name}.Depth"
    assert stale_or_invalid(doc) == []


def test_ensemble_dans_un_ensemble_copie_recursivement(document: Any) -> None:
    source, inner = caisson_with_inner(document)
    rep = api.make_repeat([source], row(count=1))
    (copy,) = copies(rep, source)
    (inner_copy,) = [m for m in members(copy) if m.Label.startswith("Caisson")]
    assert inner_copy.RepeatSource == inner and api.furniture_of(inner_copy) == copy
    assert len(members(inner_copy)) == 5
    assert corner(inner_copy) == (800.0, 0.0, 100.0)
    assert len(joints(document)) == 2 * (8 + 8)
    api.resize_furniture(source, width=800, height=900)
    assert stale_or_invalid(document) == []
    assert copy.Width.Value == 800
    assert corner(inner_copy)[2] == pytest.approx(corner(inner)[2])
    assert corner(inner_copy)[0] == pytest.approx(corner(inner)[0] + 700)
    api.dissociate(copy)
    assert not repeat.is_copy(inner_copy) and all(not repeat.is_copy(m) for m in members(copy))
    api.resize_furniture(copy, width=1000)
    assert stale_or_invalid(document) == []
    assert inner_copy.Width.Value == inner.Width.Value + 200  # la copie a gagné 200 mm de plus


def test_formule_de_l_utilisateur_sur_un_membre_suivie_par_la_copie(document: Any) -> None:
    source = caisson(document, shelf_count=0)
    left = member(source, "Côté gauche")
    left.Placement = App.Placement(App.Vector(30, 0, 0), left.Placement.Rotation)
    left.setExpression("Placement.Base.x", f"{source.Name}.Origin.x + 30 mm")  # formule libre
    document.recompute()
    rep = api.make_repeat([source], row(count=1))
    (copy,) = copies(rep, source)
    twin = member(copy, "Côté gauche 2")
    # le décalage de la copie (700 mm) est dans son Std Part : la formule cite seulement la source
    assert engine(twin)["Placement.Base.x"] == f"{left.Name}.Placement.Base.x"
    assert twin.getGlobalPlacement().Base.x == pytest.approx(730.0)
    assert stale_or_invalid(document) == []


# --- Sélection mixte, refus ------------------------------------------------------------------


def test_selection_mixte_pieces_et_ensembles(document: Any) -> None:
    source = caisson(document, shelf_count=0)
    plank = board(document, "Tasseau", (400, 40, 22), (0, 1000, 0))
    document.recompute()
    rep = api.make_repeat([source, plank], row(count=2, step=500.0))
    assert [c.Label for c in copies(rep, source)] == ["Caisson 2", "Caisson 3"]
    assert [c.Label for c in copies(rep, plank)] == ["Tasseau 2", "Tasseau 3"]
    assert [c.Placement.Base.x for c in copies(rep, plank)] == [500.0, 1000.0]
    assert [corner(c)[0] for c in copies(rep, source)] == [500.0, 1000.0]
    assert stale_or_invalid(document) == []


def test_une_piece_n_est_pas_repetee_avec_son_ensemble(document: Any) -> None:
    source = caisson(document)
    shelf = member(source, "Étagère")
    count = len(document.Objects)
    with pytest.raises(ValueError, match=r"« Étagère » est membre de « Caisson »"):
        api.make_repeat([source, shelf], row())
    with pytest.raises(ValueError, match="répété en même temps"):
        api.make_repeat([shelf, source], row())
    assert len(document.Objects) == count
    rep = api.make_repeat([shelf], row(axis="Z", step=100, count=1))  # la pièce seule : permis
    assert api.furniture_of(copies(rep, shelf)[0]) == source


def test_ensemble_deja_copie_ou_avec_forme_libre_refuse(document: Any) -> None:
    source = caisson(document)
    rep = api.make_repeat([source], row(count=1))
    with pytest.raises(ValueError, match="dissociez-la"):
        api.make_repeat(copies(rep, source), row())
    other = caisson(document, origin=Vec3(0, 2000, 0))
    assert copies(rep, source) and other is not source
    with pytest.raises(TypeError, match="n'est pas une pièce de bois"):
        api.make_repeat([document.addObject("Part::Box", "Bloc")], row())


# --- R20 : dissocier un ensemble copie -------------------------------------------------------


def test_dissocier_un_ensemble_copie(undoable: Any) -> None:
    source = caisson(undoable)
    rep = api.make_repeat([source], row())
    first, second = copies(rep, source)
    pieces = members(first)
    api.dissociate(first)
    assert not repeat.is_copy(first) and api.repeat_of(first) is None
    assert engine(first) == {} and first.Width.Value == 600.0
    assert engine(container.std_part_of(first)) == {}  # le Std Part ne cite plus la source
    assert corner(first) == (700.0, 0.0, 0.0)
    for piece in pieces:
        assert not repeat.is_copy(piece) and "Repeat" not in piece.PropertiesList
        assert not [t for t in engine(piece).values() if source.Name in t or "Repeat" in t]
    assert [c.Name for c in copies(rep, source)] == [second.Name]
    assert (rep.Count, second.RepeatIndex) == (2, 2)
    assert all(
        repeat.is_copy(m) for m in members(second)
    )  # l'autre copie reste liée, avec ses membres
    for joint in joints(undoable):  # les assemblages de l'ensemble dissocié sont libres
        if {joint.HostPart.Name, joint.GuestPart.Name} <= {m.Name for m in pieces}:
            assert "RepeatJoint" not in joint.PropertiesList
    assert stale_or_invalid(undoable) == []
    api.resize_furniture(source, width=900)  # l'ensemble dissocié ne suit plus la source
    assert (first.Width.Value, second.Width.Value) == (600.0, 900.0)
    api.resize_furniture(first, width=650, height=800)  # il se redimensionne comme tout ensemble
    assert stale_or_invalid(undoable) == []
    assert bounds(member(first, "Côté droit 2"))[:2] == (700 + 632, 700 + 650)
    assert bounds(member(first, "Dessus 2"))[4:] == (782.0, 800.0)
    api.edit_repeat(rep, row(count=3))  # la copie dissociée ne revient pas
    assert [c.RepeatIndex for c in copies(rep, source)] == [2, 3]
    undoable.undo()
    assert [c.RepeatIndex for c in copies(rep, source)] == [2]


def test_dissocier_un_membre_copie_le_relie_a_son_ensemble(document: Any) -> None:
    source = caisson(document)
    rep = api.make_repeat([source], row(count=1))
    (copy,) = copies(rep, source)
    shelf = member(copy, "Étagère 2")
    api.dissociate(shelf)
    assert not repeat.is_copy(shelf) and repeat.is_copy(copy)
    assert api.furniture_of(shelf) == copy and "Length" in dict(shelf.FurnitureBindings)
    api.resize_furniture(source, width=800)  # la copie suit la source, l'étagère libre l'ensemble
    assert stale_or_invalid(document) == []
    assert shelf.Length.Value == pytest.approx(762.0)
    assert len(members(copy)) == 6


def test_supprimer_la_source_ou_la_repetition(undoable: Any) -> None:
    source = caisson(undoable)
    rep = api.make_repeat([source], row(count=1))
    (copy,) = copies(rep, source)
    undoable.removeObject(rep.Name)
    assert not repeat.is_copy(copy) and not [m for m in members(copy) if repeat.is_copy(m)]
    assert engine(copy) == {}
    undoable.recompute()
    assert stale_or_invalid(undoable) == []
    api.resize_furniture(copy, width=700)
    assert stale_or_invalid(undoable) == []
    other = caisson(undoable, origin=Vec3(0, 2000, 0))
    rep2 = api.make_repeat([other], row(count=1))
    (copy2,) = copies(rep2, other)
    undoable.removeObject(other.Name)
    assert rep2.Source == [] and not repeat.is_copy(copy2)
    assert engine(copy2) == {}
    undoable.recompute()
    assert stale_or_invalid(undoable) == []


# --- Annulation, réouverture -----------------------------------------------------------------


def test_annulation_en_un_bloc(undoable: Any) -> None:
    source = caisson(undoable)
    before = {o.Name for o in undoable.Objects}
    api.make_repeat([source], row())
    assert len(undoable.Objects) > len(before) + 3 * 8
    assert undoable.UndoNames[0] == "Répéter"
    undoable.undo()
    assert {o.Name for o in undoable.Objects} == before
    assert stale_or_invalid(undoable) == []
    undoable.redo()
    undoable.recompute()
    rep = undoable.getObject("Repeat")
    assert len(copies(rep, source)) == 2 and len(joints(undoable)) == 8 * 3
    assert stale_or_invalid(undoable) == []
    api.edit_repeat(rep, row(count=1))
    undoable.undo()
    undoable.recompute()
    assert len(copies(rep, source)) == 2 and stale_or_invalid(undoable) == []


def test_refus_pendant_l_edition_ne_laisse_rien(undoable: Any) -> None:
    source = caisson(undoable)
    rep = api.make_repeat([source], row(count=1))
    before = (len(undoable.Objects), engine(copies(rep, source)[0]))
    with pytest.raises(ValueError):
        api.edit_repeat(rep, api.RepeatParams(spacing="CountOnSpan", count=2, span=10))
    with pytest.raises(ValueError, match="100"):
        api.edit_repeat(rep, row(count=101))
    assert (len(undoable.Objects), engine(copies(rep, source)[0])) == before


def test_enregistrer_et_rouvrir(document: Any, rouvrir: Reopen) -> None:
    source = caisson(document)
    rep = api.make_repeat([source], row(follow_resize=False))
    first, second = copies(rep, source)
    names = (source.Name, rep.Name, first.Name, second.Name)
    engines = {o.Name: engine(o) for o in (first, second, *members(first), *members(second))}
    doc = rouvrir(document)
    source, rep, first, second = (doc.getObject(n) for n in names)
    assert stale_or_invalid(doc) == []
    assert type(first.Proxy).__name__ == "Furniture" and repeat.is_copy(first)
    assert (first.Repeat, first.RepeatSource, first.RepeatIndex) == (rep, source, 1)
    assert first.getEditorMode("Repeat") == ["ReadOnly"]
    assert {o.Name: engine(o) for o in (first, second, *members(first), *members(second))} == (
        engines
    )
    assert all(repeat.is_copy(m) for m in members(first))
    assert api.furniture_of(members(first)[0]) == first
    api.resize_furniture(source, width=750)
    assert stale_or_invalid(doc) == []
    assert (first.Width.Value, second.Width.Value) == (750.0, 750.0)
    api.edit_repeat(rep, row(count=3))
    assert len(copies(rep, source)) == 3 and stale_or_invalid(doc) == []
    api.dissociate(second)
    assert stale_or_invalid(doc) == []
    api.resize_furniture(second, width=800)
    assert stale_or_invalid(doc) == []


# --- Suivre le redimensionnement d'un ensemble parent ------------------------------------------


def test_suivre_le_redimensionnement_d_un_caisson_dans_le_bureau(bureau: Any) -> None:
    doc = bureau.doc
    source, _ = api.make_carcass(
        doc, width=300, depth=400, height=300, shelf_count=0, origin=Vec3(40, 0, 0),
        furniture=bureau.furniture,
    )  # fmt: skip
    doc.recompute()
    rep = api.make_repeat([source], row(count=2, step=320.0, follow_resize=True))
    assert rep.FollowResize and set(engine(rep)) == {"Span", "Step"}
    assert engine(rep)["Span"].startswith(f"{bureau.furniture.Name}.Width - ")
    assert rep.Step.Value == pytest.approx(320.0)
    api.resize_furniture(bureau.furniture, width=1500)
    assert stale_or_invalid(doc) == []
    assert rep.Step.Value == pytest.approx(470.0)
    assert [corner(c)[0] for c in copies(rep, source)] == [510.0, 980.0]
    assert [len(copies(rep, source)), rep.Count] == [2, 2]


# --- Rangées, cycles ------------------------------------------------------------------------


def test_epaisseur_d_un_voisin_modifiee_avec_des_copies(document: Any) -> None:
    meuble = Meuble(document)
    rep = meuble.repeat()
    meuble.left.Thickness = 30  # saisie de l'éditeur de propriétés : tout l'ensemble est relié
    document.recompute()
    assert stale_or_invalid(document) == []
    for shelf in (meuble.shelf, *copies(rep)):
        assert shelf.Length.Value == pytest.approx(600 - 30 - 18)
    meuble.shelf.Thickness = 25
    document.recompute()
    assert stale_or_invalid(document) == []
    assert [c.Thickness.Value for c in copies(rep)] == [25.0, 25.0]
    api.resize_furniture(meuble.furniture, width=700)
    assert stale_or_invalid(document) == []
    assert [c.Length.Value for c in copies(rep)] == [pytest.approx(700 - 30 - 18)] * 2


def test_aucun_cycle_de_dependance(document: Any) -> None:
    meuble = Meuble(document)
    meuble.repeat()
    source = caisson(document, origin=Vec3(0, 2000, 0))
    api.make_repeat([source], row(count=2))
    for obj in document.Objects:
        assert obj not in obj.OutListRecursive, obj.Name
    document.recompute()
    assert stale_or_invalid(document) == []
