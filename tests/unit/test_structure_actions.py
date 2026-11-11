# SPDX-License-Identifier: LGPL-2.1-or-later
"""Panneau « Structure » (ADR 0046, lot 3) : décisions du glisser-déposer et du menu contextuel
(logique pure), lecture des faits d'un document simulé, garde-fous statiques de l'interface."""

from __future__ import annotations

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
    plain_tooltip,
    top_level,
)
from freecad.menuiserie.core.structure_decision import Move
from freecad.menuiserie.core.structure_tree import NodeKind
from tests.unit.aides import ROOT

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


def test_un_assemblage_vers_un_sous_ensemble_de_l_arrivee_range_dans_ce_sous_ensemble() -> None:
    """Etagere déposée sur Bureau, assemblée à Fond (Tiroir) : elle va dans Tiroir, comme Fond."""
    facts = make_facts(links={"Etagere": frozenset({"Fond"}), "Fond": frozenset({"Etagere"})})
    decision = decide_drop(facts, ["Etagere"], "Bureau")
    assert decision.allowed and decision.moves == (Move("Tiroir", ("Etagere",)),)
    assert "elle est rangée dans « Tiroir », comme « Fond »" in decision.notes[0].message
    direct = decide_drop(facts, ["Etagere"], "Tiroir")
    assert direct.moves == (Move("Tiroir", ("Etagere",)),) and direct.notes == ()


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
    assert "(« Armoire »)" in text


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


def test_deposer_sur_un_sous_ensemble_une_piece_assemblee_a_une_piece_du_parent() -> None:
    """Plateau et Joue sont dans Bureau, Plateau est déposée sur Tiroir (sous-ensemble de Bureau) :
    elle reste dans Bureau, avec Joue ; rien n'est rangé, la raison est donnée."""
    text = refused(make_facts(), ["Plateau"], "Tiroir")
    assert "« Plateau » est assemblée à « Joue » : elle reste dans « Bureau »" in text


def test_deposer_les_deux_pieces_assemblees_sur_le_sous_ensemble() -> None:
    """Plateau et Joue (avec Joue T, déjà dans Tiroir) vont ensemble dans Tiroir, sans note."""
    decision = decide_drop(make_facts(), ["Plateau", "Joue"], "Tiroir")
    assert decision.moves == (Move("Tiroir", ("Plateau", "Joue")),) and decision.notes == ()


def test_une_partie_assemblee_suit_sa_piece_et_l_autre_va_ou_on_veut() -> None:
    """Etagere (Armoire) et Planche (libre) sur Bureau : Planche, assemblée à Planche2 libre,
    reste hors ensemble ; Etagere entre dans Bureau."""
    decision = decide_drop(make_facts(), ["Etagere", "Planche"], "Bureau")
    assert decision.moves == (Move("Bureau", ("Etagere",)),)
    assert "reste hors ensemble avec elle" in decision.notes[0].message


def test_sortir_d_un_sous_ensemble_vers_le_parent_garde_l_assemblage() -> None:
    facts = make_facts(links={"JoueT": frozenset({"Plateau"}), "Plateau": frozenset({"JoueT"})})
    assert decide_drop(facts, ["JoueT"], "Bureau").allowed


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
    decision = decide_create(make_facts(), ["Plateau", "Joue", "Tiroir"])
    assert (decision.allowed, creates_sub_furniture(make_facts(), decision.keys)) == (True, True)


def test_creer_refuse_un_melange() -> None:
    assert not decide_create(make_facts(), ["Plateau", "Planche"]).allowed
    assert not decide_create(make_facts(), ["Plateau", "Etagere"]).allowed


def test_creer_avec_une_seule_piece_assemblee_a_une_piece_du_parent_ne_cree_rien() -> None:
    """Plateau seule resterait dans Bureau avec Joue : rien à créer, la raison est donnée."""
    text = decide_create(make_facts(), ["Plateau"]).message
    assert "Rien à créer : « Plateau » est assemblée à « Joue »" in text
    assert "reste dans « Bureau »" in text


def test_creer_laisse_dans_le_parent_la_piece_assemblee_a_une_piece_du_parent() -> None:
    facts = make_facts(
        links={"Plateau": frozenset({"Joue"}), "Joue": frozenset({"Plateau"})},
    )
    decision = decide_create(facts, ["Plateau", "Tiroir"])
    assert decision.allowed and decision.keys == ("Tiroir",)
    assert "elle reste dans « Bureau »" in decision.notes[0].message


def test_creer_refuse_un_assemblage_vers_un_sous_ensemble_voisin() -> None:
    """Joue (assemblée à Joue T, dans Tiroir) ne peut pas former un ensemble cohérent."""
    text = decide_create(make_facts(), ["Plateau", "Joue"]).message
    assert "autre ensemble" in text


def test_creer_permet_les_pieces_assemblees_choisies_ensemble_ou_hors_ensemble() -> None:
    assert decide_create(make_facts(), ["Plateau", "Joue", "Tiroir"]).allowed  # Joue T y est
    assert decide_create(make_facts(), ["Fond"]).allowed  # Fond n'est assemblée à rien
    # Planche est assemblée à Planche2, libre : l'api la range avec elle, sans refus
    assert decide_create(make_facts(), ["Planche"]).allowed
    assert decide_create(make_facts(), ["Planche", "Planche2"]).allowed


def test_creer_refuse_sans_selection_et_panneau_ouvert() -> None:
    assert not decide_create(make_facts(), []).allowed
    assert decide_create(make_facts(busy=True), ["Planche"]).template == BUSY


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


@pytest.mark.parametrize("name", ["Bu>reau", "Bu\\reau"])
def test_renommer_un_ensemble_refuse_un_nom_inutilisable_dans_une_expression(name: str) -> None:
    decision = decide_rename("Bureau", name, furniture=True)
    assert not decision.allowed
    assert "inutilisable dans une expression" in decision.message


@pytest.mark.parametrize("furniture", [False, True])
@pytest.mark.parametrize("name", ["Pla\nteau", "Pla\tteau", "Pla\x00teau"])
def test_renommer_refuse_les_caracteres_de_controle(name: str, furniture: bool) -> None:
    decision = decide_rename("Plateau", name, furniture=furniture)
    assert not decision.allowed
    assert not decision.silent
    assert "caractère de contrôle" in decision.message


def test_infobulle_echappe_le_html_saisi() -> None:
    tip = plain_tooltip("<b>Gras</b> & <img src=x>")
    assert tip == "<span>&lt;b&gt;Gras&lt;/b&gt; &amp; &lt;img src=x&gt;</span>"
    assert "<b>" not in tip


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
