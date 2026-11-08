# SPDX-License-Identifier: LGPL-2.1-or-later
"""Cas limites de la répétition (revue du jalon #180) : pièce tournée, rangs après dissociation,
annulation après suppression, 100 copies assemblées, ensemble dans un ensemble."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

import pytest

from tests.integration.cadre import placement, stale_or_invalid

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
api = pytest.importorskip("freecad.menuiserie.api")
repeat = pytest.importorskip("freecad.menuiserie.features.repeat")


def bar(doc: Any, mark: str = "B", where: Any = None) -> Any:
    obj = api.make_wood_part(280, 40, 22, "chene", mark=mark, doc=doc)
    obj.Placement = where or placement(0, 0)
    doc.recompute()
    return obj


def copies(rep: Any) -> list[Any]:
    found: list[Any] = repeat.copies_of(rep)
    return found


def test_piece_tournee_de_45_degres_garde_sa_rotation_et_decale_sur_l_axe_global(
    document: Any,
) -> None:
    src = bar(document, where=placement(10, 20, 45))
    rep = api.make_repeat([src], api.RepeatParams(count=3, step=100.0, axis="X"))
    document.recompute()
    assert stale_or_invalid(document) == []
    for k, copy in enumerate(copies(rep), start=1):
        assert copy.Placement.Base.isEqual(App.Vector(10 + 100 * k, 20, 0), 1e-6)
        assert abs(copy.Placement.Rotation.Angle - src.Placement.Rotation.Angle) < 1e-9


def test_rangs_apres_dissociation_du_dernier_puis_ajout(document: Any) -> None:
    src = bar(document)
    rep = api.make_repeat([src], api.RepeatParams(count=3, step=100.0, axis="X"))
    last = copies(rep)[-1]
    api.dissociate(last)
    api.edit_repeat(rep, api.RepeatParams(count=3, step=100.0, axis="X"))
    document.recompute()
    live = copies(rep)
    xs = sorted(round(c.Placement.Base.x) for c in live)
    labels = [c.Label for c in live]
    assert len(set(labels)) == len(labels)
    assert len(set(xs)) == len(xs), (xs, labels)
    assert stale_or_invalid(document) == []


def test_rangs_apres_dissociation_au_milieu_puis_baisse(document: Any) -> None:
    src = bar(document)
    rep = api.make_repeat([src], api.RepeatParams(count=4, step=100.0, axis="X"))
    api.dissociate(copies(rep)[1])
    api.edit_repeat(rep, api.RepeatParams(count=2, step=100.0, axis="X"))
    document.recompute()
    assert stale_or_invalid(document) == []
    assert len(copies(rep)) <= 3


def test_dissocier_puis_modifier_source_et_pas(document: Any) -> None:
    src = bar(document)
    rep = api.make_repeat([src], api.RepeatParams(count=2, step=100.0, axis="X"))
    first, second = copies(rep)
    api.dissociate(first)
    kept = (first.Length.Value, first.Placement.Base.x)
    src.Length = 500
    rep.Step = 150
    document.recompute()
    assert (first.Length.Value, first.Placement.Base.x) == kept
    assert second.Length.Value == 500 and round(second.Placement.Base.x) == 300
    assert stale_or_invalid(document) == []


def test_undo_redo_dissocier_et_suppression_de_la_repetition(document: Any) -> None:
    document.UndoMode = 1
    src = bar(document)
    rep = api.make_repeat([src], api.RepeatParams(count=2, step=100.0, axis="X"))
    first = copies(rep)[0]
    api.dissociate(first)
    document.undo()
    document.recompute()
    assert repeat.is_copy(first) and stale_or_invalid(document) == []
    document.redo()
    document.recompute()
    assert not repeat.is_copy(first)
    document.openTransaction("sup")
    document.removeObject(rep.Name)
    document.commitTransaction()
    document.recompute()
    assert stale_or_invalid(document) == []
    document.undo()
    document.recompute()
    assert stale_or_invalid(document) == [] and len(copies(rep)) == 1


def test_cent_copies_assemblees_temps_et_validite(document: Any) -> None:
    low = api.make_wood_part(6000, 60, 22, "chene", mark="Basse", doc=document)
    bar_ = bar(document, where=placement(40, 60, 90))
    bar_.Placement = placement(40, 60, 90)
    document.recompute()
    api.make_mortise_tenon(low, bar_)
    document.recompute()
    start = time.perf_counter()
    rep = api.make_repeat([bar_], api.RepeatParams(count=100, step=50.0, axis="X"))
    created = time.perf_counter() - start
    assert len(copies(rep)) == 100
    start = time.perf_counter()
    rep.Step = 55
    document.recompute()
    print(f"\nTEMPS creation={created:.1f}s recalcul={time.perf_counter() - start:.1f}s")
    assert stale_or_invalid(document) == []


def test_pas_nul_ou_negatif_via_l_editeur(document: Any) -> None:
    src = bar(document)
    rep = api.make_repeat([src], api.RepeatParams(count=2, step=100.0, axis="X"))
    rep.Step = 0
    document.recompute()
    assert stale_or_invalid(document) == []
    rep.Step = -50
    document.recompute()
    assert stale_or_invalid(document) == []


def test_repeter_deux_fois_la_meme_source(document: Any) -> None:
    src = bar(document)
    api.make_repeat([src], api.RepeatParams(count=2, step=100.0, axis="X"))
    api.make_repeat([src], api.RepeatParams(count=2, step=100.0, axis="Y"))
    document.recompute()
    assert stale_or_invalid(document) == []
    assert src.Document.getObjectsByLabel(src.Label)


def test_enregistrer_rouvrir_puis_annuler_et_modifier(
    document: Any, rouvrir: Callable[[Any], Any]
) -> None:
    src = bar(document)
    rep = api.make_repeat([src], api.RepeatParams(count=2, step=100.0, axis="X"))
    names = (src.Name, rep.Name)
    doc = rouvrir(document)
    src, rep = (doc.getObject(n) for n in names)
    api.edit_repeat(rep, api.RepeatParams(count=4, step=80.0, axis="Y", reverse=True))
    assert len(copies(rep)) == 4 and stale_or_invalid(doc) == []
    assert round(copies(rep)[0].Placement.Base.y) == -80


def _carcass(doc: Any) -> Any:
    furniture, _ = api.make_carcass(doc, shelf_count=1)
    doc.recompute()
    return furniture


def test_vingt_caissons_copies_temps_et_validite(document: Any) -> None:
    source = _carcass(document)
    start = time.perf_counter()
    api.make_repeat([source], api.RepeatParams(count=20, step=650.0, axis="X"))
    created = time.perf_counter() - start
    start = time.perf_counter()
    source.Width = 700
    document.recompute()
    print(
        f"\nTEMPS 20 caissons creation={created:.1f}s recalcul={time.perf_counter() - start:.1f}s"
    )
    assert stale_or_invalid(document) == []


def test_ajouter_puis_annuler_puis_supprimer_un_ensemble_copie(document: Any) -> None:
    document.UndoMode = 1
    source = _carcass(document)
    rep = api.make_repeat([source], api.RepeatParams(count=2, step=700.0, axis="X"))
    first = next(c for c in copies(rep) if c.Label.startswith("Caisson"))
    api.edit_repeat(rep, api.RepeatParams(count=3, step=700.0, axis="X"))
    assert stale_or_invalid(document) == []
    document.undo()
    document.recompute()
    assert stale_or_invalid(document) == []
    document.openTransaction("sup ensemble copie")
    document.removeObject(first.Name)
    document.commitTransaction()
    document.recompute()
    assert stale_or_invalid(document) == []


def test_dissocier_ensemble_puis_supprimer_la_source_puis_rouvrir(
    document: Any, rouvrir: Callable[[Any], Any]
) -> None:
    source = _carcass(document)
    rep = api.make_repeat([source], api.RepeatParams(count=2, step=700.0, axis="X"))
    first, second = [c for c in copies(rep) if repeat.is_copy(c) and c.Label.startswith("Caisson")][
        :2
    ]
    api.dissociate(first)
    document.removeObject(source.Name)
    document.recompute()
    names = (first.Name, second.Name, rep.Name)
    doc = rouvrir(document)
    assert stale_or_invalid(doc) == [], [o.Name for o in doc.Objects if "Invalid" in o.State]
    assert all(doc.getObject(n) is not None for n in names[:2])
