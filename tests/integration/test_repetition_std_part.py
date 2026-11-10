# SPDX-License-Identifier: LGPL-2.1-or-later
"""Répétition d'un ensemble et Std Part d'ensemble (ADR 0044, section « Std Part »).

Chaque copie d'un ensemble a son propre Std Part, créé comme celui d'un ensemble neuf, où entrent
ses membres copiés ; le ``Placement`` de ce Std Part est celui du Std Part de la source plus le
décalage. Création, suivi de la source (cotes, déplacement, rotation), sous-ensemble (règle
``carried``), dissociation, suppression (nombre réduit, répétition, source, Std Part, interface)
sans Std Part orphelin, annulation, enregistrer et rouvrir.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from freecad.menuiserie.core.geometry import Vec3
from tests.integration.cadre import stale_or_invalid
from tests.integration.test_repetition_ensembles import (
    caisson,
    caisson_with_inner,
    copies,
    corner,
    engine,
    joints,
    member,
    members,
    row,
)

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
api = pytest.importorskip("freecad.menuiserie.api")
repeat = pytest.importorskip("freecad.menuiserie.features.repeat")
container = pytest.importorskip("freecad.menuiserie.features.furniture_container")
entry = pytest.importorskip("freecad.menuiserie.features.furniture_entry")
furniture_module = pytest.importorskip("freecad.menuiserie.features.furniture")
release_furniture = pytest.importorskip(
    "freecad.menuiserie.features.furniture_members"
).release_furniture
bindings = pytest.importorskip("freecad.menuiserie.features.furniture_bindings")
watch = pytest.importorskip("freecad.menuiserie.features.std_part_watch")

Reopen = Callable[[Any], Any]


@pytest.fixture
def undoable(document: Any) -> Any:
    document.UndoMode = 1
    return document


def std_parts(doc: Any) -> list[Any]:
    return [o for o in doc.Objects if container.is_std_part(o)]


def std_of(furniture: Any) -> Any:
    return container.std_part_of(furniture)


def orphans(doc: Any) -> list[str]:
    """Std Parts qui ne contiennent aucun ensemble (sauf ceux de l'utilisateur)."""
    return [
        part.Label
        for part in std_parts(doc)
        if not any(furniture_module.is_furniture(o) for o in part.Group)
        and not any(container.is_std_part(o) for o in part.Group)
    ]


def global_bounds(part: Any) -> tuple[float, ...]:
    shape = part.Shape.copy()
    shape.Placement = part.getGlobalPlacement()
    box = shape.BoundBox
    return tuple(round(v, 3) for v in (box.XMin, box.XMax, box.YMin, box.YMax, box.ZMin, box.ZMax))


def delete_like_the_interface(furniture: Any) -> None:
    """Suppression par l'interface (``ViewProviderFurniture.onDelete``) puis ``removeObject``."""
    messages = release_furniture(furniture)
    assert all(messages)
    furniture.Document.removeObject(furniture.Name)


# --- Création ----------------------------------------------------------------------------------


def test_la_copie_a_son_propre_std_part(document: Any) -> None:
    source = caisson(document)
    rep = api.make_repeat([source], row())
    first, second = copies(rep, source)
    own = std_of(source)
    assert len(std_parts(document)) == 3 and orphans(document) == []
    for index, copy in enumerate((first, second), start=1):
        part = std_of(copy)
        assert part is not None and part != own and part.TypeId == "App::Part"
        assert part.Label == f"{copy.Label} (Std Part)"
        assert part.getParentGeoFeatureGroup() == own.getParentGeoFeatureGroup()
        assert (
            container.own_std_part(copy) == part
        )  # un Std Part propre : il se déplace à la souris
        assert tuple(copy.Origin) == tuple(source.Origin)
        assert corner(copy) == (700.0 * index, 0.0, 0.0)
        inside = {o.Name for o in part.Group if o.TypeId != "App::Origin"}
        found = {m.Name for m in members(copy)}
        assert found <= inside and copy.Name in inside
        assert {j.Name for j in joints(document) if j.HostPart.Name in found} <= inside
    assert {m.Name for m in members(source)} <= {o.Name for o in own.Group}
    assert not {m.Name for c in (first, second) for m in members(c)} & {o.Name for o in own.Group}
    assert stale_or_invalid(document) == []


def test_la_copie_est_a_la_meme_place_que_la_source_au_decalage_pres(document: Any) -> None:
    source = caisson(document)
    rep = api.make_repeat([source], row(count=1))
    (copy,) = copies(rep, source)
    for label in ("Côté droit", "Dessus", "Fond", "Étagère"):
        twin, original = member(copy, f"{label} 2"), member(source, label)
        assert tuple(twin.Placement.Base) == tuple(original.Placement.Base)  # même place, Std Part
        assert twin.getGlobalPlacement().Base.x == pytest.approx(
            original.getGlobalPlacement().Base.x + 700.0
        )
    assert stale_or_invalid(document) == []


def test_copie_d_un_ensemble_range_chez_l_utilisateur(document: Any) -> None:
    user = document.addObject("App::Part", "Atelier")
    user.Placement = App.Placement(App.Vector(0, 500, 0), App.Rotation(App.Vector(0, 0, 1), 90))
    source, _ = api.make_carcass(document, shelf_count=0)
    document.recompute()
    user.addObject(std_of(source))
    document.recompute()
    rep = api.make_repeat([source], row(count=1))
    (copy,) = copies(rep, source)
    assert std_of(copy).getParentGeoFeatureGroup() == user  # rangée avec la source
    assert rep.getParentGeoFeatureGroup() == user
    shift = corner(copy)[0] - corner(source)[0], corner(copy)[1] - corner(source)[1]
    assert shift == pytest.approx((0.0, 700.0), abs=1e-6)  # le pas suit l'axe X du conteneur
    assert stale_or_invalid(document) == []


# --- Suivi de la source ------------------------------------------------------------------------


def test_la_copie_suit_la_source_redimensionnee(document: Any) -> None:
    source = caisson(document)
    rep = api.make_repeat([source], row(count=1))
    (copy,) = copies(rep, source)
    api.resize_furniture(source, width=800, depth=500, height=900)
    assert stale_or_invalid(document) == []
    assert (copy.Width.Value, copy.Depth.Value, copy.Height.Value) == (800, 500, 900)
    assert global_bounds(member(copy, "Côté droit 2")) == (1482, 1500, 0, 500, 0, 900)
    assert std_of(copy).Placement.Base.x == 700.0


def test_la_copie_suit_la_source_deplacee_et_tournee(document: Any) -> None:
    source = caisson(document, shelf_count=0)
    rep = api.make_repeat([source], row(count=1))
    (copy,) = copies(rep, source)
    assert api.move_furniture(source, (50, 20, 10))
    assert stale_or_invalid(document) == []
    assert corner(copy) == (750.0, 20.0, 10.0)
    assert std_of(copy).Placement.Base.isEqual(App.Vector(750, 20, 10), 1e-6)
    assert api.rotate_furniture(source, (0, 0, 30))
    assert stale_or_invalid(document) == []
    assert std_of(copy).Placement.Rotation.isSame(std_of(source).Placement.Rotation, 1e-9)
    assert not api.move_furniture(copy, (1, 0, 0))  # sa position est pilotée par la source
    twin, original = member(copy, "Côté droit 2"), member(source, "Côté droit")
    assert twin.Shape.BoundBox.XLength == pytest.approx(original.Shape.BoundBox.XLength)
    assert twin.getGlobalPlacement().Rotation.isSame(original.getGlobalPlacement().Rotation, 1e-9)


def test_le_pas_change_avec_le_std_part(document: Any) -> None:
    source = caisson(document, shelf_count=0)
    rep = api.make_repeat([source], row(count=1))
    (copy,) = copies(rep, source)
    rep.Step = 900
    document.recompute()
    assert corner(copy) == (900.0, 0.0, 0.0) and stale_or_invalid(document) == []


def test_membre_ajoute_a_la_source_entre_dans_le_std_part_de_la_copie(document: Any) -> None:
    source = caisson(document, shelf_count=0)
    rep = api.make_repeat([source], row(count=1))
    (copy,) = copies(rep, source)
    plank = api.make_wood_part(500, 100, 18, "chene", mark="Tasseau", doc=document)
    plank.Placement = App.Placement(App.Vector(30, 30, 100), App.Rotation())
    document.recompute()
    api.add_to_furniture(source, [plank])
    api.edit_repeat(rep, row(count=1))  # recopie les membres que la source a gagnés
    twin = member(copy, "Tasseau 2")
    assert twin.getParentGeoFeatureGroup() == std_of(copy)
    assert tuple(twin.Placement.Base) == tuple(plank.Placement.Base)
    assert twin.getGlobalPlacement().Base.x == pytest.approx(730.0)
    assert stale_or_invalid(document) == []


# --- Sous-ensembles (règle « carried ») ---------------------------------------------------------


def test_sous_ensemble_copie_dans_le_std_part_de_la_copie(document: Any) -> None:
    source, inner = caisson_with_inner(document)
    rep = api.make_repeat([source], row(count=1))
    (copy,) = copies(rep, source)
    (twin,) = [m for m in members(copy) if m.Label.startswith("Caisson")]
    part = std_of(twin)
    assert part is not None and part.getParentGeoFeatureGroup() == std_of(copy)
    assert tuple(twin.Origin) == (0, 0, 0)  # le parent lie le Placement du Std Part (carried)
    assert corner(twin) == (800.0, 0.0, 100.0)
    read = bindings.read_members(copy)
    flags = {m.key: (m.carried, m.linked) for m in read.members}
    assert flags[twin.Name] == (True, False)  # copie interne : liée par l'ensemble copie
    assert "Placement.Base.x" in engine(part)  # la position vient des liaisons de la copie
    api.resize_furniture(source, width=900, height=800)
    assert stale_or_invalid(document) == []
    assert copy.Width.Value == 900
    assert corner(twin)[0] == pytest.approx(corner(inner)[0] + 700)
    assert std_of(twin).getParentGeoFeatureGroup() == std_of(copy)


def test_repeter_un_sous_ensemble_est_carried_et_lie(bureau: Any) -> None:
    doc = bureau.doc
    source, _ = api.make_carcass(
        doc, width=300, depth=400, height=300, shelf_count=0, origin=Vec3(40, 0, 0),
        furniture=bureau.furniture,
    )  # fmt: skip
    doc.recompute()
    rep = api.make_repeat([source], row(count=1, step=320.0))
    (copy,) = copies(rep, source)
    part = std_of(copy)
    assert part.getParentGeoFeatureGroup() == std_of(bureau.furniture)
    assert tuple(copy.Origin) == (0, 0, 0) and corner(copy) == (360.0, 0.0, 0.0)
    read = bindings.read_members(bureau.furniture)
    flags = {m.key: (m.carried, m.linked) for m in read.members}
    assert flags[source.Name] == (True, False) and flags[copy.Name] == (True, True)
    assert dict(copy.FurnitureBindings) == {}  # elle suit sa source, pas le bureau
    assert stale_or_invalid(doc) == []
    api.resize_furniture(bureau.furniture, width=1300)
    assert stale_or_invalid(doc) == []
    assert corner(copy)[0] == pytest.approx(corner(source)[0] + 320.0)


# --- Dissociation ------------------------------------------------------------------------------


def test_dissocier_laisse_un_ensemble_normal_avec_son_std_part(document: Any) -> None:
    source = caisson(document, shelf_count=0)
    rep = api.make_repeat([source], row())
    first, second = copies(rep, source)
    part = std_of(first)
    api.dissociate(first)
    assert std_of(first) == part and engine(part) == {} and engine(first) == {}
    assert not any(repeat.is_copy(o) for o in (first, *members(first)))
    assert corner(first) == (700.0, 0.0, 0.0)
    api.move_furniture(source, (0, 100, 0))  # la source bouge : la copie dissociée reste
    assert corner(first) == (700.0, 0.0, 0.0) and corner(second) == (1400.0, 100.0, 0.0)
    assert api.move_furniture(first, (0, 0, 30))  # elle se déplace comme tout ensemble
    assert corner(first) == (700.0, 0.0, 30.0)
    assert stale_or_invalid(document) == [] and orphans(document) == []


# --- Suppression -------------------------------------------------------------------------------


def test_reduire_le_nombre_supprime_les_std_parts_des_copies(undoable: Any) -> None:
    source = caisson(undoable, shelf_count=0)
    rep = api.make_repeat([source], row(count=1))
    before = (len(undoable.Objects), len(std_parts(undoable)))
    api.edit_repeat(rep, row(count=3))
    assert len(std_parts(undoable)) == before[1] + 2
    api.edit_repeat(rep, row(count=1))
    assert (len(undoable.Objects), len(std_parts(undoable))) == before
    assert orphans(undoable) == [] and stale_or_invalid(undoable) == []
    undoable.undo()
    undoable.recompute()
    assert len(std_parts(undoable)) == before[1] + 2 and stale_or_invalid(undoable) == []


def test_piece_ajoutee_a_la_main_sort_du_std_part_d_une_copie_supprimee(undoable: Any) -> None:
    source = caisson(undoable, shelf_count=0)
    rep = api.make_repeat([source], row(count=2))
    first, second = copies(rep, source)
    planks = []
    for copy in (first, second):
        plank = api.make_wood_part(400, 60, 18, "chene", mark=f"Libre {copy.Label}", doc=undoable)
        plank.Placement = App.Placement(App.Vector(800, 0, 50), App.Rotation())
        undoable.recompute()
        api.add_to_furniture(copy, [plank])
        planks.append(plank)
    where = [plank.getGlobalPlacement() for plank in planks]
    api.edit_repeat(rep, row(count=1))  # la copie de rang 2 saute, pas la première
    assert planks[0].getParentGeoFeatureGroup() == std_of(first)
    assert planks[1].getParentGeoFeatureGroup() is None  # libre, à sa place globale
    assert all(p.getGlobalPlacement().isSame(w, 1e-6) for p, w in zip(planks, where, strict=True))
    assert orphans(undoable) == [] and stale_or_invalid(undoable) == []


def test_supprimer_la_repetition_supprime_les_copies_et_leur_std_part(document: Any) -> None:
    source = caisson(document, shelf_count=0)
    rep = api.make_repeat([source], row())
    names = [n for c in copies(rep, source) for n in (c.Name, std_of(c).Name)]
    document.removeObject(rep.Name)
    document.recompute()
    assert [n for n in names if document.getObject(n) is not None] == []
    assert stale_or_invalid(document) == [] and orphans(document) == []


def test_supprimer_la_source_dissocie_les_copies(document: Any) -> None:
    source = caisson(document, shelf_count=0)
    rep = api.make_repeat([source], row())
    first, second = copies(rep, source)
    delete_like_the_interface(source)
    document.recompute()
    assert stale_or_invalid(document) == []
    assert not repeat.is_copy(first) and engine(std_of(first)) == {} and engine(first) == {}
    assert corner(second) == (1400.0, 0.0, 0.0)
    assert rep.Source == [] or source.Name not in [o.Name for o in rep.Source]
    api.move_furniture(first, (0, 10, 0))
    assert corner(first) == (700.0, 10.0, 0.0) and orphans(document) == []


def test_supprimer_une_copie_par_l_interface_ne_laisse_pas_de_std_part(document: Any) -> None:
    source = caisson(document, shelf_count=0)
    rep = api.make_repeat([source], row(count=1))
    (copy,) = copies(rep, source)
    delete_like_the_interface(copy)
    document.recompute()
    assert len(std_parts(document)) == 1 and orphans(document) == []
    assert stale_or_invalid(document) == []
    api.resize_furniture(source, width=700)
    assert stale_or_invalid(document) == []


def test_std_part_de_la_source_supprime_a_la_main(document: Any) -> None:
    source = caisson(document, shelf_count=0)
    rep = api.make_repeat([source], row(count=1))
    (copy,) = copies(rep, source)
    part = std_of(source)
    watch.std_part_deleted(part)  # appelé par l'observateur avant la suppression
    document.removeObject(part.Name)
    document.recompute()
    assert not repeat.is_copy(copy) and engine(std_of(copy)) == {}
    assert corner(copy) == (700.0, 0.0, 0.0)
    assert stale_or_invalid(document) == []


# --- Annulation, enregistrement ----------------------------------------------------------------


def test_annuler_la_repetition_retire_les_std_parts(undoable: Any) -> None:
    source = caisson(undoable)
    undoable.clearUndos()
    before = (len(undoable.Objects), len(std_parts(undoable)))
    api.make_repeat([source], row())
    assert len(std_parts(undoable)) == before[1] + 2
    undoable.undo()
    undoable.recompute()
    assert (len(undoable.Objects), len(std_parts(undoable))) == before
    assert stale_or_invalid(undoable) == []
    undoable.redo()
    undoable.recompute()
    assert len(std_parts(undoable)) == before[1] + 2 and stale_or_invalid(undoable) == []


def test_enregistrer_et_rouvrir_une_copie_avec_son_std_part(document: Any, rouvrir: Reopen) -> None:
    source = caisson(document)
    rep = api.make_repeat([source], row())
    first, second = copies(rep, source)
    names = (source.Name, rep.Name, first.Name, second.Name)
    placed = {n: engine(std_of(document.getObject(n))) for n in names[2:]}
    doc = rouvrir(document)
    source, rep, first, second = (doc.getObject(n) for n in names)
    assert stale_or_invalid(doc) == []
    assert {n: engine(std_of(doc.getObject(n))) for n in names[2:]} == placed
    assert all(std_of(c).getParentGeoFeatureGroup() is None for c in (first, second))
    assert (first.Repeat, first.RepeatSource) == (rep, source)
    assert rep.Source == [source]
    assert all(m.getParentGeoFeatureGroup() == std_of(first) for m in members(first))
    api.move_furniture(source, (10, 20, 0))
    api.resize_furniture(source, width=750)
    assert stale_or_invalid(doc) == []
    assert corner(second) == (1410.0, 20.0, 0.0) and second.Width.Value == 750.0
    api.edit_repeat(rep, row(count=3))
    assert len(copies(rep, source)) == 3 and stale_or_invalid(doc) == []
    api.dissociate(second)
    api.edit_repeat(rep, row(count=1))
    assert stale_or_invalid(doc) == [] and orphans(doc) == []
