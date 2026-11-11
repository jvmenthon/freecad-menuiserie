# SPDX-License-Identifier: LGPL-2.1-or-later
"""Panneau « Structure » (ADR 0046, lot 3) : menu contextuel (logique pure), lecture des faits d'un
document simulé, garde-fous statiques de l'interface."""

from __future__ import annotations

import ast
from collections.abc import Iterator
from typing import Any

import pytest

from freecad.menuiserie.core.structure_actions import (
    BUSY,
    MoveFacts,
)
from freecad.menuiserie.core.structure_menu import Action, menu_entries
from tests.unit.aides import ROOT
from tests.unit.aides_debit_document import Doc, World, simulated_world
from tests.unit.test_structure_actions import make_facts
from tests.unit.test_structure_arbre import joint_between

GUI = ROOT / "freecad" / "menuiserie" / "gui"
NEW_GUI = (GUI / "structure_actions.py", GUI / "structure_dnd.py")


# --- Menu ----------------------------------------------------------------------------------


def entries_of(facts: MoveFacts, *keys: str) -> dict[Action, Any]:
    return {entry.action: entry for entry in menu_entries(facts, list(keys))}


def test_menu_dans_l_ordre() -> None:
    order = [entry.action for entry in menu_entries(make_facts(), ["Plateau"])]
    assert order == [
        Action.OPEN,
        Action.RENAME,
        Action.ADD_TO,
        Action.LEAVE,
        Action.CREATE,
        Action.DELETE,
    ]


def test_menu_piece_libre_tout_est_possible() -> None:
    entries = entries_of(make_facts(links={}), "Planche")
    assert {action: entry.decision.allowed for action, entry in entries.items()} == {
        Action.OPEN: True,
        Action.RENAME: True,
        Action.ADD_TO: True,
        Action.LEAVE: False,  # déjà hors ensemble
        Action.CREATE: True,
        Action.DELETE: True,
    }
    assert entries[Action.LEAVE].decision.message == "« Planche » n'est dans aucun ensemble."


def test_menu_sous_menu_des_ensembles_avec_refus_expliques() -> None:
    add = entries_of(make_facts(), "Plateau")[Action.ADD_TO]
    assert [child.label for child in add.children] == ["Armoire", "Bureau", "Tiroir"]
    assert all(child.verbatim and child.action is Action.MOVE_INTO for child in add.children)
    by_target = {child.target: child.decision for child in add.children}
    assert by_target["Bureau"].message == "« Plateau » est déjà dans « Bureau »."
    assert "assemblée à « Joue »" in by_target["Armoire"].message
    assert "assemblée à « Joue »" in by_target["Tiroir"].message  # Joue reste dans Bureau


def test_menu_sans_ensemble_dans_le_document() -> None:
    facts = MoveFacts({"Planche": "Planche"}, frozenset(), {})
    add = entries_of(facts, "Planche")[Action.ADD_TO]
    assert (add.decision.allowed, add.children) == (False, ())
    assert add.decision.message == "Aucun ensemble dans le document."


def test_menu_sous_ensemble_depuis_des_membres() -> None:
    entries = entries_of(make_facts(), "Plateau", "Joue")
    assert entries[Action.CREATE].label.startswith("Créer un sous-ensemble")
    assert entries_of(make_facts(), "Planche")[Action.CREATE].label.startswith("Créer un ensemble")


def test_menu_sur_un_assemblage_seul_ouvrir_et_supprimer() -> None:
    entries = entries_of(make_facts(), "J1")
    allowed = {action for action, entry in entries.items() if entry.decision.allowed}
    assert allowed == {Action.OPEN, Action.DELETE}
    assert all(entries[a].decision.template for a in entries if a not in allowed)


def test_menu_panneau_de_tache_ouvert() -> None:
    entries = entries_of(make_facts(busy=True), "Plateau")
    refusals = {a: e.decision.template for a, e in entries.items() if not e.decision.allowed}
    assert refusals[Action.OPEN] == BUSY
    assert refusals[Action.DELETE] == BUSY
    assert entries[Action.RENAME].decision.allowed  # renommer ne dépend pas du panneau ouvert


def test_menu_selection_multiple_ouvrir_et_renommer_grises() -> None:
    entries = entries_of(make_facts(), "Plateau", "Joue")
    assert not entries[Action.OPEN].decision.allowed
    assert not entries[Action.RENAME].decision.allowed
    assert entries[Action.DELETE].decision.keys == ("Plateau", "Joue")


# --- Lecture d'un document simulé ----------------------------------------------------------


