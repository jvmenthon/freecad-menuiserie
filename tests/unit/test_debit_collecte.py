# SPDX-License-Identifier: LGPL-2.1-or-later
"""Collecte de la liste de débit sur des objets simulés (J2c : D1 à D8, hors forme réelle).

Liens, conteneurs, ensembles, doublons, boucles, ajouts d'après une boîte englobante, tourillons,
pièces illisibles. Les mêmes cas sur un vrai document sont dans
``tests/integration/test_liste_de_debit*.py``.
"""

from __future__ import annotations

import types
from collections.abc import Iterator
from typing import Any

import pytest

from freecad.menuiserie.core.part_model import Allowances
from tests.unit.aides_debit_document import (
    Doc,
    Obj,
    Shape,
    World,
    group,
    link,
    simulated_world,
)

# (xmin, xmax, ymin, ymax, zmin, zmax) d'une pièce de 800 x 200 x 22 sans ajout
PLAIN = (0.0, 800.0, 0.0, 200.0, 0.0, 22.0)


@pytest.fixture
def world(monkeypatch: pytest.MonkeyPatch) -> Iterator[World]:
    with simulated_world(monkeypatch) as simulated:
        yield simulated


def counts(world: World, doc: Doc, objects: list[Obj] | None = None) -> dict[str, int]:
    """Quantité collectée par nom de brute."""
    collected = world.features.cutlist_collect.collect(doc, objects)
    return {entry.source: entry.quantity for entry in collected.entries}


def kinds(world: World, doc: Doc, objects: list[Obj] | None = None) -> list[str]:
    """Natures des avertissements de la collecte."""
    collected = world.features.cutlist_collect.collect(doc, objects)
    return [notice.kind.value for notice in collected.notices]


# --- D1, D2 : pièces, pièces usinées, doublons ---------------------------------------------


def test_une_entree_par_brute_et_pieces_usinees_ramenees_a_leur_brute(world: World) -> None:
    board = world.part("WoodPart", "M1")
    shelf = world.part("WoodPart001", "M2")
    machined = world.machined("MachinedPart", board, Shape(PLAIN))
    doc = Doc(board, shelf, machined, Obj("Autre", "Part::Box"))
    assert counts(world, doc) == {"WoodPart": 1, "WoodPart001": 1}


def test_selection_sans_doublon(world: World) -> None:
    board = world.part("WoodPart", "M1")
    machined = world.machined("MachinedPart", board, Shape(PLAIN))
    shelf = world.part("WoodPart001", "M2")
    box = group("Part", board, shelf)
    doc = Doc(board, shelf, machined, box)
    assert counts(world, doc, [board, machined, box, box]) == {"WoodPart": 1, "WoodPart001": 1}
    assert counts(world, doc, [machined]) == {"WoodPart": 1}


def test_selection_vide_ou_none_couvre_le_document(world: World) -> None:
    board = world.part("WoodPart")
    doc = Doc(board)
    assert counts(world, doc, []) == counts(world, doc) == {"WoodPart": 1}


def test_objet_d_un_autre_document_refuse(world: World) -> None:
    board = world.part("WoodPart")
    Doc(board)
    other = Doc(world.part("WoodPart"))
    with pytest.raises(ValueError, match="autre document"):
        world.features.cutlist_collect.cut_list_of(other, [board])


def test_groupes_imbriques_et_origine_ignoree(world: World) -> None:
    board = world.part("WoodPart")
    inner = group("Group", board, Obj("Origin", "App::Origin"), type_id="App::DocumentObjectGroup")
    outer = group("Part", inner)
    assert counts(world, Doc(board, inner, outer), [outer]) == {"WoodPart": 1}


# --- D3 : liens ----------------------------------------------------------------------------


def test_chaque_lien_ajoute_une_occurrence_et_l_original_compte(world: World) -> None:
    board = world.part("WoodPart")
    doc = Doc(board, link("Link", board), link("Link001", board))
    assert counts(world, doc) == {"WoodPart": 3}


def test_tableau_de_liens_fois_element_count(world: World) -> None:
    board = world.part("WoodPart")
    element = Obj("Element", "App::LinkElement", LinkedObject=board)
    doc = Doc(board, link("Array", board, count=4), element)
    assert counts(world, doc) == {"WoodPart": 5}


def test_lien_vers_un_lien_suivi_et_multiplicateurs_composes(world: World) -> None:
    board = world.part("WoodPart")
    inner = link("Inner", board, count=3)
    outer = link("Outer", inner, count=2)
    assert counts(world, Doc(board, inner, outer), [outer]) == {"WoodPart": 6}


