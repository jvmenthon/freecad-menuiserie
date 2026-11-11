# SPDX-License-Identifier: LGPL-2.1-or-later
"""Panneau « Structure » (ADR 0046, lot 2) : logique de synchronisation pure et garde-fous
statiques de l'interface (les modules de ``gui/`` importent FreeCADGui)."""

from __future__ import annotations

import ast
from collections.abc import Callable

import pytest

from freecad.menuiserie.core.structure_sync import (
    IGNORED_PROPERTIES,
    Coalescer,
    ReentrancyGuard,
    expanded_after_refresh,
    is_relevant_change,
    keys_to_select_in_freecad,
    node_id,
    rows_for_selection,
)
from freecad.menuiserie.core.structure_tree import NodeKind, StructureNode
from tests.unit.aides import ROOT

GUI = ROOT / "freecad" / "menuiserie" / "gui"
SYNC = GUI / "structure_sync.py"


class Scheduler:
    """Différé simulé : range les rappels, qu'un test exécute à la main."""

    def __init__(self) -> None:
        self.queue: list[Callable[[], None]] = []

    def __call__(self, callback: Callable[[], None]) -> None:
        self.queue.append(callback)

    def run(self) -> None:
        queue, self.queue = self.queue, []
        for callback in queue:
            callback()


def make_coalescer() -> tuple[Coalescer, Scheduler, list[int]]:
    calls: list[int] = []
    scheduler = Scheduler()
    return Coalescer(scheduler, lambda: calls.append(1)), scheduler, calls


# --- Regroupement ------------------------------------------------------------------------


def test_une_rafale_donne_une_seule_execution() -> None:
    coalescer, scheduler, calls = make_coalescer()
    for _ in range(50):
        coalescer.request()
    assert len(scheduler.queue) == 1
    assert calls == []  # rien n'est calculé avant le différé
    scheduler.run()
    assert calls == [1]


def test_nouvelle_demande_apres_l_execution() -> None:
    coalescer, scheduler, calls = make_coalescer()
    coalescer.request()
    scheduler.run()
    coalescer.request()
    scheduler.run()
    assert calls == [1, 1]


def test_demande_pendant_l_action_reprogramme() -> None:
    scheduler = Scheduler()
    calls: list[int] = []

    def action() -> None:
        calls.append(1)
        if len(calls) == 1:
            coalescer.request()

    coalescer = Coalescer(scheduler, action)
    coalescer.request()
    scheduler.run()
    assert coalescer.pending
    scheduler.run()
    assert calls == [1, 1]


def test_annulation_avant_le_differe() -> None:
    coalescer, scheduler, calls = make_coalescer()
    coalescer.request()
    coalescer.cancel()
    scheduler.run()
    assert calls == [] and not coalescer.pending


def test_annulation_puis_nouvelle_demande_ne_double_pas_l_execution() -> None:
    coalescer, scheduler, calls = make_coalescer()
    coalescer.request()
    coalescer.cancel()
    coalescer.request()
    scheduler.run()  # l'ancien rappel et le nouveau : une seule exécution
    assert calls == [1]


# --- Garde de rétroaction ----------------------------------------------------------------


def test_garde_active_pendant_l_ecriture_seulement() -> None:
    guard = ReentrancyGuard()
    assert not guard.active
    with guard.applying():
        assert guard.active
        with guard.applying():
            assert guard.active
        assert guard.active
    assert not guard.active


def test_garde_relachee_apres_une_erreur() -> None:
    guard = ReentrancyGuard()
    with pytest.raises(RuntimeError), guard.applying():
        raise RuntimeError("échec")
    assert not guard.active


# --- Filtre des modifications ------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(IGNORED_PROPERTIES))
def test_modifications_geometriques_ignorees(name: str) -> None:
    assert not is_relevant_change(name)


@pytest.mark.parametrize("name", ["Label", "Group", "Length", "Furniture"])
def test_autres_modifications_suivies(name: str) -> None:
    assert is_relevant_change(name)


# --- Identité et état déplié -------------------------------------------------------------


def test_identite_par_chemin_de_cles() -> None:
    joints = StructureNode(NodeKind.JOINTS, "Assemblages (1)")
    piece = StructureNode(NodeKind.PIECE, "Plateau", "P1")
    assert node_id("/Bureau", piece) == "/Bureau/P1"
    assert node_id("/Bureau", joints) == "/Bureau/joints"
    assert node_id("/Tiroir", joints) != node_id("/Bureau", joints)


def test_etat_deplie_garde_sinon_defaut() -> None:
    assert expanded_after_refresh(False, "/A", {"/A": True}) is True
    assert expanded_after_refresh(True, "/A", {"/A": False}) is False
    assert expanded_after_refresh(True, "/B", {"/A": False}) is True


# --- Correspondance de sélection ---------------------------------------------------------


def test_lignes_surlignees_seulement_si_montrees() -> None:
    assert rows_for_selection(["P2", "Origin", "P1", "P2"], {"P1", "P2"}) == ["P2", "P1"]
    assert rows_for_selection([], {"P1"}) == []


def test_objets_a_selectionner_sans_cle_vide_ni_doublon() -> None:
    assert keys_to_select_in_freecad(["P1", "", "P2", "P1"]) == ["P1", "P2"]
    assert keys_to_select_in_freecad([""]) == []


# --- Garde-fous statiques de l'interface -------------------------------------------------


def calls_named(name: str) -> list[ast.Call]:
    tree = ast.parse(SYNC.read_text(encoding="utf-8"))
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and name in (getattr(node.func, "attr", None), getattr(node.func, "id", None))
    ]


def attributes() -> set[str]:
    tree = ast.parse(SYNC.read_text(encoding="utf-8"))
    return {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}


def test_chaque_observateur_pose_est_retire() -> None:
    for added, removed in (
        ("addDocumentObserver", "removeDocumentObserver"),
        ("addObserver", "removeObserver"),
    ):
        assert calls_named(added), added
        assert removed in attributes(), removed  # passé à ``_try`` : référence, pas appel


def test_le_panneau_se_detache_a_la_fermeture_et_a_la_destruction() -> None:
    source = (GUI / "structure_panel.py").read_text(encoding="utf-8")
    assert "visibilityChanged" in source
    assert "destroyed" in source and "detach" in source


def test_double_clic_comme_l_arbre_natif() -> None:
    """Le double-clic appelle le ``doubleClicked`` du ViewProvider (celui de l'arbre natif)."""
    assert "doubleClicked" in SYNC.read_text(encoding="utf-8")
    assert calls_named("setEdit")


def test_la_selection_n_ecrit_que_dans_gui_selection() -> None:
    written = {call.func.attr for call in calls_named("addSelection")}  # type: ignore[attr-defined]
    assert written == {"addSelection"}
    for forbidden in ("removeObject", "setExpression", "Label ="):
        assert forbidden not in SYNC.read_text(encoding="utf-8")
