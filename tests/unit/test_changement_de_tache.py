# SPDX-License-Identifier: LGPL-2.1-or-later
"""Sélection de ligne et tâche en cours du panneau « Structure » (ADR 0046) : décision pure
(``core/task_switch``), détection d'une modification (``core/document_state``,
``features/document_snapshot``), étendue de la mise en évidence et câblage (analyse statique)."""

from __future__ import annotations

import ast
from collections.abc import Iterator
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

from freecad.menuiserie.core.document_state import changed_objects, differs, is_tracked
from freecad.menuiserie.core.structure_highlight import SCOPE_BY_KIND, Scope, scope_of
from freecad.menuiserie.core.structure_tree import NodeKind
from freecad.menuiserie.core.task_switch import Action, Choice, plan, resolve
from tests.unit.aides import ROOT
from tests.unit.aides_freecad import simulated_freecad

GUI = ROOT / "freecad/menuiserie/gui"

# --- Décision ---------------------------------------------------------------------------


def decide(**facts: bool) -> Action:
    base = {"task_open": True, "ours": True, "creating": False, "changed": False}
    return plan(**{**base, **facts})


def test_aucune_tache_ouvre_la_piece() -> None:
    assert decide(task_open=False, ours=False) is Action.OPEN


def test_tache_inchangee_fermee_sans_rien_changer_puis_piece_ouverte() -> None:
    assert decide() is Action.DISCARD_THEN_OPEN


def test_tache_modifiee_demande() -> None:
    assert decide(changed=True) is Action.ASK


def test_tache_de_creation_demande_meme_inchangee() -> None:
    assert decide(creating=True) is Action.ASK  # « Annuler » supprimerait l'objet


def test_tache_d_un_autre_atelier_refusee() -> None:
    assert decide(ours=False, changed=True) is Action.REFUSE


@pytest.mark.parametrize(
    ("choice", "action"),
    [
        (Choice.APPLY, Action.APPLY_THEN_OPEN),
        (Choice.DISCARD, Action.DISCARD_THEN_OPEN),
        (Choice.STAY, Action.NOTHING),
        (None, Action.NOTHING),  # boîte fermée (Échap)
    ],
)
def test_reponse_de_l_utilisateur(choice: Choice | None, action: Action) -> None:
    assert resolve(choice) is action


# --- Détection d'une modification -------------------------------------------------------


def test_proprietes_suivies_sont_les_saisies() -> None:
    assert is_tracked("Length", "App::PropertyLength", [])
    assert is_tracked("Placement", "App::PropertyPlacement", [])
    assert not is_tracked("Shape", "Part::PropertyPartShape", [])
    assert not is_tracked("Proxy", "App::PropertyPythonObject", [])
    assert not is_tracked("Visibility", "App::PropertyBool", [])
    assert not is_tracked("Width", "App::PropertyLength", ["Output"])
    assert not is_tracked("Cache", "App::PropertyString", ["Transient"])
    # « ReadOnly » est un mode d'éditeur : « Inverser » écrit HostPart et GuestPart ainsi déclarées
    assert is_tracked("HostPart", "App::PropertyLink", ["ReadOnly"])


def test_photo_identique_n_est_pas_une_modification() -> None:
    photo = {"P": {"Length": "100 mm"}}
    assert not differs(photo, {"P": {"Length": "100 mm"}})


def test_valeur_modifiee_objet_cree_ou_supprime() -> None:
    photo = {"P": {"Length": "100 mm"}, "Q": {}}
    assert changed_objects(photo, {"P": {"Length": "90 mm"}, "Q": {}}) == ["P"]
    assert changed_objects(photo, {"P": {"Length": "100 mm"}}) == ["Q"]
    assert changed_objects(photo, {**photo, "R": {}}) == ["R"]


class FakeObject:
    def __init__(self, name: str, **values: object) -> None:
        self.Name = name
        self.TypeId = "Part::FeaturePython"
        self._types = {"Length": "App::PropertyLength", "Shape": "Part::PropertyPartShape"}
        self.PropertiesList = ["Length", "Shape", "Links", *values]
        self.Length = 100
        self.Shape = object()  # repr avec adresse : ne doit jamais compter
        self.Links: list[Any] = []
        for key, value in values.items():
            setattr(self, key, value)

    def getTypeIdOfProperty(self, name: str) -> str:
        return self._types.get(name, "App::PropertyLinkList")

    def getPropertyStatus(self, name: str) -> list[str]:
        return []


@pytest.fixture
def snapshot_of(monkeypatch: pytest.MonkeyPatch) -> Iterator[Any]:
    with simulated_freecad(monkeypatch):
        from freecad.menuiserie.features import document_snapshot

        yield document_snapshot.snapshot_of


def test_photo_stable_sans_adresse_et_sensible_aux_saisies(snapshot_of: Any) -> None:
    target = FakeObject("Cible")
    obj = FakeObject("P")
    obj.Links = [target, (target, ["Face1"])]
    doc = SimpleNamespace(Objects=[obj, target])
    before = snapshot_of(doc)
    assert before == snapshot_of(doc)  # ni forme ni adresse
    assert before["P"]["Links"] == "[<Cible>,[<Cible>,[Face1]]]"
    obj.Shape = object()  # recalcul : forme recréée
    assert not differs(before, snapshot_of(doc))
    obj.Length = 90
    assert differs(before, snapshot_of(doc))


