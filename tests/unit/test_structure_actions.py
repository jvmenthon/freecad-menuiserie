# SPDX-License-Identifier: LGPL-2.1-or-later
"""Panneau « Structure » (ADR 0046, lot 3) : décisions du glisser-déposer et du menu contextuel
(logique pure), lecture des faits d'un document simulé, garde-fous statiques de l'interface."""

from __future__ import annotations

import ast
from collections.abc import Iterator
from typing import Any

import pytest

from freecad.menuiserie.core.structure_actions import (
    BUSY,
    DRAGGABLE_KINDS,
    MAX_NAME_LENGTH,
    MoveFacts,
    cleaned_name,
    creates_sub_furniture,
    decide_create,
    decide_delete,
    decide_drop,
    decide_open,
    decide_rename,
    decide_rename_target,
    decide_selection,
    drop_target,
    top_level,
)
from freecad.menuiserie.core.structure_menu import Action, menu_entries
from freecad.menuiserie.core.structure_tree import NodeKind
from tests.unit.aides import ROOT
from tests.unit.aides_debit_document import Doc, World, simulated_world
from tests.unit.test_structure_arbre import joint_between

GUI = ROOT / "freecad" / "menuiserie" / "gui"
NEW_GUI = (GUI / "structure_actions.py", GUI / "structure_dnd.py")


def make_facts(**changes: Any) -> MoveFacts:
    """Bureau (Tiroir (Fond, Joue T), Plateau, Joue), Armoire (Etagere) et deux pièces libres.
    Plateau est assemblée à Joue (même ensemble), Joue T à Joue (Tiroir et Bureau) et Planche à
    Planche2 (toutes deux libres)."""
    parent = {
        "Tiroir": "Bureau",
        "Plateau": "Bureau",
        "Joue": "Bureau",
        "Fond": "Tiroir",
        "JoueT": "Tiroir",
        "Etagere": "Armoire",
    }
    labels = {key: key for key in (*parent, "Bureau", "Armoire", "Planche", "Planche2")}
    links = {
        "Plateau": {"Joue"},
        "Joue": {"Plateau", "JoueT"},
        "JoueT": {"Joue"},
        "Planche": {"Planche2"},
        "Planche2": {"Planche"},
    }
    fields: dict[str, Any] = {
        "labels": labels,
        "furnitures": frozenset({"Bureau", "Tiroir", "Armoire"}),
        "parent": parent,
        "links": {key: frozenset(value) for key, value in links.items()},
        **changes,
    }
    return MoveFacts(**fields)


def refused(facts: MoveFacts, keys: list[str], target: str | None) -> str:
    decision = decide_drop(facts, keys, target)
    assert not decision.allowed
    return decision.message


# --- Glisser-déposer : cas permis --------------------------------------------------------


def test_une_piece_libre_entre_dans_un_ensemble() -> None:
    decision = decide_drop(make_facts(), ["Etagere"], "Bureau")
    assert (decision.allowed, decision.keys) == (True, ("Etagere",))


def test_une_piece_libre_sans_assemblage_entre_dans_un_ensemble() -> None:
    facts = make_facts(links={})
    assert decide_drop(facts, ["Planche"], "Armoire").allowed


def test_une_piece_change_d_ensemble() -> None:
    facts = make_facts(links={})
    assert decide_drop(facts, ["Fond"], "Armoire").keys == ("Fond",)


def test_une_piece_sort_de_son_ensemble() -> None:
    facts = make_facts(links={})
    assert decide_drop(facts, ["Etagere"], None).keys == ("Etagere",)


def test_un_sous_ensemble_change_d_ensemble_avec_ses_pieces() -> None:
    """Fond et Joue T vont avec Tiroir ; Joue T est assemblée à Joue, restée dans Bureau."""
    facts = make_facts(links={"Fond": frozenset(), "JoueT": frozenset({"Fond"})})
    assert decide_drop(facts, ["Tiroir"], "Armoire").keys == ("Tiroir",)


def test_un_assemblage_entre_pieces_deplacees_ensemble_est_permis() -> None:
    facts = make_facts(links={"Plateau": frozenset({"Joue"}), "Joue": frozenset({"Plateau"})})
    assert decide_drop(facts, ["Plateau", "Joue"], "Armoire").keys == ("Plateau", "Joue")
    assert not decide_drop(make_facts(), ["Plateau", "Joue"], "Armoire").allowed  # Joue / Joue T


