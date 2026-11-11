# SPDX-License-Identifier: LGPL-2.1-or-later
"""Répétition en grille d'ensembles (ADR 0045 et 0044) : même position relative par cellule, Std
Part par copie, assemblages internes recopiés, « Suivre le redimensionnement » sur deux axes."""

from __future__ import annotations

from typing import Any

import pytest

from tests.integration.aides_grille import Line, Reopen, X, Y, Z, grid
from tests.integration.cadre import stale_or_invalid
from tests.integration.test_repetition_ensembles import (
    Meuble,
    above,
    bounds,
    caisson,
    corner,
    engine,
    joints,
    members,
)
from tests.integration.test_repetition_std_part import orphans, std_of, std_parts

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
api = pytest.importorskip("freecad.menuiserie.api")
repeat = pytest.importorskip("freecad.menuiserie.features.repeat")


def two_by_two(columns: int = 2, rows: int = 2, **values: Any) -> Any:
    """Caissons de 600 x 400 tous les 700 mm sur X et tous les 500 mm sur Y."""
    return grid(Line(X, columns, 700.0), Line(Y, rows, 500.0), **values)


def tops(rep: Any, source: Any) -> dict[tuple[int, int, int], Any]:
    return {repeat.cell_of(c): c for c in repeat.copies_of(rep, source)}


@pytest.fixture
def undoable(document: Any) -> Any:
    document.UndoMode = 1
    return document


def shifted(box: tuple[float, ...], dx: float, dy: float) -> tuple[float, ...]:
    return (box[0] + dx, box[1] + dx, box[2] + dy, box[3] + dy, box[4], box[5])


def test_chaque_cellule_a_son_ensemble_a_la_bonne_place(document: Any) -> None:
    source = caisson(document)
    rep = api.make_repeat([source], two_by_two())
    found = tops(rep, source)
    assert sorted(found) == [(0, 1, 0), (1, 0, 0), (1, 1, 0)]
    assert [c.Label for c in repeat.copies_of(rep, source)] == [f"Caisson {k}" for k in (2, 3, 4)]
    for (i, j, _k), copy in found.items():
        assert corner(copy) == (700.0 * i, 500.0 * j, 0.0)
        assert api.repeat_of(copy) == rep and copy.Width.Value == source.Width.Value
        assert len(members(copy)) == len(members(source))
    assert stale_or_invalid(document) == []


def test_meme_position_relative_pour_chaque_membre_et_chaque_cellule(document: Any) -> None:
    source = caisson(document)
    rep = api.make_repeat([source], two_by_two())
    originals = {m.Name: bounds(m) for m in members(source)}
    for (i, j, _k), copy in tops(rep, source).items():
        for piece in members(copy):
            assert repeat.cell_of(piece) == (i, j, 0)
            assert bounds(piece) == shifted(
                originals[piece.RepeatSource.Name], 700.0 * i, 500.0 * j
            )


def test_assemblages_internes_recopies_par_cellule(document: Any) -> None:
    source = caisson(document)
    own = len(joints(document))
    rep = api.make_repeat([source], two_by_two())
    assert len(joints(document)) == own * 4  # l'original et ses trois copies
    for joint in joints(document):
        host, guest = joint.HostPart, joint.GuestPart
        if repeat.is_copy(host) or repeat.is_copy(guest):
            assert repeat.cell_of(host) == repeat.cell_of(guest) and host.Repeat == rep
    assert stale_or_invalid(document) == []


def test_la_source_redimensionnee_redimensionne_toutes_les_copies(document: Any) -> None:
    source = caisson(document)
    rep = api.make_repeat([source], two_by_two())
    api.resize_furniture(source, width=800)
    assert {c.Width.Value for c in tops(rep, source).values()} == {800.0}
    assert stale_or_invalid(document) == []


def test_modifier_la_grille_garde_les_ensembles_conserves(document: Any) -> None:
    source = caisson(document)
    rep = api.make_repeat([source], two_by_two())
    names = {cell: (c.Name, std_of(c).Name) for cell, c in tops(rep, source).items()}
    assert len(names) == 3
    api.edit_repeat(rep, two_by_two(3, 2))
    after = tops(rep, source)
    assert len(after) == 5
    assert {cell: (c.Name, std_of(c).Name) for cell, c in after.items() if cell in names} == names
    assert corner(after[(2, 1, 0)]) == (1400.0, 500.0, 0.0) and orphans(document) == []
    assert len(std_parts(document)) == 6  # la source et ses cinq copies
    api.edit_repeat(rep, two_by_two(1, 2))  # une seule colonne : (0, 1, 0)
    assert sorted(tops(rep, source)) == [(0, 1, 0)] and orphans(document) == []
    assert len(std_parts(document)) == 2 and stale_or_invalid(document) == []


