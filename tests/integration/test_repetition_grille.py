# SPDX-License-Identifier: LGPL-2.1-or-later
"""Répétition en grille X x Y x Z de pièces (ADR 0045, ``docs/specs/repetition.md`` § Grille).

Création (exemple 4 x 3 : 11 copies), modes de saisie, sens par axe, bornes, édition sans
renumérotation des cellules, dissociation, annuler et rétablir, enregistrer et rouvrir, document
d'avant la grille. Assemblages et ensembles : ``test_repetition_grille_assemblages.py`` et
``test_repetition_grille_ensembles.py``.
"""

from __future__ import annotations

from typing import Any

import pytest

from tests.integration.aides_grille import Line, Reopen, X, Y, Z, grid
from tests.integration.cadre import stale_or_invalid

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
api = pytest.importorskip("freecad.menuiserie.api")
repeat = pytest.importorskip("freecad.menuiserie.features.repeat")


def four_by_three(**values: Any) -> Any:
    """4 x 3 sur X et Y, pas de 100 mm sur X et de 150 mm sur Y : 11 copies."""
    return grid(Line(X, 4, 100.0), Line(Y, 3, 150.0), **values)


def source(doc: Any, mark: str = "Barreau") -> Any:
    part = api.make_wood_part(30, 20, 10, "chene", mark=mark, doc=doc)
    doc.recompute()
    return part


def copies(rep: Any) -> list[Any]:
    found: list[Any] = repeat.copies_of(rep)
    return found


def cells(rep: Any) -> dict[tuple[int, int, int], Any]:
    return {repeat.cell_of(copy): copy for copy in copies(rep)}


def where(copy: Any) -> tuple[float, float, float]:
    base = copy.Placement.Base
    return (round(base.x, 6), round(base.y, 6), round(base.z, 6))


def engine(obj: Any) -> dict[str, str]:
    return {path.lstrip("."): text for path, text in obj.ExpressionEngine}


@pytest.fixture
def undoable(document: Any) -> Any:
    document.UndoMode = 1
    return document


# --- Création --------------------------------------------------------------------------------


def test_quatre_par_trois_donne_onze_copies(document: Any) -> None:
    rep = api.make_repeat([source(document)], four_by_three())
    found = cells(rep)
    assert len(found) == 11 and (rep.Count, rep.Count2, rep.Axis, rep.Axis2) == (3, 2, "X", "Y")
    assert rep.Axis3 == "None" and (rep.Step.Value, rep.Step2.Value) == (100.0, 150.0)
    assert set(found) == {(i, j, 0) for i in range(4) for j in range(3)} - {(0, 0, 0)}
    for (i, j, k), copy in found.items():
        assert where(copy) == (100.0 * i, 150.0 * j, 0.0 * k)
    assert [c.RepeatIndex for c in copies(rep)] == list(range(1, 12))  # ordre : X puis Y
    assert [c.Label for c in copies(rep)] == [f"Barreau {k}" for k in range(2, 13)]
    assert stale_or_invalid(document) == []


def test_trois_axes_et_sens_par_axe(document: Any) -> None:
    rep = api.make_repeat(
        [source(document)],
        grid(Line(X, 2, 50.0), Line(Y, 2, 40.0, reverse=True), Line(Z, 3, 30.0)),
    )
    assert len(copies(rep)) == 11 and (rep.Axis3, rep.Count3) == ("Z", 2)
    assert (rep.Reverse, rep.Reverse2, rep.Reverse3) == (False, True, False)
    assert where(cells(rep)[(1, 1, 2)]) == (50.0, -40.0, 60.0)
    assert where(cells(rep)[(0, 1, 0)]) == (0.0, -40.0, 0.0)


def test_un_axe_de_nombre_1_est_inactif(document: Any) -> None:
    rep = api.make_repeat([source(document)], grid(Line(X, 3, 100.0), Line(Y, 1, 150.0)))
    assert len(copies(rep)) == 2 and rep.Axis2 == "None"
    assert {where(c) for c in copies(rep)} == {(100.0, 0.0, 0.0), (200.0, 0.0, 0.0)}


def test_nombre_sur_une_longueur_par_axe(document: Any) -> None:
    rep = api.make_repeat(
        [source(document)],
        grid(
            Line(X, 4, span=330.0),
            Line(Y, 3, span=120.0),
            spacing=api.SpacingMode.COUNT_ON_SPAN,
        ),
    )  # cotes de la source : 30 sur X, 20 sur Y
    assert (rep.Step.Value, rep.Step2.Value) == (100.0, 50.0)
    assert (rep.Span.Value, rep.Span2.Value) == (330.0, 120.0)
    assert where(cells(rep)[(3, 2, 0)]) == (300.0, 100.0, 0.0)