def test_lien_vers_std_part_ensemble_et_piece_usinee(world: World) -> None:
    board = world.part("WoodPart", "M1")
    machined = world.machined("MachinedPart", board, Shape(PLAIN))
    side = world.part("WoodPart001", "M2")
    cabinet = world.furniture("Furniture", side)
    box = group("Part", board)
    links = [link("L1", box), link("L2", cabinet), link("L3", machined)]
    doc = Doc(board, side, machined, box, cabinet, *links)
    assert counts(world, doc, links) == {"WoodPart": 2, "WoodPart001": 1}
    assert counts(world, doc) == {"WoodPart": 3, "WoodPart001": 2}


def test_lien_sans_cible_ignore(world: World) -> None:
    doc = Doc(link("Broken", None), world.part("WoodPart"))
    assert counts(world, doc) == {"WoodPart": 1}


def test_boucle_de_liens_bornee_avec_avertissement(world: World) -> None:
    first, second = link("A", None), link("B", None)
    first.props["LinkedObject"], second.props["LinkedObject"] = second, first
    board = world.part("WoodPart")
    assert counts(world, Doc(board, first, second)) == {"WoodPart": 1}
    assert "LinkTooDeep" in kinds(world, Doc(board, first, second))


# --- D6 : ensembles ------------------------------------------------------------------------


def test_ensemble_selectionne_donne_ses_membres_et_leur_libelle(world: World) -> None:
    side, top = world.part("WoodPart", "C"), world.part("WoodPart001", "D")
    cabinet = world.furniture("Furniture", side, top)
    cabinet.props["Label"] = "Caisson"
    spare = world.part("WoodPart002", "X")
    doc = Doc(side, top, spare, cabinet)
    collected = world.features.cutlist_collect.collect(doc, [cabinet])
    assert {e.source: e.furniture for e in collected.entries} == {
        "WoodPart": "Caisson",
        "WoodPart001": "Caisson",
    }
    assert counts(world, doc) == {"WoodPart": 1, "WoodPart001": 1, "WoodPart002": 1}
    free = world.features.cutlist_collect.collect(doc, [spare])
    assert free.entries[0].furniture == ""


def test_sous_ensemble_lu_recursivement(world: World) -> None:
    inner_part = world.part("WoodPart", "A")
    inner = world.furniture("Furniture001", inner_part)
    outer = world.furniture("Furniture", inner)
    doc = Doc(inner_part, inner, outer)
    assert counts(world, doc, [outer]) == {"WoodPart": 1}


# --- D4 : ajouts ---------------------------------------------------------------------------


def additions(world: World, shape: Shape) -> tuple[Allowances, list[str]]:
    board = world.part("WoodPart")
    world.machined("MachinedPart", board, shape)
    notices: list[Any] = []
    result = world.features.cutlist_parts.additions_of(board, notices)
    return result, [notice.kind.value for notice in notices]


@pytest.mark.parametrize(
    ("bounds", "expected"),
    [
        ((0.0, 860.0, 0.0, 200.0, 0.0, 22.0), Allowances(60, 0, 0)),
        ((-10.0, 830.0, 0.0, 200.0, 0.0, 22.0), Allowances(40, 0, 0)),
        ((0.0, 800.0, -3.0, 212.5, 0.0, 22.0), Allowances(0, 15.5, 0)),
        ((0.0, 800.0, 0.0, 200.0, -5.0, 27.0), Allowances(0, 0, 10)),
        ((0.0, 800.0000001, 0.0, 200.0, 0.0, 22.0), Allowances()),
        (PLAIN, Allowances()),
    ],
)
def test_ajouts_selon_la_boite_dans_le_repere_de_la_brute(
    world: World, bounds: tuple[float, ...], expected: Allowances
) -> None:
    result, notices = additions(world, Shape(bounds))
    assert result == expected
    assert notices == []


def test_retraits_ne_changent_rien(world: World) -> None:
    inside = (2.0, 790.0, 1.0, 199.0, 0.0, 22.0)
    assert additions(world, Shape(inside))[0] == Allowances()


def test_sans_piece_usinee_aucun_ajout(world: World) -> None:
    notices: list[Any] = []
    assert (
        world.features.cutlist_parts.additions_of(world.part("WoodPart"), notices) == Allowances()
    )
    assert notices == []


@pytest.mark.parametrize(
    "shape",
    [
        Shape(PLAIN, null=True),
        Shape(PLAIN, valid=False),
    ],
)
def test_forme_absente_ou_invalide_ajouts_nuls_et_avertissement(world: World, shape: Shape) -> None:
    result, notices = additions(world, shape)
    assert result == Allowances()
    assert notices == ["NoMachinedShape"]


def test_piece_usinee_en_erreur_ajouts_nuls_et_avertissement(world: World) -> None:
    board = world.part("WoodPart")
    machined = world.machined("MachinedPart", board, Shape((0, 860, 0, 200, 0, 22)))
    machined.State.append("Invalid")
    assert kinds(world, Doc(board, machined)) == ["NoMachinedShape"]


