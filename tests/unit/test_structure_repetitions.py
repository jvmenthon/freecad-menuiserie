# SPDX-License-Identifier: LGPL-2.1-or-later
"""Panneau « Structure » et répétitions (ADR 0046, lot 4 ; ADR 0043 et 0044) : le vrai lecteur
(``DocumentRepetitions``) sur des objets simulés qui portent les vraies propriétés de la
répétition, l'arbre qu'il donne, les faits, le menu et la mise en évidence qui en découlent.

Les vraies répétitions de pièces et d'ensembles sont dans
``tests/integration/test_structure_repetitions.py``."""

from __future__ import annotations

import types
from collections.abc import Iterator
from typing import Any

import pytest

from freecad.menuiserie.core.structure_actions import (
    decide_dissociate,
    decide_drop,
    decide_rename_target,
    decide_selection,
)
from freecad.menuiserie.core.structure_highlight import Scope
from freecad.menuiserie.core.structure_menu import Action, menu_entries
from freecad.menuiserie.core.structure_tree import NodeKind, StructureNode, build_structure
from tests.unit.aides_debit_document import Doc, Obj, World
from tests.unit.aides_freecad import simulated_freecad

TIMES = chr(0x00D7)  # signe de multiplication des lignes de répétition


class Stage:
    """Un document simulé avec ses répétitions ; les copies portent les vraies propriétés."""

    def __init__(self, world: World, modules: types.SimpleNamespace) -> None:
        self.world = world
        self.modules = modules
        self.objects: list[Obj] = []

    def add(self, *objects: Obj) -> None:
        self.objects.extend(objects)

    def repeat(self, name: str, *sources: Obj) -> Obj:
        proxy = self.world._proxy("repeat", "Repeat")  # pylint: disable=protected-access
        repeat = Obj(name, "App::FeaturePython", Proxy=proxy, Source=list(sources), Label=name)
        self.add(repeat)
        return repeat

    def copy(
        self, name: str, repeat: Obj, source: Obj, index: int, owner: Obj | None = None
    ) -> Obj:
        """Copie de pièce de ``source``, membre de ``owner`` s'il est donné."""
        names = self.modules.repeat.COPY_PROPERTY_NAMES
        props: dict[str, Any] = dict.fromkeys(names)
        props.update(Repeat=repeat, RepeatSource=source, RepeatIndex=index)
        part = self.world.part(name, Label=name, **props)
        repeat.InList.append(part)
        if owner is not None:
            part.props.update(Furniture=owner, FurnitureBindings=[])
            owner.InList.append(part)
        self.add(part)
        return part

    def copy_furniture(self, name: str, repeat: Obj, source: Obj, index: int) -> Obj:
        """Ensemble copie de l'ensemble ``source`` (son contenu se pose avec :meth:`copy`)."""
        names = self.modules.repeat.COPY_PROPERTY_NAMES
        props: dict[str, Any] = dict.fromkeys(names)
        props.update(Repeat=repeat, RepeatSource=source, RepeatIndex=index, Label=name)
        furniture = self.world.furniture(name)
        furniture.props.update(props)
        repeat.InList.append(furniture)
        self.add(furniture)
        return furniture

    def doc(self) -> Doc:
        return Doc(*self.objects)

    def reader(self) -> Any:
        return self.modules.structure_repetitions.repetition_reader(self.doc())

    def roots(self) -> tuple[StructureNode, ...]:
        source = self.modules.structure_source.DocumentStructure(self.doc())
        return build_structure(source, source)

    def facts(self) -> Any:
        """Faits sans passer par ``foreign_objects`` (objets simulés sans liens)."""
        return self.modules.structure_facts.facts_of(self.doc())


@pytest.fixture(name="stage")
def stage_fixture(monkeypatch: pytest.MonkeyPatch) -> Iterator[Stage]:
    with simulated_freecad(monkeypatch):
        from freecad.menuiserie.features import (
            furniture,
            machined_part,
            repeat,
            structure_facts,
            structure_repetitions,
            structure_source,
            wood_part,
        )

        modules = types.SimpleNamespace(
            furniture=furniture,
            machined_part=machined_part,
            repeat=repeat,
            structure_facts=structure_facts,
            structure_repetitions=structure_repetitions,
            structure_source=structure_source,
            wood_part=wood_part,
        )
        yield Stage(World(modules), modules)


def keys(node: StructureNode) -> list[str]:
    return [n.key for n in node.walk() if n.key]


