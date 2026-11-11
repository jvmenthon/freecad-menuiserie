# SPDX-License-Identifier: LGPL-2.1-or-later
"""Panneau « Structure » et vraies répétitions (ADR 0046, lot 4 ; ADR 0043 et 0044).

Pièces libres, pièces d'un ensemble et ensembles répétés avec ``api.make_repeat`` : une ligne
« <nom> xN » dépliable en ses copies (genres ``REPEAT`` et ``COPY``), à la racine ou dans
l'ensemble de la source, sans doublon avec les pièces ; l'ensemble copie montre son contenu et
jamais son Std Part ; faits, décisions, mise en évidence et dissociation.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

import pytest

from tests.integration.bureau import build_desk

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
api = pytest.importorskip("freecad.menuiserie.api")
shaped_sources = pytest.importorskip("freecad.menuiserie.features.shaped_sources")
structure_source = pytest.importorskip("freecad.menuiserie.features.structure_source")
structure_facts = pytest.importorskip("freecad.menuiserie.features.structure_facts")
highlight = pytest.importorskip("freecad.menuiserie.features.highlight_targets")
tree_module = pytest.importorskip("freecad.menuiserie.core.structure_tree")
actions_module = pytest.importorskip("freecad.menuiserie.core.structure_actions")
highlight_module = pytest.importorskip("freecad.menuiserie.core.structure_highlight")
menu_module = pytest.importorskip("freecad.menuiserie.core.structure_menu")
furniture_module = pytest.importorskip("freecad.menuiserie.features.furniture")
repeat_module = pytest.importorskip("freecad.menuiserie.features.repeat")

NodeKind = tree_module.NodeKind
TIMES = chr(0x00D7)


def board(document: Any, mark: str, **where: float) -> Any:
    part = api.make_wood_part(600, 300, 19, "chene", mark=mark, doc=document)
    part.Placement = App.Placement(App.Vector(*where.values()), App.Rotation())
    document.recompute()
    return part


def along(axis: str, count: int, step: float) -> Any:
    return api.RepeatParams(count=count, step=step, axis=getattr(api.RepeatAxis, axis))


def roots_of(document: Any) -> tuple[Any, ...]:
    return tuple(structure_source.structure_of(document))


def keys_of(roots: Any) -> list[str]:
    return [node.key for root in roots for node in root.walk() if node.key]


def copies_of(repeat: Any) -> list[Any]:
    """Copies de ``repeat`` par rang (``InList`` répète un objet autant de fois qu'il la cite)."""
    found: list[Any] = repeat_module.copies_of(repeat)
    return sorted(found, key=lambda copy: (copy.RepeatSource.Name, copy.RepeatIndex))


def assert_everything_once(document: Any) -> None:
    roots = roots_of(document)
    shown = Counter(keys_of(roots))
    expected = {
        structure_source.row_key_of(obj)
        for obj in document.Objects
        if shaped_sources.is_workshop_object(obj)
    }
    assert expected <= set(shown)
    assert [key for key, count in shown.items() if count > 1] == []
    assert all(root.kind is not NodeKind.LEFTOVERS for root in roots)
    assert not any(obj.Name in shown for obj in document.Objects if obj.TypeId == "App::Part")


def test_piece_libre_repetee_une_ligne_nom_x_n(document: Any) -> None:
    source = board(document, "Planche", x=0, y=0, z=0)
    repeat = api.make_repeat([source], along("X", 3, 700.0))
    document.recompute()
    roots = roots_of(document)
    kinds = [(root.kind, root.key) for root in roots]
    assert kinds == [(NodeKind.PIECE, source.Name), (NodeKind.REPEAT, repeat.Name)]
    line = roots[1]
    assert line.label == f"{repeat.Label} {TIMES}3"
    assert line.expanded is False
    assert [(c.kind, c.key) for c in line.children] == [
        (NodeKind.COPY, c.Name) for c in copies_of(repeat)
    ]
    assert_everything_once(document)


def test_repetition_d_un_membre_rangee_dans_l_ensemble(document: Any) -> None:
    desk = build_desk(document)
    shelf = board(document, "Etagere", x=0, y=0, z=100)
    api.add_to_furniture(desk.furniture, [shelf])
    repeat = api.make_repeat([shelf], along("Z", 2, 150.0))
    document.recompute()
    (root,) = [r for r in roots_of(document) if r.key == desk.furniture.Name]
    lines = [c for c in root.children if c.kind is NodeKind.REPEAT]
    assert [c.key for c in lines] == [repeat.Name]
    assert [c.key for c in lines[0].children] == [c.Name for c in copies_of(repeat)]
    assert not [c for c in root.children if c.kind is NodeKind.PIECE and c.key in keys_of(lines)]
    assert_everything_once(document)


def test_ensemble_repete_copie_complete_sans_std_part(document: Any) -> None:
    desk = build_desk(document)
    repeat = api.make_repeat([desk.furniture], along("Y", 1, 1500.0))
    document.recompute()
    (twin,) = [o for o in copies_of(repeat) if furniture_module.is_furniture(o)]
    roots = roots_of(document)
    line = next(r for r in roots if r.kind is NodeKind.REPEAT)
    (copy,) = line.children
    assert (copy.kind, copy.key) == (NodeKind.COPY, twin.Name)
    inner = [n.key for n in copy.walk() if n.key and n.key != twin.Name]
    assert inner  # le contenu de l'ensemble copie est sous sa ligne
    assert all(document.getObject(key).TypeId != "App::Part" for key in inner)
    assert not [r for r in roots if r.key == twin.Name]  # pas aussi à la racine
    assert_everything_once(document)


def test_faits_et_decisions_des_copies(document: Any) -> None:
    desk = build_desk(document)
    source = board(document, "Planche", x=2000, y=0, z=0)
    repeat = api.make_repeat([source], along("X", 2, 700.0))
    twin_repeat = api.make_repeat([desk.furniture], along("Y", 1, 1500.0))
    document.recompute()
    facts = structure_facts.facts_of(document)
    all_copies = {
        structure_source.row_key_of(o) for r in (repeat, twin_repeat) for o in copies_of(r)
    }
    assert all_copies <= set(facts.copies)  # les copies internes de l'ensemble copie aussi
    assert set(facts.repeats) == {repeat.Name, twin_repeat.Name}
    first = copies_of(repeat)[0]
    assert not actions_module.decide_drop(facts, [first.Name], desk.furniture.Name).allowed
    assert not actions_module.decide_drop(facts, [first.Name], None).allowed
    assert not actions_module.decide_drop(facts, [source.Name], first.Name).allowed
    assert not actions_module.decide_drop(facts, [repeat.Name], None).allowed
    assert actions_module.decide_rename_target(facts, [repeat.Name]).allowed
    assert actions_module.decide_dissociate(facts, [first.Name]).allowed
    entries = {e.action: e for e in menu_module.menu_entries(facts, [first.Name])}
    assert entries[menu_module.Action.OPEN].label == "Modifier la répétition"
    assert menu_module.Action.DISSOCIATE in entries


def test_renommer_la_repetition_et_une_copie(document: Any) -> None:
    source = board(document, "Planche", x=0, y=0, z=0)
    repeat = api.make_repeat([source], along("X", 2, 700.0))
    document.recompute()
    assert api.rename(repeat, "  Barreaux ") == "Barreaux"
    assert roots_of(document)[1].label == f"Barreaux {TIMES}2"
    with pytest.raises((TypeError, ValueError)):
        api.rename(repeat, "")
    assert api.rename(copies_of(repeat)[0], "Premier") == "Premier"


def test_mise_en_evidence_toutes_les_copies(document: Any) -> None:
    source = board(document, "Planche", x=0, y=0, z=0)
    repeat = api.make_repeat([source], along("X", 2, 700.0))
    desk = build_desk(document)
    twin_repeat = api.make_repeat([desk.furniture], along("Y", 1, 1500.0))
    document.recompute()
    scope = highlight_module.scope_of(NodeKind.REPEAT.value)
    assert scope is highlight_module.Scope.COPIES
    shown = highlight.highlighted_objects(repeat, scope)
    assert {o.Name for o in shown} == {o.Name for o in copies_of(repeat)}
    twin = next(o for o in copies_of(twin_repeat) if furniture_module.is_furniture(o))
    pieces = highlight.highlighted_objects(twin, highlight_module.scope_of(NodeKind.COPY.value))
    assert pieces
    assert not any(furniture_module.is_furniture(o) for o in pieces)


def test_dissocier_une_copie_la_remet_a_plat(document: Any) -> None:
    source = board(document, "Planche", x=0, y=0, z=0)
    repeat = api.make_repeat([source], along("X", 2, 700.0))
    document.recompute()
    first, second = copies_of(repeat)
    api.dissociate(first)
    document.recompute()
    roots = roots_of(document)
    line = next(r for r in roots if r.kind is NodeKind.REPEAT)
    assert line.label == f"{repeat.Label} {TIMES}1"
    assert [c.key for c in line.children] == [second.Name]
    assert (NodeKind.PIECE, first.Name) in [(r.kind, r.key) for r in roots]
    assert_everything_once(document)
