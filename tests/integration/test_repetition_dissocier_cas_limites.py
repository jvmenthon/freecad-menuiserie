# SPDX-License-Identifier: LGPL-2.1-or-later
"""Cas limites de « Dissocier la répétition » et des copies « Nom (n) » (ADR 0067, demande de jv du
2026-11-23) : grille, plusieurs sources, pièces en bois, ensemble, butée, noms, annuler et
rétablir, enregistrer et rouvrir, refus (transaction abandonnée)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from tests.integration.aides_grille import Line, X, Y, grid
from tests.integration.cadre import stale_or_invalid
from tests.integration.test_repetition_butee import face_at, on_span, piece
from tests.integration.test_repetition_ensembles import Meuble
from tests.integration.test_repetition_pieces_en_bois import shaped_source

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
api = pytest.importorskip("freecad.menuiserie.api")
repeat = pytest.importorskip("freecad.menuiserie.features.repeat")
repeat_links = pytest.importorskip("freecad.menuiserie.features.repeat_links")

Reopen = Callable[[Any], Any]
LINKED = ("Repeat", "RepeatSource", "RepeatIndex")


def source(doc: Any, mark: str = "Barreau") -> Any:
    part = api.make_wood_part(30, 20, 10, "chene", mark=mark, doc=doc)
    doc.recompute()
    return part


def copies(rep: Any, src: Any = None) -> list[Any]:
    found: list[Any] = repeat.copies_of(rep, src)
    return found


def engine(obj: Any) -> dict[str, str]:
    return {path.lstrip("."): text for path, text in obj.ExpressionEngine}


def free(copy: Any) -> bool:
    return not repeat.is_copy(copy) and not [p for p in LINKED if p in copy.PropertiesList]


def snapshot(doc: Any) -> list[tuple[str, str, tuple[tuple[str, str], ...]]]:
    return sorted((o.Name, o.Label, tuple(o.ExpressionEngine)) for o in doc.Objects)


@pytest.fixture
def undoable(document: Any) -> Any:
    document.UndoMode = 1
    return document


# --- Grille --------------------------------------------------------------------------------


def test_grille_toutes_les_cellules_libres_noms_uniques(undoable: Any) -> None:
    src = source(undoable)
    rep = api.make_repeat([src], grid(Line(X, 4, 100.0), Line(Y, 3, 150.0)))
    name, kept = rep.Name, copies(rep)
    assert len(kept) == 11
    where = {c.Name: (c.Placement.Base.x, c.Placement.Base.y) for c in kept}
    api.dissociate(kept[7])  # depuis une copie quelconque
    assert undoable.getObject(name) is None and all(free(c) for c in kept)
    assert {c.Name: (c.Placement.Base.x, c.Placement.Base.y) for c in kept} == where
    labels = [c.Label for c in kept]
    assert len(set(labels)) == 11 and labels[0] == "Barreau (2)" and labels[-1] == "Barreau (12)"
    assert stale_or_invalid(undoable) == []
    undoable.undo()
    undoable.recompute()
    assert undoable.getObject(name) is not None and all(repeat.is_copy(c) for c in kept)
    assert stale_or_invalid(undoable) == []


# --- Plusieurs sources ----------------------------------------------------------------------


def test_plusieurs_sources_toutes_les_copies_de_toutes_les_sources(undoable: Any) -> None:
    first, second = source(undoable, "Montant"), source(undoable, "Traverse")
    second.Placement = App.Placement(App.Vector(0, 500, 0), App.Rotation())
    undoable.recompute()
    rep = api.make_repeat([first, second], api.RepeatParams(count=2, step=100.0, axis="X"))
    name, a, b = rep.Name, copies(rep, first), copies(rep, second)
    assert [c.Label for c in a] == ["Montant (2)", "Montant (3)"]
    assert [c.Label for c in b] == ["Traverse (2)", "Traverse (3)"]
    api.dissociate(b[0])  # depuis une copie de la seconde source
    assert undoable.getObject(name) is None and all(free(c) for c in a + b)
    assert [c.Label for c in a + b] == [
        "Montant (2)",
        "Montant (3)",
        "Traverse (2)",
        "Traverse (3)",
    ]
    assert first.ExpressionEngine == [] and second.ExpressionEngine == []
    assert stale_or_invalid(undoable) == []


def test_source_supprimee_puis_dissocier_les_copies_restantes(undoable: Any) -> None:
    """Une source supprimée dissocie ses copies seules ; la répétition garde les autres et se
    dissocie ensuite."""
    first, second = source(undoable, "Montant"), source(undoable, "Traverse")
    rep = api.make_repeat([first, second], api.RepeatParams(count=2, step=100.0, axis="X"))
    name, left = rep.Name, copies(rep, second)
    undoable.removeObject(first.Name)
    assert undoable.getObject(name) is not None and all(repeat.is_copy(c) for c in left)
    api.dissociate(rep)
    assert undoable.getObject(name) is None and all(free(c) for c in left)
    assert stale_or_invalid(undoable) == []


# --- Pièces en bois ------------------------------------------------------------------------


def test_piece_en_bois_repere_et_libelle_en_parentheses_apres_dissociation(
    undoable: Any, rouvrir: Reopen
) -> None:
    pied = shaped_source(undoable)
    rep = api.make_repeat([pied], api.RepeatParams(count=2, step=300.0, axis="Y"))
    kept = copies(rep)
    assert [(c.Mark, c.Label) for c in kept] == [("Pied (2)", "Pied (2)"), ("Pied (3)", "Pied (3)")]
    names = [c.Name for c in kept]
    api.dissociate(rep)
    assert all(free(c) and c.Source == pied.Source for c in kept)
    assert [(c.Mark, c.Label) for c in kept] == [("Pied (2)", "Pied (2)"), ("Pied (3)", "Pied (3)")]
    undoable.recompute()
    assert stale_or_invalid(undoable) == []
    doc = rouvrir(undoable)
    assert [doc.getObject(n).Mark for n in names] == ["Pied (2)", "Pied (3)"]
    assert all(free(doc.getObject(n)) for n in names) and doc.getObject("Repeat") is None
    doc.recompute()
    assert stale_or_invalid(doc) == []


# --- Ensemble (Std Part) -------------------------------------------------------------------


def test_copies_membres_d_un_ensemble_restent_membres_et_suivent_l_ensemble(
    undoable: Any,
) -> None:
    """Défaut corrigé (revue, majeur) : une étagère répétée dans un caisson était refusée
    (« Liaisons impossibles ... cycle ») : FreeCAD gardait le lien retour de ``RepeatSource``
    retirée, et les copies étaient reliées une à une."""
    meuble = Meuble(undoable)
    rep = meuble.repeat()
    kept = copies(rep)
    api.dissociate(rep)
    assert all(free(c) and api.furniture_of(c) == meuble.furniture for c in kept)
    api.resize_furniture(meuble.furniture, width=700, height=800)
    undoable.recompute()
    assert [c.Length.Value for c in kept] == [664.0, 664.0]  # liaisons normales de l'ensemble
    assert stale_or_invalid(undoable) == []
    for _ in range(undoable.UndoNames.index("Dissocier la répétition") + 1):
        undoable.undo()
    undoable.recompute()
    assert all(repeat.is_copy(c) for c in kept) and stale_or_invalid(undoable) == []


# --- Butée ---------------------------------------------------------------------------------


def test_butee_la_repetition_supprimee_ne_laisse_aucune_reference(undoable: Any) -> None:
    barreau, butee = piece(undoable), piece(undoable, "Butee", (300, 0, 0))
    face = api.Stop(butee, face_at(butee, "X", 300.0))
    rep = api.make_repeat([barreau], on_span(4), stops={X: face})
    name, kept = rep.Name, copies(rep)
    placed = [c.Placement.Base.x for c in kept]
    api.dissociate(rep)
    assert undoable.getObject(name) is None
    assert [o for o in butee.InList if o.TypeId != "App::Origin"] == []
    assert [c.Placement.Base.x for c in kept] == placed
    butee.Placement = App.Placement(App.Vector(600, 0, 0), App.Rotation())
    undoable.recompute()
    assert [c.Placement.Base.x for c in kept] == placed  # la butée ne pilote plus rien
    assert stale_or_invalid(undoable) == []
    undoable.undo()  # le déplacement de la butée n'est pas une transaction
    undoable.recompute()
    assert undoable.getObject(name) is not None and undoable.getObject(name).Stop[0] == butee


# --- Noms ----------------------------------------------------------------------------------


def test_nom_change_a_la_main_garde_et_ancien_nom_renomme_quand_le_rang_change(
    document: Any,
) -> None:
    src = source(document, "B")
    rep = api.make_repeat([src], grid(Line(X, 3, 100.0), Line(Y, 2, 150.0)))
    kept = copies(rep)
    assert [c.Label for c in kept][-2:] == ["B (5)", "B (6)"]
    kept[2].Mark = "B 4"  # ancien nom automatique de son rang (3)
    kept[3].Mark = "Fond"  # nom choisi par l'utilisateur
    api.edit_repeat(rep, grid(Line(X, 4, 100.0), Line(Y, 2, 150.0)))
    document.recompute()
    by_cell = {repeat.cell_of(c): c for c in copies(rep)}
    assert by_cell[(0, 1, 0)].Label == "B (5)"  # ancien nom suivi : rang 3 -> 4
    assert by_cell[(1, 1, 0)].Label == "Fond" and by_cell[(1, 1, 0)].RepeatIndex == 5
    labels = [c.Label for c in copies(rep)]
    assert len(set(labels)) == len(labels) and stale_or_invalid(document) == []
    api.dissociate(rep)
    assert by_cell[(1, 1, 0)].Label == "Fond"  # la dissociation ne renomme rien


def test_nom_de_copie_en_double_avec_un_libelle_deja_pris_ne_plante_pas(document: Any) -> None:
    """Une pièce libre déjà nommée « Barreau (3) » : la copie du rang 2 s'en distingue."""
    src = source(document)
    other = source(document, "Barreau (3)")
    rep = api.make_repeat([src], api.RepeatParams(count=3, step=100.0, axis="X"))
    labels = [c.Label for c in copies(rep)] + [other.Label]
    assert len(set(labels)) == len(labels) and stale_or_invalid(document) == []