def test_un_assemblage_vers_une_piece_deja_dans_l_ensemble_d_arrivee_est_permis() -> None:
    facts = make_facts(links={"Etagere": frozenset({"Plateau"}), "Plateau": frozenset({"Etagere"})})
    assert decide_drop(facts, ["Etagere"], "Bureau").allowed


def test_un_assemblage_vers_un_sous_ensemble_de_l_arrivee_est_permis() -> None:
    facts = make_facts(links={"Etagere": frozenset({"Fond"}), "Fond": frozenset({"Etagere"})})
    assert decide_drop(facts, ["Etagere"], "Bureau").allowed


def test_une_piece_deja_en_place_est_ignoree_si_une_autre_bouge() -> None:
    facts = make_facts(links={})
    assert decide_drop(facts, ["Plateau", "Etagere"], "Bureau").keys == ("Etagere",)


def test_un_element_choisi_avec_son_ensemble_suit_l_ensemble() -> None:
    facts = make_facts(links={})
    assert decide_drop(facts, ["Fond", "Tiroir"], "Armoire").keys == ("Tiroir",)


# --- Glisser-déposer : refus expliqués ---------------------------------------------------


def test_refus_assemblage_vers_l_exterieur_en_entrant() -> None:
    text = refused(make_facts(), ["Plateau"], "Armoire")
    assert "« Plateau » est assemblée à « Joue »" in text
    assert "n'est pas dans « Armoire »" in text


def test_refus_assemblage_vers_une_piece_libre() -> None:
    text = refused(make_facts(), ["Planche"], "Armoire")
    assert "« Planche » est assemblée à « Planche2 »" in text


def test_refus_assemblage_vers_l_exterieur_en_sortant() -> None:
    text = refused(make_facts(), ["Plateau"], None)
    assert "reste dans « Bureau »" in text
    assert "Sortez les deux pièces ensemble" in text


def test_refus_assemblage_d_un_sous_ensemble_vers_l_exterieur() -> None:
    text = refused(make_facts(), ["Tiroir"], "Armoire")
    assert "« JoueT » est assemblée à « Joue »" in text


def test_une_piece_libre_assemblee_a_une_piece_libre_reste_libre() -> None:
    assert decide_drop(make_facts(), ["Planche", "Planche2"], "Armoire").allowed


def test_refus_cycle_dans_soi_meme() -> None:
    assert "« Bureau » ne peut pas entrer dans « Bureau »" in refused(
        make_facts(), ["Bureau"], "Bureau"
    )


def test_refus_cycle_dans_un_sous_ensemble() -> None:
    assert "« Bureau » ne peut pas entrer dans « Tiroir »" in refused(
        make_facts(), ["Bureau"], "Tiroir"
    )


def test_refus_deja_dans_l_ensemble() -> None:
    assert refused(make_facts(), ["Plateau"], "Bureau") == "« Plateau » est déjà dans « Bureau »."


def test_refus_deja_hors_ensemble() -> None:
    assert refused(make_facts(), ["Planche"], None) == "« Planche » n'est dans aucun ensemble."


def test_refus_rien_choisi() -> None:
    assert refused(make_facts(), [], "Bureau") == "Aucun élément choisi."


def test_refus_element_inconnu_autre_document() -> None:
    assert "ne se range pas" in refused(make_facts(), ["Ailleurs"], "Bureau")


def test_refus_ensemble_d_arrivee_inconnu() -> None:
    assert "ne se range pas" in refused(make_facts(), ["Planche"], "Ailleurs")


def test_refus_une_piece_n_est_pas_un_ensemble_d_arrivee() -> None:
    assert not decide_drop(make_facts(), ["Planche"], "Plateau").allowed


def test_refus_panneau_de_tache_ouvert() -> None:
    assert refused(make_facts(busy=True), ["Etagere"], "Bureau") == BUSY


def test_un_refus_ne_donne_aucune_cle_a_deplacer() -> None:
    assert decide_drop(make_facts(), ["Plateau"], "Armoire").keys == ()


def test_pas_de_boucle_sur_un_cycle_de_donnees() -> None:
    """Des ensembles qui se contiennent l'un l'autre (document corrompu) ne bouclent pas."""
    facts = make_facts(parent={"A": "B", "B": "A", "P": "A"}, labels=dict.fromkeys("ABP", "x"))
    facts = MoveFacts(facts.labels, frozenset("AB"), facts.parent)
    assert facts.chain("P") == ["A", "B"]
    assert facts.pieces_under("A") == {"P"}
    assert not decide_drop(facts, ["A"], "B").allowed


# --- Création, suppression, ouverture, renommage ------------------------------------------


