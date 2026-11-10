# SPDX-License-Identifier: LGPL-2.1-or-later
"""Panneau « Structure » (ADR 0046, lot 4) : répétition « xN », liste de débit, autres objets.

Modèle pur (source simulée), lecture d'un document simulé, décisions du menu et du dépôt, et
garde-fous statiques : aucun objet d'un autre atelier n'est jamais modifié, ouvert ni supprimé.
"""

from __future__ import annotations

from collections.abc import Collection, Iterator, Sequence
from typing import Any, ClassVar

import pytest

from freecad.menuiserie.core.structure_actions import (
    DRAGGABLE_KINDS,
    NO_DROP_KINDS,
    MoveFacts,
    decide_create,
    decide_delete,
    decide_drop,
    decide_open,
    decide_rename_target,
    decide_selection,
    drop_blocked,
)
from freecad.menuiserie.core.structure_menu import Action, menu_entries
from freecad.menuiserie.core.structure_tree import (
    OTHERS_TITLE,
    REPEAT_LABEL,
    NodeKind,
    StructureNode,
    build_structure,
)
from tests.unit.aides import ROOT
from tests.unit.aides_debit_document import Doc, Obj, World, simulated_world
from tests.unit.test_structure_arbre import FakeSource, title

PACKAGE = ROOT / "freecad" / "menuiserie"
TIMES = "\u00d7"  # signe de multiplication des lignes de répétition


class FakeExtras:
    """Deux caissons répétés (copies C2, C3 : rangées dans le bureau), une liste de débit et deux
    objets d'un autre atelier."""

    def repetitions(self, container: str | None) -> Sequence[str]:
        return {"Bureau": ["R1"], None: ["R0"]}.get(container, [])

    def copies(self, repetition: str) -> Sequence[str]:
        return {"R1": ["P2", "P3"], "R0": []}[repetition]

    def all_copies(self) -> Collection[str]:
        return {"P2", "P3"}

    def cut_lists(self) -> Sequence[str]:
        return ["CL"]

    def other_objects(self) -> Sequence[str]:
        return ["Sk", "Box"]


class LotSource(FakeSource):
    LABELS: ClassVar[dict[str, str]] = {
        **FakeSource.LABELS,
        "R1": "Caisson",
        "R0": "Etagere",
        "CL": "Liste",
        "Sk": "A",
        "Box": "B",
    }


def tree(extras: object | None = FakeExtras()) -> tuple[StructureNode, ...]:
    return build_structure(LotSource(), title, extras)  # type: ignore[arg-type]


def test_sans_extras_l_arbre_est_celui_des_lots_precedents() -> None:
    assert tree(None) == build_structure(FakeSource(), title)


def test_repetition_une_seule_ligne_dependable_en_ses_copies() -> None:
    bureau = tree()[0]
    repeat = next(n for n in bureau.children if n.kind is NodeKind.REPEAT)
    assert (repeat.label, repeat.key, repeat.expanded) == (f"Caisson {TIMES}2", "R1", False)
    assert [(c.kind, c.key) for c in repeat.children] == [
        (NodeKind.COPY, "P2"),
        (NodeKind.COPY, "P3"),
    ]


def test_les_copies_ne_sont_pas_montrees_a_plat() -> None:
    flat = [n for n in tree()[0].children if n.kind is NodeKind.PIECE]
    assert [n.key for n in flat] == ["P1"]


def test_repetition_hors_ensemble_a_la_racine_et_zero_copie() -> None:
    root = next(n for n in tree() if n.kind is NodeKind.REPEAT)
    assert (root.label, root.children) == (f"Etagere {TIMES}0", ())


def test_ordre_des_racines() -> None:
    assert [n.kind for n in tree()] == [
        NodeKind.FURNITURE,
        NodeKind.PIECE,
        NodeKind.REPEAT,
        NodeKind.CUTLIST,
        NodeKind.OTHERS,
    ]