def test_nom_apres_dissociation_puis_nouvelle_repetition_de_la_copie(document: Any) -> None:
    src = source(document)
    rep = api.make_repeat([src], api.RepeatParams(count=1, step=100.0, axis="X"))
    (freed,) = copies(rep)
    api.dissociate(rep)
    again = api.make_repeat([freed], api.RepeatParams(count=1, step=100.0, axis="X"))
    (grandchild,) = copies(again)
    assert grandchild.Label == "Barreau (2) (2)" and stale_or_invalid(document) == []


# --- Annuler, rétablir, enregistrer, rouvrir -----------------------------------------------


def test_annuler_retablir_annuler_a_l_identique(undoable: Any) -> None:
    rep = api.make_repeat([source(undoable)], api.RepeatParams(count=3, step=100.0, axis="Y"))
    name, kept = rep.Name, copies(rep)
    before = snapshot(undoable)
    api.dissociate(rep)
    after = snapshot(undoable)
    assert undoable.UndoNames[0] == "Dissocier la répétition" and after != before
    undoable.undo()
    assert snapshot(undoable) == before and all(repeat.is_copy(c) for c in kept)
    undoable.redo()
    assert undoable.getObject(name) is None and all(free(c) for c in kept)
    assert snapshot(undoable) == after
    undoable.undo()
    assert snapshot(undoable) == before
    undoable.recompute()
    assert stale_or_invalid(undoable) == []


