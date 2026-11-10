# SPDX-License-Identifier: LGPL-2.1-or-later
"""Panneau « Structure » (ADR 0046), revue de fin de jalon : cas limites purs.

Document vide, ensemble sans pièce, noms très longs ou à caractères spéciaux, menu sans rien
de choisi, rafale de notifications après une erreur, libellés cités dans un menu Qt.
"""

from __future__ import annotations

from collections.abc import Sequence

import pytest

from freecad.menuiserie.core._validation import has_forbidden_character
from freecad.menuiserie.core.structure_actions import (
    MAX_NAME_LENGTH,
    MoveFacts,
    decide_drop,
    decide_rename,
)
from freecad.menuiserie.core.structure_menu import Action, menu_entries, verbatim_text
from freecad.menuiserie.core.structure_sync import Coalescer, node_id
from freecad.menuiserie.core.structure_tree import NodeKind, StructureNode, build_structure
from tests.unit.test_structure_arbre import FakeSource, title

NASTY = ["Bureau {0} {name}", "R&D", "a\nb", "‮RTL", "<b>gras</b>", "x" * 500, "« guillemets »"]


class Only(FakeSource):
    """Une seule racine, sans rien d'autre."""

    def __init__(self, label: str, *, pieces: Sequence[str] = ()) -> None:
        self._label = label
        self._pieces = list(pieces)

    def root_furnitures(self) -> Sequence[str]:
        return ["E"]

    def loose_pieces(self) -> Sequence[str]:
        return []

    def sub_furnitures(self, furniture: str) -> Sequence[str]:
        return []

    def pieces(self, furniture: str) -> Sequence[str]:
        return self._pieces

    def joints(self, furniture: str) -> Sequence[str]:
        return []

    def label(self, key: str) -> str:
        return self._label


def test_ensemble_sans_piece_ni_assemblage_est_une_feuille() -> None:
    (root,) = build_structure(Only("Vide"), title)
    assert (root.kind, root.label, root.children) == (NodeKind.FURNITURE, "Vide", ())


@pytest.mark.parametrize("label", NASTY, ids=range(len(NASTY)))
def test_libelles_speciaux_gardes_tels_quels_dans_l_arbre(label: str) -> None:
    (root,) = build_structure(Only(label, pieces=["P1"]), title)
    assert root.label == label
    assert [child.label for child in root.children] == [label]


def test_identites_de_lignes_distinctes_pour_les_noeuds_sans_cle() -> None:
    joints = StructureNode(NodeKind.JOINTS, "Assemblages (1)")
    others = StructureNode(NodeKind.OTHERS, "Autres objets (1)")
    assert node_id("/E", joints) != node_id("/E", others)


def facts(labels: dict[str, str], **kwargs: object) -> MoveFacts:
    return MoveFacts(labels, frozenset(k for k in labels if k.startswith("E")), {}, **kwargs)  # type: ignore[arg-type]


@pytest.mark.parametrize("label", NASTY, ids=range(len(NASTY)))
def test_refus_avec_un_libelle_special_ne_plante_pas_et_reste_court(label: str) -> None:
    data = facts({"E1": label, "P": label})
    decision = decide_drop(data, ["P"], "E1")
    assert decision.allowed
    refused = decide_drop(MoveFacts({"E1": label}, frozenset({"E1"}), {}), ["E1"], "E1")
    assert not refused.allowed
    assert "\n" not in refused.message  # le saut de ligne est échappé
    assert len(refused.message) < 400  # 500 caractères cités : tronqués à 32


def test_menu_sans_document_ni_selection_tout_est_refuse_sans_erreur() -> None:
    empty = MoveFacts({}, frozenset(), {})
    entries = menu_entries(empty, [])
    assert entries[0].action is Action.OPEN
    assert not any(e.decision.allowed for e in entries)
    assert all(e.decision.message for e in entries)  # chaque refus s'explique


def test_depot_dans_un_ensemble_vide_permis() -> None:
    data = MoveFacts({"E1": "Vide", "P": "Planche"}, frozenset({"E1"}), {})
    assert decide_drop(data, ["P"], "E1").keys == ("P",)


def test_nom_a_la_limite_et_juste_au_dela() -> None:
    assert decide_rename("a", "b" * MAX_NAME_LENGTH, furniture=False).allowed
    refused = decide_rename("a", "b" * (MAX_NAME_LENGTH + 1), furniture=False)
    assert not refused.allowed
    assert str(MAX_NAME_LENGTH + 1) in refused.message


@pytest.mark.parametrize("text", ["", " ", "\t\n", "\u00a0"])
def test_nom_vide_ou_blanc_refuse(text: str) -> None:
    assert not decide_rename("ancien", text, furniture=False).allowed


@pytest.mark.parametrize("label", [n for n in NASTY if len(n) <= MAX_NAME_LENGTH])
def test_renommer_une_piece_accepte_les_caracteres_speciaux(label: str) -> None:
    allowed = not has_forbidden_character(label)  # saut de ligne, contrôle de direction : refusés
    assert decide_rename("ancien", label, furniture=False).allowed is allowed


def test_le_et_commercial_est_double_dans_un_menu_qt() -> None:
    assert verbatim_text("R&D") == "R&&D"
    assert verbatim_text("Cuisine") == "Cuisine"
    assert verbatim_text("") == ""


def test_les_entrees_d_ensemble_sont_citees_sans_interpretation() -> None:
    data = MoveFacts({"E1": "R&D {x}", "P": "Planche"}, frozenset({"E1"}), {})
    add = next(e for e in menu_entries(data, ["P"]) if e.action is Action.ADD_TO)
    assert [(c.label, c.verbatim) for c in add.children] == [("R&D {x}", True)]


def test_une_erreur_dans_l_action_ne_bloque_pas_les_demandes_suivantes() -> None:
    queue: list[object] = []
    calls: list[int] = []

    def action() -> None:
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("objet supprimé pendant le rafraîchissement")

    coalescer = Coalescer(queue.append, action)
    coalescer.request()
    with pytest.raises(RuntimeError):
        queue.pop()()  # type: ignore[operator]
    assert not coalescer.pending
    coalescer.request()
    queue.pop()()  # type: ignore[operator]
    assert calls == [1, 1]
