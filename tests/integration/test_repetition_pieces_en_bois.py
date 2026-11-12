# SPDX-License-Identifier: LGPL-2.1-or-later
"""Répétition des pièces en bois à forme libre (ADR 0050, critères S2 à S9 de
``docs/specs/repetition.md`` § 11) : la copie lie le même corps, ses cotes ne sont jamais liées.
"""

from __future__ import annotations

from typing import Any

import pytest

from tests.integration.aides_grille import Line, Reopen, X, Y, grid
from tests.integration.cadre import stale_or_invalid
from tests.integration.test_piece_en_bois import box

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
api = pytest.importorskip("freecad.menuiserie.api")
repeat = pytest.importorskip("freecad.menuiserie.features.repeat")
bindings = pytest.importorskip("freecad.menuiserie.features.furniture_bindings")
wood = pytest.importorskip("freecad.menuiserie.features.wood_part")

SIZE = (200.0, 100.0, 50.0)
DIMENSIONS = ("Length", "Width", "Thickness")
BOUND = ("SourceAxes", "ProfileThickness", "Material", "GrainDirection", "LengthAllowance")


def params(**values: Any) -> Any:
    """Trois copies tous les 150 mm sur Y, sauf réglage contraire."""
    return api.RepeatParams(**{"count": 3, "step": 150.0, "axis": "Y", **values})


def shaped_source(doc: Any, mark: str = "Pied", name: str = "Boite") -> Any:
    """Pièce en bois d'une boîte de ``SIZE``, recalculée."""
    part = api.make_shaped_part(box(doc, SIZE, name), mark=mark)
    doc.recompute()
    return part


def copies(rep: Any, src: Any = None) -> list[Any]:
    found: list[Any] = repeat.copies_of(rep, src)
    return found


def engine(obj: Any) -> dict[str, str]:
    return {path.lstrip("."): text for path, text in obj.ExpressionEngine}


@pytest.fixture
def undoable(document: Any) -> Any:
    """Document dont les annulations sont enregistrées."""
    document.UndoMode = 1
    return document


# --- S2 : la copie lie le même corps, sans expression sur les cotes -------------------------


def test_la_copie_lie_le_meme_corps_et_reprend_les_reglages(document: Any) -> None:
    pied = shaped_source(document)
    pied.LengthAllowance = 4
    document.recompute()
    rep = api.make_repeat([pied], params())
    assert len(copies(rep)) == 3
    for copy in copies(rep):
        assert api.is_shaped_part(copy) and copy.Source == pied.Source
        assert (copy.SolidIndex, copy.SolidSignature) == (pied.SolidIndex, pied.SolidSignature)
        assert copy.SourceAxes.isSame(pied.SourceAxes, 1e-9)
        assert (copy.MaterialId, copy.GrainDirection) == (pied.MaterialId, pied.GrainDirection)
        assert copy.LengthAllowance == pied.LengthAllowance
        assert [copy.getPropertyByName(name).Value for name in DIMENSIONS] == list(SIZE)
        assert copy.Shape.isValid() and copy.Shape.Volume == pytest.approx(pied.Shape.Volume)


def test_aucune_expression_sur_les_cotes(document: Any) -> None:
    rep = api.make_repeat([shaped_source(document)], params())
    for copy in copies(rep):
        expressions = engine(copy)
        assert not set(DIMENSIONS) & set(expressions)
        assert all(name in expressions for name in (*BOUND, "Placement.Base.y"))
    assert stale_or_invalid(document) == []


def test_le_corps_n_est_ni_copie_ni_modifie(document: Any) -> None:
    pied = shaped_source(document)
    body = pied.Source
    objects = len(document.Objects)
    api.make_repeat([pied], params(count=2))
    assert len(document.Objects) == objects + 3  # répétition et deux copies, aucun corps
    assert body.ExpressionEngine == [] and body.InList.count(pied) == 1


# --- S3 : placement, pas et sens, en grille -------------------------------------------------


def test_le_placement_suit_la_source_et_le_pas(document: Any) -> None:
    pied = shaped_source(document)
    pied.Placement = App.Placement(App.Vector(10, 20, 0), App.Rotation(App.Vector(0, 0, 1), 30))
    document.recompute()
    rep = api.make_repeat([pied], params(reverse=True))
    assert [round(c.Placement.Base.y, 6) for c in copies(rep)] == [-130.0, -280.0, -430.0]
    pied.Placement = App.Placement(App.Vector(50, 20, 0), pied.Placement.Rotation)
    rep.Step = 100
    document.recompute()
    assert [round(c.Placement.Base.y, 6) for c in copies(rep)] == [-80.0, -180.0, -280.0]
    for copy in copies(rep):
        assert copy.Placement.Base.x == 50.0
        assert copy.Placement.Rotation.isSame(pied.Placement.Rotation, 1e-9)


def test_en_grille(document: Any) -> None:
    rep = api.make_repeat([shaped_source(document)], grid(Line(X, 3, 250.0), Line(Y, 2, 150.0)))
    document.recompute()
    cells = sorted(
        (round(c.Placement.Base.x, 6), round(c.Placement.Base.y, 6)) for c in copies(rep)
    )
    assert cells == [(0.0, 150.0), (250.0, 0.0), (250.0, 150.0), (500.0, 0.0), (500.0, 150.0)]
    assert stale_or_invalid(document) == []