def test_photo_propriete_illisible_reste_stable(snapshot_of: Any) -> None:
    obj = FakeObject("P")
    del obj.Links
    doc = SimpleNamespace(Objects=[obj])
    assert snapshot_of(doc) == snapshot_of(doc)


# --- Étendue de la mise en évidence ------------------------------------------------------


def test_etendue_par_genre_de_ligne() -> None:
    assert scope_of(NodeKind.FURNITURE.value) is Scope.PIECES
    for kind in (NodeKind.PIECE, NodeKind.JOINT, NodeKind.HARDWARE_ITEM):
        assert scope_of(kind.value) is Scope.OBJECT
    for kind in (NodeKind.JOINTS, NodeKind.HARDWARE, NodeKind.OTHER, NodeKind.OTHERS):
        assert scope_of(kind.value) is None  # replié ou d'un autre atelier : rien à montrer
    assert scope_of("inconnu") is None
    assert NodeKind.OTHER not in SCOPE_BY_KIND


@pytest.fixture
def targets(monkeypatch: pytest.MonkeyPatch) -> Iterator[ModuleType]:
    with simulated_freecad(monkeypatch):
        from freecad.menuiserie.features import highlight_targets

        def shown(obj: Any) -> Any:
            return getattr(obj, "machined", obj)

        monkeypatch.setattr(highlight_targets, "shown_object", shown)
        monkeypatch.setattr(highlight_targets, "is_joint", lambda obj: hasattr(obj, "HostPart"))
        monkeypatch.setattr(highlight_targets, "pieces_below", lambda obj: obj.pieces)
        yield highlight_targets


def test_piece_ensemble_et_assemblage_mis_en_evidence(targets: Any) -> None:
    machined = SimpleNamespace(Name="PU")
    blank = SimpleNamespace(Name="P", machined=machined)
    other = SimpleNamespace(Name="Q")
    assert targets.highlighted_objects(blank, Scope.OBJECT) == [machined]
    furniture = SimpleNamespace(Name="E", pieces=[blank, other, blank])
    assert targets.highlighted_objects(furniture, Scope.PIECES) == [machined, other]
    joint = SimpleNamespace(Name="J", HostPart=blank, GuestPart=other)
    assert targets.highlighted_objects(joint, Scope.OBJECT) == [machined, other]
    loose = SimpleNamespace(Name="F", HostPart=blank, GuestPart=None)  # pied sans invitée
    assert targets.highlighted_objects(loose, Scope.OBJECT) == [machined]


# --- Câblage (analyse statique : ces modules importent FreeCADGui) -----------------------


def source(name: str) -> str:
    return (GUI / name).read_text(encoding="utf-8")


def methods_of(path: str, class_name: str) -> dict[str, str]:
    tree = ast.parse(source(path))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == class_name)
    return {n.name: ast.unparse(n) for n in cls.body if isinstance(n, ast.FunctionDef)}


def test_la_selection_de_ligne_pose_le_calque_de_selection() -> None:
    methods = methods_of("structure_highlight.py", "RowHighlight")
    assert "deferrable=True" in methods["choose"]  # jamais écrit dans une transaction ouverte
    assert "deferrable=True" in methods["clear"]
    assert "SELECTION_LOOK" in methods["choose"]
    assert "self.clear()" in methods["follow"]  # lignes plus choisies : calque retiré
    sync = methods_of("structure_sync.py", "StructureSync")
    assert "itemSelectionChanged.connect(self._choose_rows)" in sync["__init__"]
    assert "_follow_highlight()" in sync["pull_selection"]  # sélection reprise de FreeCAD
    assert "_follow_highlight()" in sync["refresh_now"]
    assert "self._guard.active" in sync["_choose_rows"]  # pas pendant un remplissage
    assert "_choose_rows()" not in sync["pull_selection"]  # FreeCAD ne rend rien transparent
    observers = methods_of("structure_sync.py", "_Observers")
    assert "_on_detach" in observers["detach"]  # panneau masqué ou détruit : calque retiré


def test_le_double_clic_regle_la_tache_en_cours() -> None:
    assert "switch_to" in methods_of("structure_sync.py", "StructureSync")["_open_panel"]
    text = source("structure_switch.py")
    assert "Qt.PlainText" in text  # boîte en texte brut
    assert "panel.reject()" in text
    assert "panel.accept()" in text
    assert "singleShot" in text  # ouverture après la fermeture de la tâche
    assert "lambda" not in text


def test_le_panneau_s_inscrit_et_s_efface() -> None:
    base = methods_of("task_panels/base.py", "TransactionTaskPanel")
    assert "active.register(self)" in base["watch_document"]
    assert "snapshot_of" in base["watch_document"]
    assert "active.unregister(self)" in base["_finish"]
    assert "active.unregister(self)" in base["_on_closed_by_freecad"]
    assert "_without_transaction" in base["_apply_styles"]
    assert "DISPLAY.flush()" in base["_finish"]  # sélection différée jouée à la fin de la tâche
    assert "DISPLAY.flush()" in base["_clean_up_after_forced_close"]
    # la transaction n'est jamais abandonnée que pour poser l'édition à l'ouverture
    assert "closeActiveTransaction" not in "".join(
        text for name, text in base.items() if name != "_without_transaction"
    )


def test_aucun_nombre_magique_de_teinte_hors_core() -> None:
    for name in ("display_layers.py", "structure_highlight.py", "task_panels/preview.py"):
        assert "(70, 160, 255)" not in source(name)