def test_dissocier_un_ensemble_de_la_grille(undoable: Any) -> None:
    source = caisson(undoable)
    rep = api.make_repeat([source], two_by_two())
    freed = tops(rep, source)[(1, 1, 0)]
    api.dissociate(freed)
    assert engine(freed) == {} and corner(freed) == (700.0, 500.0, 0.0)
    api.edit_repeat(rep, two_by_two(3, 3))
    found = tops(rep, source)
    assert (1, 1, 0) not in found and len(found) == 7
    undoable.undo()
    assert sorted(tops(undoable.getObject("Repeat"), source)) == [(0, 1, 0), (1, 0, 0)]
    undoable.recompute()
    assert stale_or_invalid(undoable) == []


def test_annuler_retablir_enregistrer_rouvrir(undoable: Any, rouvrir: Reopen) -> None:
    source = caisson(undoable)
    undoable.clearUndos()
    api.make_repeat([source], two_by_two())
    assert undoable.UndoNames == ["Répéter"]
    undoable.undo()
    assert undoable.getObject("Repeat") is None and len(std_parts(undoable)) == 1
    undoable.redo()
    undoable.recompute()
    assert stale_or_invalid(undoable) == []
    names = (source.Name, undoable.getObject("Repeat").Name)
    doc = rouvrir(undoable)
    source, rep = (doc.getObject(n) for n in names)
    assert sorted(tops(rep, source)) == [(0, 1, 0), (1, 0, 0), (1, 1, 0)]
    assert corner(tops(rep, source)[(1, 1, 0)]) == (700.0, 500.0, 0.0)
    api.resize_furniture(source, depth=450)
    assert {c.Depth.Value for c in tops(rep, source).values()} == {450.0}
    api.edit_repeat(rep, two_by_two(2, 3))
    assert len(tops(rep, source)) == 5 and stale_or_invalid(doc) == []


# --- « Suivre le redimensionnement » sur deux axes --------------------------------------------


def shelf_grid() -> Any:
    """Étagère répétée sur Z (3 éléments, pas 150) et sur Y (2 éléments, pas 15), pas suivis."""
    return grid(Line(Z, 3, 150.0), Line(Y, 2, 15.0), follow_resize=True)


def test_chaque_axe_suit_la_cote_de_l_ensemble_sur_son_axe(document: Any) -> None:
    meuble = Meuble(document)
    rep = api.make_repeat([meuble.shelf], shelf_grid())
    name = meuble.furniture.Name
    assert rep.FollowResize is True and rep.Spacing == "CountOnSpan"
    assert (rep.Axis, rep.Axis2) == ("Y", "Z")  # lignes triées X, Y, Z
    assert engine(rep) == {
        "Span": f"{name}.Depth - 5 mm",
        "Step": "(Span - 380 mm) / 1",
        "Span2": f"{name}.Height - 402 mm",
        "Step2": "(Span2 - 18 mm) / 2",
    }
    assert (rep.Step.Value, rep.Step2.Value) == (15.0, 150.0)  # rien ne bouge à l'écriture
    api.resize_furniture(meuble.furniture, height=900)
    assert (rep.Step.Value, rep.Step2.Value) == (15.0, 240.0)
    api.resize_furniture(meuble.furniture, depth=500)
    assert (rep.Step.Value, rep.Step2.Value) == (pytest.approx(115.0), 240.0)
    cells = {repeat.cell_of(c): c for c in repeat.copies_of(rep)}
    assert len(cells) == 5 and (rep.Count, rep.Count2) == (1, 2)  # les nombres ne changent pas
    shelf = meuble.shelf.Placement.Base
    assert cells[(0, 1, 2)].Placement.Base.y == pytest.approx(shelf.y + 115.0)
    assert cells[(0, 1, 2)].Placement.Base.z == pytest.approx(shelf.z + 480.0)
    assert above(meuble.shelf, 240.0, 480.0)[1] == pytest.approx(cells[(0, 0, 2)].Placement.Base.z)
    api.resize_furniture(meuble.furniture, width=800)  # la largeur n'est suivie par aucun axe
    assert (rep.Step.Value, rep.Step2.Value) == (pytest.approx(115.0), 240.0)
    assert stale_or_invalid(document) == []


def test_decocher_le_suivi_retire_les_expressions_de_toutes_les_lignes(document: Any) -> None:
    meuble = Meuble(document)
    rep = api.make_repeat([meuble.shelf], shelf_grid())
    api.edit_repeat(rep, grid(Line(Z, 3, 150.0), Line(Y, 2, 15.0)))
    assert rep.FollowResize is False and engine(rep) == {}
    api.resize_furniture(meuble.furniture, height=900)
    assert rep.Step2.Value == 150.0 and stale_or_invalid(document) == []


def test_suivi_refuse_hors_ensemble(document: Any) -> None:
    barreau = api.make_wood_part(30, 20, 10, "chene", mark="Seul", doc=document)
    document.recompute()
    before = len(document.Objects)
    with pytest.raises(ValueError, match="n'est membre d'aucun ensemble"):
        api.make_repeat([barreau], grid(Line(X, 2, 50.0), Line(Y, 2, 50.0), follow_resize=True))
    assert len(document.Objects) == before