def test_creer_depuis_des_pieces_libres() -> None:
    decision = decide_create(make_facts(), ["Planche", "Planche2"])
    assert (decision.allowed, creates_sub_furniture(make_facts(), decision.keys)) == (True, False)


def test_creer_un_sous_ensemble_depuis_des_membres_du_meme_ensemble() -> None:
    decision = decide_create(make_facts(), ["Plateau", "Joue"])
    assert (decision.allowed, creates_sub_furniture(make_facts(), decision.keys)) == (True, True)


def test_creer_refuse_un_melange() -> None:
    assert not decide_create(make_facts(), ["Plateau", "Planche"]).allowed
    assert not decide_create(make_facts(), ["Plateau", "Etagere"]).allowed


def test_creer_refuse_sans_selection_et_panneau_ouvert() -> None:
    assert not decide_create(make_facts(), []).allowed
    assert decide_create(make_facts(busy=True), ["Planche"]).template == BUSY


def test_creer_ne_controle_pas_les_assemblages() -> None:
    """Un sous-ensemble reste dans l'ensemble parent : l'assemblage y reste rangé."""
    assert decide_create(make_facts(), ["Plateau"]).allowed


def test_supprimer_et_ouvrir() -> None:
    assert decide_delete(["Plateau", "Plateau"], busy=False).keys == ("Plateau",)
    assert decide_delete([], busy=False).template
    assert decide_delete(["Plateau"], busy=True).template == BUSY
    assert decide_open(["Plateau"], busy=False).allowed
    assert not decide_open(["Plateau", "Joue"], busy=False).allowed
    assert not decide_open([], busy=False).allowed
    assert decide_open(["Plateau"], busy=True).template == BUSY


def test_selection_et_lignes_de_haut_niveau() -> None:
    facts = make_facts()
    assert top_level(facts, ["Fond", "Tiroir", "Plateau", "Plateau"]) == ["Tiroir", "Plateau"]
    assert decide_selection(facts, ["Fond", "Tiroir"]).keys == ("Tiroir",)
    assert not decide_selection(facts, ["J1"]).allowed


def test_renommer_une_seule_ligne_connue() -> None:
    facts = make_facts()
    assert decide_rename_target(facts, ["Plateau"]).allowed
    assert not decide_rename_target(facts, ["Plateau", "Joue"]).allowed
    assert not decide_rename_target(facts, []).allowed
    assert "Seuls les pièces" in decide_rename_target(facts, ["J1"]).message


@pytest.mark.parametrize(
    ("text", "allowed", "silent"),
    [
        ("", False, False),
        ("   ", False, False),
        ("Plateau", False, True),
        ("  Plateau  ", False, True),
        ("Dessus", True, False),
        ("x" * MAX_NAME_LENGTH, True, False),
        ("x" * (MAX_NAME_LENGTH + 1), False, False),
    ],
)
def test_renommer_bornes_du_nom(text: str, allowed: bool, silent: bool) -> None:
    decision = decide_rename("Plateau", text, furniture=False)
    assert (decision.allowed, decision.silent) == (allowed, silent)


@pytest.mark.parametrize("name", ["Bu>reau", "Bu\\reau", "Bu‮reau"])
def test_renommer_un_ensemble_refuse_un_nom_inutilisable_dans_une_expression(name: str) -> None:
    decision = decide_rename("Bureau", name, furniture=True)
    assert not decision.allowed
    assert "inutilisable dans une expression" in decision.message


def test_renommer_une_piece_accepte_ce_qu_un_ensemble_refuse() -> None:
    assert decide_rename("Plateau", "Bu>reau", furniture=False).allowed
    assert cleaned_name("  a  ") == "a"


def test_cible_d_un_depot_selon_la_ligne_visee() -> None:
    chain = [(NodeKind.PIECE, "P"), (NodeKind.FURNITURE, "Tiroir"), (NodeKind.FURNITURE, "Bureau")]
    assert drop_target(chain) == "Tiroir"
    assert drop_target([(NodeKind.FURNITURE, "Bureau")]) == "Bureau"
    assert (
        drop_target([(NodeKind.JOINT, "J"), (NodeKind.JOINTS, ""), (NodeKind.FURNITURE, "B")])
        == "B"
    )
    assert drop_target([(NodeKind.PIECE, "Planche")]) is None
    assert drop_target([]) is None


def test_on_ne_glisse_que_des_pieces_et_des_ensembles() -> None:
    assert {NodeKind.PIECE, NodeKind.FURNITURE} == DRAGGABLE_KINDS


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
    assert "assemblée à « Joue »" in by_target["Tiroir"].message


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
    assert "Std_Delete" in source


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