# --- S4 : la copie suit les réglages de la source -------------------------------------------


def test_materiau_fil_et_epaisseur_de_profil_suivent(document: Any) -> None:
    pied = shaped_source(document)
    rep = api.make_repeat([pied], params(count=2))
    wood.set_material(pied, "noyer")
    pied.GrainDirection = "Width"
    document.recompute()
    for copy in copies(rep):
        assert (copy.MaterialId, copy.GrainDirection) == ("noyer", "Width")
    pied.ProfileThickness = 30
    document.recompute()
    assert all(c.ProfileThickness.Value == 30.0 for c in copies(rep))
    assert stale_or_invalid(document) == []


def test_un_corps_modifie_change_les_cotes_des_copies(document: Any) -> None:
    pied = shaped_source(document)
    rep = api.make_repeat([pied], params(count=2))
    pied.Source.Length = 260
    document.recompute()
    for copy in copies(rep):
        assert copy.Length.Value == pytest.approx(pied.Length.Value)
        assert not set(DIMENSIONS) & set(engine(copy))


# --- S5 : dissocier ------------------------------------------------------------------------


def test_dissocier_garde_les_valeurs(undoable: Any) -> None:
    pied = shaped_source(undoable)
    rep = api.make_repeat([pied], params())
    second = copies(rep)[1]
    api.dissociate(second)
    assert not repeat.is_copy(second) and second.ExpressionEngine == []
    assert [
        p for p in ("Repeat", "RepeatSource", "RepeatIndex") if p in second.PropertiesList
    ] == []
    assert second.Source == pied.Source and second.Placement.Base.y == 300.0
    assert second.Length.Value == SIZE[0]
    undoable.recompute()
    assert stale_or_invalid(undoable) == []
    undoable.undo()
    assert repeat.is_copy(second) and "Placement.Base.y" in engine(second)


# --- S6 : suppressions ---------------------------------------------------------------------


def test_supprimer_la_repetition_emporte_les_copies(undoable: Any) -> None:
    rep = api.make_repeat([shaped_source(undoable)], params())
    names = [c.Name for c in copies(rep)]
    undoable.removeObject(rep.Name)
    assert [n for n in names if undoable.getObject(n) is not None] == []
    undoable.recompute()
    assert stale_or_invalid(undoable) == []


def test_supprimer_la_source_dissocie_les_copies(undoable: Any) -> None:
    pied = shaped_source(undoable)
    rep = api.make_repeat([pied], params())
    kept = copies(rep)
    body = pied.Source
    undoable.removeObject(pied.Name)
    assert rep.Source == [] and undoable.getObject(body.Name) is body
    for copy in kept:
        assert not repeat.is_copy(copy) and copy.ExpressionEngine == []
    undoable.recompute()
    assert [c.Shape.isValid() for c in kept] == [True] * 3
    assert stale_or_invalid(undoable) == []


# --- S7 : ensemble contenant une pièce convertie -------------------------------------------


def test_ensemble_avec_une_piece_convertie(document: Any) -> None:
    pied = shaped_source(document, "Pied")
    planche = api.make_wood_part(600, 400, 18, "chene", mark="Plateau", doc=document)
    document.recompute()
    furniture, _ = api.make_furniture([planche, pied], "Table")
    document.recompute()
    rep = api.make_repeat([furniture], params(count=2, axis="X", step=900.0))
    [first, _second] = copies(rep)
    members = [m for m in bindings.members_of(first) if api.is_shaped_part(m)]
    assert len(members) == 1 and members[0].Source == pied.Source
    assert not set(DIMENSIONS) & set(engine(members[0]))
    assert [members[0].getPropertyByName(n).Value for n in DIMENSIONS] == list(SIZE)
    assert stale_or_invalid(document) == []


# --- S8 : liste de débit -------------------------------------------------------------------


def test_les_copies_se_regroupent_avec_la_source(document: Any) -> None:
    pied = shaped_source(document)
    rep = api.make_repeat([pied], params())
    (line,) = api.cut_list_of(document).lines
    assert line.quantity == 4
    assert set(line.marks) == {pied.Mark, *(c.Mark for c in copies(rep))}


# --- S9 : enregistrer, rouvrir, annuler, rétablir -------------------------------------------


def test_reouverture(document: Any, rouvrir: Reopen) -> None:
    pied = shaped_source(document)
    rep = api.make_repeat([pied], params())
    names = (pied.Name, rep.Name)
    engines = {c.Name: engine(c) for c in copies(rep)}
    doc = rouvrir(document)
    pied, rep = (doc.getObject(n) for n in names)
    doc.recompute()
    assert {c.Name: engine(c) for c in copies(rep)} == engines
    assert all(c.Source == pied.Source and c.Shape.isValid() for c in copies(rep))
    assert stale_or_invalid(doc) == []


def test_annulation_et_retablissement_en_un_bloc(undoable: Any) -> None:
    pied = shaped_source(undoable)
    before = {o.Name for o in undoable.Objects}
    api.make_repeat([pied], params())
    undoable.undo()
    assert {o.Name for o in undoable.Objects} == before and pied.ExpressionEngine == []
    undoable.redo()
    undoable.recompute()
    rep = undoable.getObject("Repeat")
    assert len(copies(rep)) == 3 and all(api.is_shaped_part(c) for c in copies(rep))
    assert stale_or_invalid(undoable) == []