def test_liste_de_debit_une_ligne_sans_enfant() -> None:
    cut = next(n for n in tree() if n.kind is NodeKind.CUTLIST)
    assert (cut.label, cut.key, cut.children) == ("Liste", "CL", ())


def test_autres_objets_replies_et_comptes() -> None:
    others = tree()[-1]
    assert (others.kind, others.key, others.expanded) == (NodeKind.OTHERS, "", False)
    assert others.label == OTHERS_TITLE.format(count=2)
    assert [(c.kind, c.key) for c in others.children] == [
        (NodeKind.OTHER, "Sk"),
        (NodeKind.OTHER, "Box"),
    ]


def test_pas_de_noeud_autres_objets_sans_objet() -> None:
    class Empty(FakeExtras):
        def other_objects(self) -> Sequence[str]:
            return []

    assert all(n.kind is not NodeKind.OTHERS for n in tree(Empty()))


def test_gabarits_francais() -> None:
    assert REPEAT_LABEL.format(name="Caisson", count=3) == f"Caisson {TIMES}3"


def test_copies_seules_les_pieces_et_ensembles_se_glissent() -> None:
    assert NodeKind.COPY not in DRAGGABLE_KINDS
    assert NodeKind.REPEAT not in DRAGGABLE_KINDS
    assert NodeKind.OTHER not in DRAGGABLE_KINDS
    assert {NodeKind.REPEAT, NodeKind.COPY, NodeKind.OTHERS} <= NO_DROP_KINDS


def test_cles_uniques() -> None:
    keys = [n.key for root in tree() for n in root.walk() if n.key]
    assert len(keys) == len(set(keys))


# --- Décisions : copies, dépôt, objets d'autres ateliers ----------------------------------


def facts(**changes: Any) -> MoveFacts:
    base: dict[str, Any] = {
        "labels": {"Bureau": "Bureau", "P1": "Plateau", "P2": "Copie", "Loose": "Planche"},
        "furnitures": frozenset({"Bureau"}),
        "parent": {"P1": "Bureau", "P2": "Bureau"},
        "copies": frozenset({"P2"}),
        "foreign": frozenset({"Sk"}),
    }
    return MoveFacts(**{**base, **changes})


def test_une_copie_ne_se_range_ni_ne_se_sort() -> None:
    state = facts()
    assert not decide_drop(state, ["P2"], None).allowed
    assert "copie de répétition" in decide_drop(state, ["P2"], None).message
    assert not decide_drop(state, ["Loose", "P2"], "Bureau").allowed
    assert not decide_selection(state, ["P2"]).allowed
    assert not decide_create(state, ["P2"]).allowed


def test_on_ne_depose_rien_dans_une_copie_d_ensemble() -> None:
    state = facts(furnitures=frozenset({"Bureau", "P2"}))
    assert not decide_drop(state, ["Loose"], "P2").allowed
    assert decide_drop(state, ["Loose"], "Bureau").allowed
    destinations = next(e for e in menu_entries(state, ["Loose"]) if e.action is Action.ADD_TO)
    assert [e.target for e in destinations.children] == ["Bureau"]


def test_une_piece_normale_se_range_toujours() -> None:
    assert decide_drop(facts(), ["Loose"], "Bureau").allowed


def test_un_objet_d_un_autre_atelier_ne_se_touche_pas() -> None:
    state = facts()
    assert not decide_open(["Sk"], busy=False, foreign=state.foreign).allowed
    assert not decide_delete(["Sk"], busy=False, foreign=state.foreign).allowed
    assert not decide_rename_target(state, ["Sk"]).allowed
    assert not decide_drop(state, ["Sk"], "Bureau").allowed
    assert not decide_selection(state, ["Sk"]).allowed
    entries = {e.action: e.decision.allowed for e in menu_entries(state, ["Sk"])}
    assert entries == {
        Action.OPEN: False,
        Action.RENAME: False,
        Action.ADD_TO: False,
        Action.LEAVE: False,
        Action.CREATE: False,
        Action.DELETE: False,
    }