def test_dissocier_deux_fois_refuse_la_seconde(document: Any) -> None:
    rep = api.make_repeat([source(document)], api.RepeatParams(count=2, step=100.0, axis="Y"))
    kept = copies(rep)
    api.dissociate(rep)
    for obj in kept:
        with pytest.raises(TypeError, match="ni une répétition ni une copie liée"):
            api.dissociate(obj)


def test_enregistrer_rouvrir_apres_dissociation_en_grille(undoable: Any, rouvrir: Reopen) -> None:
    rep = api.make_repeat([source(undoable)], grid(Line(X, 3, 100.0), Line(Y, 2, 150.0)))
    names = [c.Name for c in copies(rep)]
    api.dissociate(rep)
    doc = rouvrir(undoable)
    assert [o for o in doc.Objects if repeat.is_repeat(o)] == []
    kept = [doc.getObject(n) for n in names]
    assert all(c is not None and free(c) and c.ExpressionEngine == [] for c in kept)
    assert len({c.Label for c in kept}) == len(kept)
    kept[0].Length = 77
    doc.recompute()
    assert kept[0].Length.Value == 77.0 and stale_or_invalid(doc) == []


def test_rouvrir_puis_dissocier(undoable: Any, rouvrir: Reopen) -> None:
    rep = api.make_repeat([source(undoable)], api.RepeatParams(count=3, step=100.0, axis="Y"))
    names, rep_name = [c.Name for c in copies(rep)], rep.Name
    doc = rouvrir(undoable)
    doc.UndoMode = 1
    api.dissociate(doc.getObject(names[1]))
    assert all(free(doc.getObject(n)) for n in names) and doc.getObject(rep_name) is None
    assert stale_or_invalid(doc) == []


