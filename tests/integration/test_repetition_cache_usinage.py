# SPDX-License-Identifier: LGPL-2.1-or-later
"""Caches de la répétition : formes usinées et plans d'assemblage (performance).

Une copie a la même brute et les mêmes enlèvements, dans son repère, que sa source : sa forme est
reprise du cache. Le résultat doit être celui du calcul sans cache, et toute modification de la
source doit changer la clé.
"""

from __future__ import annotations

from typing import Any

import pytest

from tests.integration.aides_grille import Line, X, Y, grid

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
api = pytest.importorskip("freecad.menuiserie.api")
machined_cache = pytest.importorskip("freecad.menuiserie.features.machined_cache")
plan_cache = pytest.importorskip("freecad.menuiserie.features.joints.plan_cache")
machined_part = pytest.importorskip("freecad.menuiserie.features.machined_part")
solids = pytest.importorskip("freecad.menuiserie.features.solids")


def signature(doc: Any) -> dict[str, tuple[float, tuple[float, ...], int, int]]:
    """Volume, boîte, nombre de faces et de solides de chaque pièce usinée, par nom."""
    found = {}
    for obj in doc.Objects:
        if machined_part.is_machined_part(obj):
            box = obj.Shape.BoundBox
            size = (box.XLength, box.YLength, box.ZLength, box.XMin, box.YMin, box.ZMin)
            found[obj.Name] = (
                round(obj.Shape.Volume, 6),
                tuple(round(value, 6) for value in size),
                len(obj.Shape.Faces),
                len(obj.Shape.Solids),
            )
    return found


def repeated_carcass(doc: Any) -> Any:
    furniture, _ = api.make_carcass(doc, shelf_count=1)
    doc.recompute()
    params = grid(Line(X, 2, 700.0), Line(Y, 2, 500.0))
    api.make_repeat([furniture], params)
    doc.recompute()
    return furniture


def test_copies_identiques_au_calcul_sans_cache(
    document: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    machined_cache.reset_machined_cache()
    plan_cache.reset_plan_cache()
    repeated_carcass(document)
    cached = signature(document)
    assert len(cached) > machined_cache.machined_cache_size() > 0  # des copies ont été reprises
    assert plan_cache.plan_cache_size() > 0

    def direct(base: Any, _key: Any, additions: Any, cuts: Any, trims: Any = ()) -> Any:
        return solids.machined_shape(base, additions, cuts, trims)

    monkeypatch.setattr(machined_part, "cached_machined_shape", direct)
    other = App.newDocument("SansCache")
    try:
        repeated_carcass(other)
        assert signature(other) == cached
    finally:
        App.closeDocument(other.Name)


def test_modifier_la_source_change_la_cle(document: Any) -> None:
    machined_cache.reset_machined_cache()
    furniture = repeated_carcass(document)
    before = signature(document)
    entries = machined_cache.machined_cache_size()
    furniture.Width = furniture.Width.Value + 50.0
    document.recompute()
    after = signature(document)
    assert after != before
    assert machined_cache.machined_cache_size() > entries
    machined_cache.reset_machined_cache()  # le résultat est le même sans aucun cache
    plan_cache.reset_plan_cache()
    for obj in document.Objects:
        if machined_part.is_machined_part(obj):
            obj.touch()
    document.recompute()
    assert signature(document) == after


def test_la_forme_rendue_n_est_pas_partagee(document: Any) -> None:
    machined_cache.reset_machined_cache()
    repeated_carcass(document)
    shapes = [o.Shape for o in document.Objects if machined_part.is_machined_part(o)]
    twins = [(a, b) for i, a in enumerate(shapes) for b in shapes[i + 1 :] if a.Volume == b.Volume]
    assert twins  # des pièces de même forme existent (les copies)
    assert not any(a.isSame(b) for a, b in twins)  # mais chacune a son propre objet OCC


def test_pas_change_formes_d_un_document_construit_avec_ce_pas(document: Any) -> None:
    """Un pas changé ne change que les placements : formes et boîtes sont celles d'un document
    construit directement avec ce pas (pièces usinées et assemblages)."""
    furniture, _ = api.make_carcass(document, shelf_count=1)
    document.recompute()
    rep = api.make_repeat([furniture], grid(Line(X, 2, 700.0)))
    document.recompute()
    api.edit_repeat(rep, grid(Line(X, 2, 900.0)))
    other = App.newDocument("PasDirect")
    try:
        furniture2, _ = api.make_carcass(other, shelf_count=1)
        other.recompute()
        api.make_repeat([furniture2], grid(Line(X, 2, 900.0)))
        other.recompute()
        assert sorted(signature(document).values()) == sorted(signature(other).values())
    finally:
        App.closeDocument(other.Name)


def test_annuler_puis_refaire_la_meme_saisie(document: Any) -> None:
    """Après une annulation qui restaure l'ancienne forme, la même saisie reconstruit la forme."""
    document.UndoMode = 1
    furniture = repeated_carcass(document)
    before = signature(document)
    width = furniture.Width.Value
    document.openTransaction("largeur")
    furniture.Width = width + 50.0
    document.recompute()
    document.commitTransaction()
    after = signature(document)
    document.undo()
    document.recompute()
    assert signature(document) == before
    document.openTransaction("largeur")
    furniture.Width = width + 50.0
    document.recompute()
    document.commitTransaction()
    assert signature(document) == after