def all_keys(roots: tuple[StructureNode, ...]) -> list[str]:
    return [key for root in roots for key in keys(root)]


def free_piece_repeated(stage: Stage) -> tuple[Obj, Obj, Obj, Obj]:
    """Une planche libre répétée deux fois."""
    board = stage.world.part("Planche", Label="Planche")
    stage.add(board)
    repeat = stage.repeat("Repeat", board)
    first = stage.copy("Planche1", repeat, board, 1)
    second = stage.copy("Planche2", repeat, board, 2)
    return board, repeat, first, second


# --- Lecteur -----------------------------------------------------------------------------------


def test_lecteur_copies_de_premier_niveau_et_toutes_les_copies(stage: Stage) -> None:
    _board, _repeat, _first, _second = free_piece_repeated(stage)
    reader = stage.reader()
    assert reader.all_repetitions() == ["Repeat"]
    assert reader.container_of("Repeat") is None
    assert reader.copies_of("Repeat") == ["Planche1", "Planche2"]
    assert reader.every_copy() == ["Planche1", "Planche2"]
    assert reader.furniture_copies() == []


def test_lecteur_document_sans_repetition(stage: Stage) -> None:
    stage.add(stage.world.part("Planche"))
    reader = stage.reader()
    assert (reader.all_repetitions(), reader.every_copy(), reader.furniture_copies()) == (
        [],
        [],
        [],
    )


def test_lecteur_conteneur_est_l_ensemble_de_la_source(stage: Stage) -> None:
    shelf = stage.world.part("Etagere", Label="Etagere")
    desk = stage.world.furniture("Bureau", shelf)
    stage.add(desk, shelf)
    repeat = stage.repeat("Repeat", shelf)
    stage.copy("Etagere1", repeat, shelf, 1, owner=desk)
    assert stage.reader().container_of("Repeat") == "Bureau"


def test_lecteur_copie_interne_n_est_pas_une_ligne_de_la_repetition(stage: Stage) -> None:
    """Un ensemble répété : sa copie est une ligne ; la copie de son membre est dedans."""
    member = stage.world.part("Dessus", Label="Dessus")
    cabinet = stage.world.furniture("Caisson", member)
    stage.add(cabinet, member)
    repeat = stage.repeat("Repeat", cabinet)
    twin = stage.copy_furniture("Caisson1", repeat, cabinet, 1)
    inner = stage.copy("Dessus1", repeat, member, 1, owner=twin)
    reader = stage.reader()
    assert reader.copies_of("Repeat") == ["Caisson1"]
    assert reader.furniture_copies() == ["Caisson1"]
    assert reader.every_copy() == [twin.Name, inner.Name]


# --- Arbre -------------------------------------------------------------------------------------


def test_une_ligne_nom_x_n_depliable_en_ses_copies_sans_doublon(stage: Stage) -> None:
    free_piece_repeated(stage)
    roots = stage.roots()
    assert [(n.kind, n.label) for n in roots] == [
        (NodeKind.PIECE, "Planche"),
        (NodeKind.REPEAT, f"Repeat {TIMES}2"),
    ]
    repeat = roots[1]
    assert repeat.expanded is False
    assert [(c.kind, c.key) for c in repeat.children] == [
        (NodeKind.COPY, "Planche1"),
        (NodeKind.COPY, "Planche2"),
    ]
    shown = all_keys(roots)
    assert sorted(shown) == sorted(set(shown))  # aucune ligne en double
    assert not [n for n in roots if n.kind is NodeKind.LEFTOVERS]  # l'objet Répétition est là


def test_repetition_rangee_dans_l_ensemble_de_sa_source(stage: Stage) -> None:
    shelf = stage.world.part("Etagere", Label="Etagere")
    desk = stage.world.furniture("Bureau", shelf)
    desk.props["Label"] = "Bureau"
    stage.add(desk, shelf)
    repeat = stage.repeat("Repeat", shelf)
    stage.copy("Etagere1", repeat, shelf, 1, owner=desk)
    (root,) = stage.roots()
    assert root.kind is NodeKind.FURNITURE
    assert [(n.kind, n.key) for n in root.children] == [
        (NodeKind.PIECE, "Etagere"),
        (NodeKind.REPEAT, "Repeat"),
    ]
    assert [c.key for c in root.children[1].children] == ["Etagere1"]