@pytest.fixture
def world(monkeypatch: pytest.MonkeyPatch) -> Iterator[World]:
    with simulated_world(monkeypatch) as simulated:
        yield simulated


def read_facts(*objects: Any) -> MoveFacts:
    from freecad.menuiserie.features.structure_facts import facts_of

    return facts_of(Doc(*objects))


def test_faits_cles_de_ligne_ensembles_et_appartenances(world: World) -> None:
    plate = world.part("Planche", Label="Plateau")
    machined = world.machined("Planche_usinee", plate, shape=None)
    loose = world.part("Libre", Label="Etagere")
    drawer_part = world.part("Fond", Label="Fond")
    drawer = world.furniture("Tiroir", drawer_part)
    desk = world.furniture("Bureau", plate, drawer)
    desk.props["Label"], drawer.props["Label"] = "Bureau", "Tiroir"
    facts = read_facts(desk, drawer, plate, machined, loose, drawer_part)
    assert facts.furnitures == {"Bureau", "Tiroir"}
    assert facts.parent == {"Planche_usinee": "Bureau", "Tiroir": "Bureau", "Fond": "Tiroir"}
    assert facts.labels["Planche_usinee"] == "Plateau"
    assert "Libre" in facts.labels
    assert "Libre" not in facts.parent
    assert not facts.busy


def test_faits_assemblages_dans_les_deux_sens_par_cle_de_ligne(world: World) -> None:
    left = world.part("G", Label="Joue")
    right = world.part("D", Label="Joue D")
    machined = world.machined("G_usinee", left, shape=None)
    joint = joint_between(world, "J", left, right)
    facts = read_facts(left, right, machined, joint)
    assert facts.links == {"G_usinee": {"D"}, "D": {"G_usinee"}}


def test_faits_un_assemblage_sans_deuxieme_piece_est_ignore(world: World) -> None:
    left = world.part("G", Label="Joue")
    joint = joint_between(world, "J", left, left)
    joint.props["GuestPart"] = None
    assert read_facts(left, joint).links == {}


def test_renommer_vise_la_brute_d_une_piece_usinee(world: World) -> None:
    from freecad.menuiserie.features.structure_facts import renamed_object

    blank = world.part("Planche", Label="Plateau")
    machined = world.machined("Planche_usinee", blank, shape=None)
    desk = world.furniture("Bureau", blank)
    assert renamed_object(machined) is blank
    assert renamed_object(blank) is blank
    assert renamed_object(desk) is desk


# --- Garde-fous de l'interface (analyse statique : les modules importent FreeCADGui) -------


@pytest.mark.parametrize("path", NEW_GUI, ids=lambda path: path.name)
def test_pas_de_modification_de_l_arbre_natif_ni_objet_ajoute(path: Any) -> None:
    """ADR 0046 : ni ShowInTree, ni claimChildren, ni objet ou propriété créés hors de l'api."""
    source = path.read_text(encoding="utf-8")
    for forbidden in ("ShowInTree", "claimChildren", "addObject", "addProperty", "removeObject"):
        assert forbidden not in source


def calls_in(path: Any) -> set[str]:
    return {
        node.func.attr
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }


def test_chaque_ecriture_passe_par_l_api_dans_une_transaction() -> None:
    source = (GUI / "structure_actions.py").read_text(encoding="utf-8")
    for call in ("api.remove_from_furniture", "api.add_to_furniture", "api.make_furniture"):
        assert call in source
    assert "openTransaction" in calls_in(GUI / "structure_actions.py")
    # jamais « retirer puis recréer » les propriétés de membre (FreeCAD 1.1 ne les rétablit pas
    # au Ctrl+Z) : changement d'ensemble et sortie gardent les propriétés
    assert "move=True" in source
    assert "keep_properties=True" in source
    assert "Std_Delete" in source
    assert "api.rename" in source  # M2 : « Renommer » aussi passe par l'api


def test_le_panneau_n_ecrit_aucun_libelle_lui_meme() -> None:
    """Règle S5 : toute écriture dans le document passe par l'api (ici ``api.rename``)."""
    for path in sorted(GUI.glob("structure_*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            targets = node.targets if isinstance(node, ast.Assign) else []
            for target in targets:
                assert not (isinstance(target, ast.Attribute) and target.attr == "Label"), path


def test_aucun_texte_visible_en_dur() -> None:
    texts = {"addAction", "addMenu", "setText", "setToolTip", "setStatusTip", "showText"}
    for path in NEW_GUI:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in texts
                and node.args
            ):
                assert not isinstance(node.args[0], ast.Constant), f"{path.name}:{node.lineno}"