def test_repetition_et_liste_de_debit_s_ouvrent_et_se_suppriment() -> None:
    state = facts()
    assert decide_open(["R1"], busy=False, foreign=state.foreign).allowed
    assert decide_delete(["R1", "CL"], busy=False, foreign=state.foreign).allowed


def test_depot_sur_repetition_copie_liste_ou_autres_objets_refuse() -> None:
    furniture = (NodeKind.FURNITURE, "Bureau")
    for kind in (NodeKind.REPEAT, NodeKind.COPY, NodeKind.CUTLIST, NodeKind.OTHERS, NodeKind.OTHER):
        assert drop_blocked([(kind, "X"), furniture])
        assert drop_blocked([(kind, "X")])


def test_depot_permis_sur_ensemble_piece_assemblages_et_vide() -> None:
    furniture = (NodeKind.FURNITURE, "Bureau")
    assert drop_blocked([]) == ""
    assert drop_blocked([furniture]) == ""
    assert drop_blocked([(NodeKind.PIECE, "P1"), furniture]) == ""
    assert drop_blocked([(NodeKind.JOINTS, ""), furniture]) == ""
    assert drop_blocked([(NodeKind.PIECE, "Loose")]) == ""


# --- Lecture d'un document simulé ------------------------------------------------------------


@pytest.fixture
def world(monkeypatch: pytest.MonkeyPatch) -> Iterator[World]:
    with simulated_world(monkeypatch) as simulated:
        yield simulated


def cut_list(world: World, sheet: Obj | None = None) -> Obj:
    proxy = world.features.cutlist_object.CutListProxy.__new__(
        world.features.cutlist_object.CutListProxy
    )
    return Obj("CutList", "App::FeaturePython", Proxy=proxy, Label="Liste de débit", Sheet=sheet)


def sheet(doc_marker: bool = True) -> Obj:
    return Obj("CutListSheet", "Spreadsheet::Sheet", MenuiserieCutList=doc_marker)


def structure(world: World, objects: Sequence[Obj], reader: Any = None) -> Any:
    from freecad.menuiserie.features.structure_source import DocumentStructure, structure_of

    doc: Any = Doc(*objects)
    del world
    return (DocumentStructure(doc, reader), structure_of(doc))


def test_document_liste_de_debit_une_ligne_sans_son_tableur(world: World) -> None:
    listing, table = cut_list(world), sheet()
    table.InList.append(listing)
    _source, roots = structure(world, [listing, table])
    assert [(n.kind, n.label) for n in roots] == [(NodeKind.CUTLIST, "Liste de débit")]


def test_document_tableur_orphelin_de_l_atelier_cache(world: World) -> None:
    _source, roots = structure(world, [sheet()])
    assert roots == ()


def test_document_objet_d_un_autre_atelier_sous_autres_objets(world: World) -> None:
    blank = world.part("Planche", Label="Etagere")
    box = Obj("Box", "Part::Box", Label="Boite")
    _source, roots = structure(world, [blank, box])
    assert [(n.kind, n.label) for n in roots] == [
        (NodeKind.PIECE, "Etagere"),
        (NodeKind.OTHERS, "Autres objets (1)"),
    ]
    assert [(n.kind, n.key) for n in roots[1].children] == [(NodeKind.OTHER, "Box")]


def test_document_sources_de_pieces_en_forme_non_montrees(world: World) -> None:
    body = Obj("Body", "PartDesign::Body", Label="Corps")
    sketch = Obj("Sketch", "Sketcher::SketchObject", Label="Esquisse")
    shaped = Obj("Forme", "Part::FeaturePython", Source=body)
    body.InList.append(shaped)  # la pièce en forme lit le Body
    sketch.InList.append(body)  # le Body contient l'esquisse
    _source, roots = structure(world, [body, sketch])
    assert roots == ()