def test_pas_sur_une_longueur_par_axe(document: Any) -> None:
    rep = api.make_repeat(
        [source(document)],
        grid(
            Line(X, step=100.0, span=330.0),
            Line(Z, step=35.0, span=95.0),
            spacing=api.SpacingMode.STEP_ON_SPAN,
        ),
    )  # X : floor((330 - 30) / 100) = 3 ; Z (cote 10) : floor(85 / 35) = 2
    assert (rep.Count, rep.Count2, rep.Axis2) == (3, 2, "Z")
    assert len(copies(rep)) == 11 and where(cells(rep)[(3, 0, 2)]) == (300.0, 0.0, 70.0)


# --- Bornes ---------------------------------------------------------------------------------


def test_total_au_dela_du_maximum_refuse_sans_rien_creer(undoable: Any) -> None:
    barreau = source(undoable)
    before = len(undoable.Objects)
    with pytest.raises(ValueError, match=r"11 x 10 donneraient 109 copies.*le maximum est 100"):
        api.make_repeat([barreau], grid(Line(X, 11, 40.0), Line(Y, 10, 30.0)))
    assert len(undoable.Objects) == before


def test_edition_refusee_ne_touche_a_rien(document: Any) -> None:
    rep = api.make_repeat([source(document)], four_by_three())
    names = [c.Name for c in copies(rep)]
    with pytest.raises(ValueError, match="le maximum est 100"):
        api.edit_repeat(rep, grid(Line(X, 20, 100.0), Line(Y, 20, 150.0)))
    assert [c.Name for c in copies(rep)] == names and (rep.Count, rep.Count2) == (3, 2)


def test_grille_de_cent_copies(document: Any) -> None:
    rep = api.make_repeat([source(document)], grid(Line(X, 10, 40.0), Line(Y, 10, 30.0)))
    assert len(copies(rep)) == 99 and stale_or_invalid(document) == []


# --- Édition : les cellules ne sont pas renumérotées -------------------------------------


def test_changer_le_nombre_d_un_axe_garde_les_copies_des_cellules(document: Any) -> None:
    rep = api.make_repeat([source(document)], four_by_three())
    before = {cell: copy.Name for cell, copy in cells(rep).items()}
    api.edit_repeat(rep, grid(Line(X, 5, 100.0), Line(Y, 3, 150.0)))
    after = {cell: copy.Name for cell, copy in cells(rep).items()}
    assert len(after) == 14 and (rep.Count, rep.Count2) == (4, 2)
    assert all(after[cell] == name for cell, name in before.items())  # mêmes objets, mêmes cellules
    assert {(4, 0, 0), (4, 1, 0), (4, 2, 0)} == set(after) - set(before)
    assert [c.RepeatIndex for c in copies(rep)] == list(range(1, 15))  # rangs d'affichage refaits
    assert [c.Label for c in copies(rep)] == [f"Barreau {k}" for k in range(2, 16)]
    assert stale_or_invalid(document) == []


def test_retirer_une_colonne_et_une_rangee(document: Any) -> None:
    rep = api.make_repeat([source(document)], four_by_three())
    kept = {cell: c.Name for cell, c in cells(rep).items() if cell[0] < 3 and cell[1] < 2}
    api.edit_repeat(rep, grid(Line(X, 3, 100.0), Line(Y, 2, 150.0)))
    assert {cell: c.Name for cell, c in cells(rep).items()} == kept
    assert len(document.findObjects("Part::FeaturePython")) == 6  # source + 5 copies
    assert stale_or_invalid(document) == []


def test_changer_le_pas_deplace_les_copies_conservees(document: Any) -> None:
    rep = api.make_repeat([source(document)], four_by_three())
    names = {cell: c.Name for cell, c in cells(rep).items()}
    api.edit_repeat(rep, grid(Line(X, 4, 60.0), Line(Y, 3, 150.0, reverse=True)))
    assert {cell: c.Name for cell, c in cells(rep).items()} == names
    assert where(cells(rep)[(3, 2, 0)]) == (180.0, -300.0, 0.0)
    rep.Step2 = 10.0  # éditeur de propriétés : les copies suivent
    document.recompute()
    assert where(cells(rep)[(3, 2, 0)]) == (180.0, -20.0, 0.0)


def test_une_copie_dissociee_ne_revient_pas(document: Any) -> None:
    rep = api.make_repeat([source(document)], four_by_three())
    freed = cells(rep)[(1, 1, 0)]
    api.dissociate(freed)
    assert not repeat.is_copy(freed) and len(copies(rep)) == 10
    api.edit_repeat(rep, grid(Line(X, 4, 100.0), Line(Y, 4, 150.0)))
    found = cells(rep)
    assert (1, 1, 0) not in found and len(found) == 14  # 16 cellules - l'original - la dissociée
    assert (rep.Count, rep.Count2) == (3, 3) and stale_or_invalid(document) == []
    assert where(freed) == (100.0, 150.0, 0.0)  # elle garde sa place