def test_ensemble_copie_montre_son_contenu_sous_sa_ligne(stage: Stage) -> None:
    member = stage.world.part("Dessus", Label="Dessus")
    cabinet = stage.world.furniture("Caisson", member)
    cabinet.props["Label"] = "Caisson"
    stage.add(cabinet, member)
    repeat = stage.repeat("Repeat", cabinet)
    twin = stage.copy_furniture("Caisson1", repeat, cabinet, 1)
    inner = stage.copy("Dessus1", repeat, member, 1, owner=twin)
    roots = stage.roots()
    assert [(n.kind, n.key) for n in roots] == [
        (NodeKind.FURNITURE, "Caisson"),
        (NodeKind.REPEAT, "Repeat"),
    ]
    (copy,) = roots[1].children
    assert (copy.kind, copy.key, copy.expanded) == (NodeKind.COPY, "Caisson1", False)
    assert [(c.kind, c.key) for c in copy.children] == [(NodeKind.PIECE, inner.Name)]
    shown = all_keys(roots)
    assert sorted(shown) == sorted(set(shown))


# --- Faits, décisions et menu ---------------------------------------------------------------------


def test_faits_copies_internes_comprises_et_repetitions(stage: Stage) -> None:
    member = stage.world.part("Dessus", Label="Dessus")
    cabinet = stage.world.furniture("Caisson", member)
    stage.add(cabinet, member)
    repeat = stage.repeat("Repeat", cabinet)
    twin = stage.copy_furniture("Caisson1", repeat, cabinet, 1)
    stage.copy("Dessus1", repeat, member, 1, owner=twin)
    facts = stage.facts()
    assert facts.copies == frozenset({"Caisson1", "Dessus1"})
    assert facts.repeats == {"Repeat": "Repeat"}


def test_une_copie_ne_se_range_pas_ni_ne_recoit(stage: Stage) -> None:
    _board, _repeat, first, _second = free_piece_repeated(stage)
    shelf = stage.world.part("Etagere", Label="Etagere")
    desk = stage.world.furniture("Bureau", shelf)
    stage.add(desk, shelf)
    facts = stage.facts()
    assert not decide_drop(facts, [first.Name], "Bureau").allowed
    assert not decide_drop(facts, ["Planche"], first.Name).allowed
    assert not decide_selection(facts, [first.Name]).allowed


def test_une_repetition_ne_se_range_pas_mais_se_renomme(stage: Stage) -> None:
    _board, repeat, _first, _second = free_piece_repeated(stage)
    facts = stage.facts()
    assert not decide_drop(facts, [repeat.Name], None).allowed
    assert decide_rename_target(facts, [repeat.Name]).allowed


def test_menu_d_une_copie_modifier_et_dissocier(stage: Stage) -> None:
    _board, _repeat, first, _second = free_piece_repeated(stage)
    facts = stage.facts()
    entries = {e.action: e for e in menu_entries(facts, [first.Name])}
    assert entries[Action.OPEN].label == "Modifier la répétition"
    assert entries[Action.DISSOCIATE].decision.allowed
    assert entries[Action.RENAME].decision.allowed
    assert entries[Action.DELETE].decision.allowed
    assert not entries[Action.LEAVE].decision.allowed  # sortir de l'ensemble : refusé


def test_menu_d_une_pièce_ordinaire_sans_dissocier(stage: Stage) -> None:
    free_piece_repeated(stage)
    facts = stage.facts()
    actions = [e.action for e in menu_entries(facts, ["Planche"])]
    assert Action.DISSOCIATE not in actions
    assert menu_entries(facts, ["Planche"])[0].label == "Ouvrir"


def test_dissocier_refuse_hors_copie_ou_pendant_une_tache(stage: Stage) -> None:
    _board, _repeat, first, _second = free_piece_repeated(stage)
    facts = stage.facts()
    assert not decide_dissociate(facts, ["Planche"]).allowed
    assert not decide_dissociate(facts, []).allowed
    assert decide_dissociate(facts, [first.Name]).allowed
    busy = type(facts)(**{**facts.__dict__, "busy": True})
    assert not decide_dissociate(busy, [first.Name]).allowed


def test_la_repetition_met_en_evidence_toutes_ses_copies(stage: Stage) -> None:
    from freecad.menuiserie.features.highlight_targets import highlighted_objects

    _board, repeat, first, second = free_piece_repeated(stage)
    shown = highlighted_objects(repeat, Scope.COPIES)
    assert sorted(o.Name for o in shown) == [first.Name, second.Name]
    assert [o.Name for o in highlighted_objects(first, Scope.OBJECT)] == [first.Name]