def test_document_objet_dont_depend_un_autre_n_est_pas_montre(world: World) -> None:
    operand = Obj("Box", "Part::Box")
    operand.InList.append(Obj("Cut", "Part::Cut"))
    _source, roots = structure(world, [operand])
    assert roots == ()


def test_document_origine_et_std_part_non_montres(world: World) -> None:
    blank = world.part("Planche", Label="Etagere")
    std_part = Obj("Part", "App::Part", OutList=[blank])
    origin = Obj("Origin", "App::Origin")
    _source, roots = structure(world, [std_part, origin, blank])
    assert [n.key for n in roots] == ["Planche"]


class Reader:
    """Lecteur de répétitions simulé : R répète Planche2 et Planche3 dans le bureau."""

    def all_repetitions(self) -> Sequence[str]:
        return ["R"]

    def container_of(self, repetition: str) -> str | None:
        return "Bureau"

    def copies_of(self, repetition: str) -> Sequence[str]:
        return ["Planche2", "Planche3", "Disparue"]


def test_document_repetition_par_le_point_d_extension(world: World) -> None:
    first, second, third = (world.part(n, Label=n) for n in ("Planche", "Planche2", "Planche3"))
    desk = world.furniture("Bureau", first, second, third)
    desk.props["Label"] = "Bureau"
    repeat = Obj("R", "App::FeaturePython", Label="Etagere")
    from freecad.menuiserie.features.structure_source import DocumentStructure

    objects: Any = [desk, first, second, third, repeat]
    doc: Any = Doc(*objects)
    from freecad.menuiserie.core.structure_tree import build_structure as build

    source = DocumentStructure(doc, Reader())
    roots = build(source, title, source)
    kinds = [(n.kind, n.label) for n in roots[0].children]
    assert kinds == [
        (NodeKind.PIECE, "Planche"),
        (NodeKind.REPEAT, f"Etagere {TIMES}2"),  # la copie « Disparue » n'existe plus : ignorée
    ]
    assert [c.key for c in roots[0].children[1].children] == ["Planche2", "Planche3"]


def test_document_sans_type_repetition_lecteur_vide(world: World) -> None:
    from freecad.menuiserie.features.structure_repetitions import NoRepetitions, repetition_reader

    assert isinstance(repetition_reader(Doc()), NoRepetitions)
    assert NoRepetitions().all_repetitions() == ()
    del world


def test_faits_copies_et_objets_d_autres_ateliers(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    from freecad.menuiserie.features import structure_facts

    first, second = world.part("Planche", Label="A"), world.part("Planche2", Label="B")
    desk = world.furniture("Bureau", first, second)
    box = Obj("Box", "Part::Box")
    monkeypatch.setattr(structure_facts, "repetition_reader", lambda _doc: Reader())
    state = structure_facts.facts_of(Doc(desk, first, second, box))
    assert (state.copies, state.foreign) == (frozenset({"Planche2"}), frozenset({"Box"}))


# --- Garde-fous statiques -------------------------------------------------------------------

READ_ONLY = (
    PACKAGE / "features" / "structure_foreign.py",
    PACKAGE / "features" / "structure_repetitions.py",
    PACKAGE / "core" / "structure_tree.py",
)


@pytest.mark.parametrize("path", READ_ONLY, ids=lambda path: path.name)
def test_modules_du_lot_4_sans_ecriture(path: Any) -> None:
    source = path.read_text(encoding="utf-8")
    for forbidden in ("ShowInTree", "claimChildren", "addObject", "addProperty", "openTransaction"):
        assert forbidden not in source
    assert "setEdit" not in source
    assert "FreeCADGui" not in source


def test_le_panneau_n_ouvre_pas_un_objet_d_un_autre_atelier() -> None:
    sync = (PACKAGE / "gui" / "structure_sync.py").read_text(encoding="utf-8")
    assert "NodeKind.OTHER.value" in sync