# --- Refus : la transaction est abandonnée, rien ne reste -----------------------------------


def test_refus_en_cours_de_route_abandonne_tout(
    undoable: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Liaisons impossibles (cycle) sur la 2e copie : ``ValueError``, aucune copie dissociée, la
    répétition reste, aucune entrée d'annulation ajoutée."""
    rep = api.make_repeat([source(undoable)], api.RepeatParams(count=3, step=100.0, axis="Y"))
    kept = copies(rep)
    before, undo_names = snapshot(undoable), list(undoable.UndoNames)
    real = repeat_links.unlink_copy
    calls: list[str] = []

    def failing(copy: Any, **kwargs: Any) -> None:
        calls.append(copy.Name)
        if len(calls) == 2:
            raise ValueError("Liaisons impossibles : cycle")
        real(copy, **kwargs)

    monkeypatch.setattr(repeat_links, "unlink_copy", failing)
    with pytest.raises(ValueError, match="cycle"):
        api.dissociate(rep)
    assert len(calls) == 2
    assert snapshot(undoable) == before and list(undoable.UndoNames) == undo_names
    assert all(repeat.is_copy(c) for c in kept) and "Placement.Base.y" in engine(kept[0])
    undoable.recompute()
    assert stale_or_invalid(undoable) == []
    monkeypatch.setattr(repeat_links, "unlink_copy", real)
    api.dissociate(rep)  # la transaction suivante s'ouvre normalement
    assert all(free(c) for c in kept)


def test_refus_dans_une_transaction_de_l_appelant_laisse_la_main_a_l_appelant(
    undoable: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``transaction=False`` (commande, panneau Structure) : l'api n'abandonne rien elle-même ;
    l'appelant abandonne sa transaction et le document revient à l'état d'avant."""
    rep = api.make_repeat([source(undoable)], api.RepeatParams(count=2, step=100.0, axis="Y"))
    kept = copies(rep)
    before = snapshot(undoable)

    def failing(_copy: Any, **_kwargs: Any) -> None:
        raise ValueError("Liaisons impossibles : cycle")

    undoable.openTransaction("Dissocier la répétition")
    monkeypatch.setattr(repeat_links, "unlink_copy", failing)
    with pytest.raises(ValueError, match="cycle"):
        api.dissociate(rep, transaction=False)
    undoable.abortTransaction()
    assert snapshot(undoable) == before and all(repeat.is_copy(c) for c in kept)
    assert stale_or_invalid(undoable) == []