def test_passer_d_un_axe_a_un_autre_garde_les_copies(document: Any) -> None:
    rep = api.make_repeat([source(document)], api.RepeatParams(count=3, step=100.0, axis="X"))
    names = [c.Name for c in copies(rep)]
    api.edit_repeat(rep, api.RepeatParams(count=3, step=100.0, axis="Z"))
    assert [c.Name for c in copies(rep)] == names
    assert sorted(cells(rep)) == [(0, 0, 1), (0, 0, 2), (0, 0, 3)]
    assert [where(c) for c in copies(rep)][-1] == (0.0, 0.0, 300.0)


def test_une_grille_devient_un_axe_puis_revient(document: Any) -> None:
    rep = api.make_repeat([source(document)], four_by_three())
    api.edit_repeat(rep, grid(Line(Y, 3, 150.0)))
    assert sorted(cells(rep)) == [(0, 1, 0), (0, 2, 0)] and rep.Axis == "Y"
    assert (rep.Axis2, rep.Count2) == ("None", 0)
    api.edit_repeat(rep, four_by_three())
    assert len(copies(rep)) == 11 and stale_or_invalid(document) == []


# --- Annuler, rétablir -----------------------------------------------------------------------


def test_annuler_et_retablir_la_creation_et_l_edition(undoable: Any) -> None:
    rep = api.make_repeat([source(undoable)], four_by_three())
    api.edit_repeat(rep, grid(Line(X, 5, 100.0), Line(Y, 2, 150.0)))
    assert len(copies(rep)) == 9
    undoable.undo()
    rep = undoable.getObject("Repeat")
    assert len(cells(rep)) == 11 and (rep.Count, rep.Count2) == (3, 2)
    assert where(cells(rep)[(3, 2, 0)]) == (300.0, 300.0, 0.0)
    undoable.redo()
    rep = undoable.getObject("Repeat")
    assert len(cells(rep)) == 9 and (rep.Count, rep.Count2) == (4, 1)
    undoable.undo()
    undoable.undo()
    assert undoable.getObject("Repeat") is None and len(undoable.Objects) == 1
    undoable.redo()
    assert len(cells(undoable.getObject("Repeat"))) == 11
    undoable.recompute()
    assert stale_or_invalid(undoable) == []


# --- Enregistrer et rouvrir ---------------------------------------------------------------


def test_reouverture_conserve_la_grille(document: Any, rouvrir: Reopen) -> None:
    barreau = source(document)
    rep = api.make_repeat([barreau], four_by_three())
    api.dissociate(cells(rep)[(2, 1, 0)])
    names = (barreau.Name, rep.Name)
    engines = {c.Name: engine(c) for c in copies(rep)}
    doc = rouvrir(document)
    barreau, rep = (doc.getObject(n) for n in names)
    assert (rep.Axis, rep.Axis2, rep.Count, rep.Count2) == ("X", "Y", 3, 2)
    assert rep.getEditorMode("Count2") == ["ReadOnly"] and rep.getEditorMode("Step2") == []
    assert {c.Name: engine(c) for c in copies(rep)} == engines
    assert sorted(cells(rep)) == sorted(set(cells(rep)))  # RepeatCell relue
    assert len(cells(rep)) == 10 and (2, 1, 0) not in cells(rep)
    barreau.Length = 55
    rep.Step = 80
    doc.recompute()
    assert cells(rep)[(3, 2, 0)].Length.Value == 55.0 and where(cells(rep)[(3, 2, 0)])[0] == 240.0
    names_before = {cell: c.Name for cell, c in cells(rep).items()}
    api.edit_repeat(rep, grid(Line(X, 5, 80.0), Line(Y, 3, 150.0)))
    assert all(cells(rep)[cell].Name == name for cell, name in names_before.items())
    assert len(cells(rep)) == 13 and stale_or_invalid(doc) == []


def test_document_d_avant_la_grille(document: Any, rouvrir: Reopen) -> None:
    """Sans ``RepeatCell`` ni lignes 2 et 3 (documents de la répétition à un axe) : la cellule se
    déduit du rang, et l'on peut passer en grille sans refaire les copies."""
    barreau = source(document)
    rep = api.make_repeat([barreau], api.RepeatParams(count=3, step=100.0, axis="Y"))
    for copy in copies(rep):
        copy.removeProperty("RepeatCell")
    for name in ("Axis", "Count", "Step", "Span", "Reverse"):
        for suffix in ("2", "3"):
            rep.removeProperty(name + suffix)
    names = (barreau.Name, rep.Name)
    kept = [c.Name for c in copies(rep)]
    doc = rouvrir(document)
    rep = doc.getObject(names[1])
    assert "Axis2" in rep.PropertiesList  # recréées à la réouverture
    assert sorted(cells(rep)) == [(0, 1, 0), (0, 2, 0), (0, 3, 0)]
    api.edit_repeat(rep, grid(Line(Y, 4, 100.0), Line(X, 2, 60.0)))
    assert [c.Name for c in copies(rep)][:3] != [] and set(kept) <= {c.Name for c in copies(rep)}
    assert len(copies(rep)) == 7 and stale_or_invalid(doc) == []
    assert where(cells(rep)[(1, 3, 0)]) == (60.0, 300.0, 0.0)