def test_ajouts_dans_l_entree_de_debit(world: World) -> None:
    board = world.part("WoodPart", "T1")
    machined = world.machined("MachinedPart", board, Shape((0, 860, 0, 200, 0, 22)))
    [entry] = world.features.cutlist_collect.collect(Doc(board, machined)).entries
    assert entry.additions == Allowances(60, 0, 0)
    assert entry.rough.length == 860


# --- D5 : tourillons -----------------------------------------------------------------------


def dowel_joint(host: Obj, guest: Obj) -> Obj:
    return Obj("Dowels", "Part::FeaturePython", HostPart=host, GuestPart=guest, Label="Tourillons")


def test_tourillons_effectifs_et_multiplicite(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    host, guest = world.part("WoodPart", "H"), world.part("WoodPart001", "G")
    joint = dowel_joint(host, guest)
    parts = world.features.cutlist_parts
    monkeypatch.setattr(world.features.cutlist_collect, "is_dowel_joint", lambda obj: obj is joint)
    values = types.SimpleNamespace(diameter=8.0, dowel_length=35.0, count=4)
    monkeypatch.setattr(parts, "resolved_for", lambda _joint: values)
    doc = Doc(host, guest, joint, link("L", host), link("L2", guest))
    collected = world.features.cutlist_collect.collect(doc)
    [item] = collected.hardware
    assert (item.diameter, item.length, item.quantity) == (8.0, 35.0, 4 * 2)
    only_host = world.features.cutlist_collect.collect(doc, [host])
    assert only_host.hardware == ()


def test_tourillons_impossibles_avertissement(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    host, guest = world.part("WoodPart"), world.part("WoodPart001")
    joint = dowel_joint(host, guest)
    parts = world.features.cutlist_parts

    def failing(_joint: Any) -> Any:
        raise ValueError("pièces trop minces")

    monkeypatch.setattr(parts, "resolved_for", failing)
    monkeypatch.setattr(world.features.cutlist_collect, "is_dowel_joint", lambda obj: obj is joint)
    doc = Doc(host, guest, joint)
    collected = world.features.cutlist_collect.collect(doc)
    assert collected.hardware == ()
    [notice] = collected.notices
    assert notice.kind.value == "UnreadableDowels"
    assert "pièces trop minces" in notice.message


# --- D7, D8 : pièces illisibles ------------------------------------------------------------


def test_categorie_inconnue_listee_avec_point_d_interrogation(world: World) -> None:
    future = world.part("WoodPart", "F1", Category="Composite", GrainDirection="Spiral")
    ok = world.part("WoodPart001", "M1")
    collected = world.features.cutlist_collect.collect(Doc(future, ok))
    names = {entry.source: entry.record.material_name for entry in collected.entries}
    assert names == {"WoodPart": "? Chêne", "WoodPart001": "Chêne"}
    assert [n.kind.value for n in collected.notices] == ["UnreadablePart"]
    assert "F1" not in collected.notices[0].message  # nommée par son libellé
    assert "WoodPart" in collected.notices[0].message


def test_cote_invalide_n_interrompt_pas_la_liste(world: World) -> None:
    broken = world.part("WoodPart", "B", size=(0, 200, 22), Label="Pièce cassée")
    ok = world.part("WoodPart001", "M1")
    collected = world.features.cutlist_collect.collect(Doc(broken, ok))
    assert [entry.source for entry in collected.entries] == ["WoodPart001"]
    [notice] = collected.notices
    assert notice.kind.value == "IgnoredPart"
    assert "Pièce cassée" in notice.message


def test_propriete_manquante_ignoree_avec_avertissement(world: World) -> None:
    broken = world.part("WoodPart")
    del broken.props["Density"]
    assert kinds(world, Doc(broken)) == ["IgnoredPart"]


def test_libelle_hostile_cite_sans_caractere_de_controle(world: World) -> None:
    broken = world.part("WoodPart", size=(0, 1, 1), Label="x\n‮" + "y" * 80)
    [notice] = world.features.cutlist_collect.collect(Doc(broken)).notices
    assert "\n" not in notice.message
    assert "‮" not in notice.message
    assert "…" in notice.message


# --- cut_list_of : regroupement et avertissements ------------------------------------------


def test_cut_list_regroupe_les_liens_et_garde_les_avertissements(world: World) -> None:
    board = world.part("WoodPart", "M1")
    future = world.part("WoodPart001", "F", Category="Composite")
    doc = Doc(board, future, link("L", board))
    cut_list = world.features.cutlist_collect.cut_list_of(doc)
    assert sorted((line.mark, line.quantity) for line in cut_list.lines) == [("F", 1), ("M1", 2)]
    assert cut_list.warnings[0].kind.value == "UnreadablePart"
