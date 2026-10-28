# SPDX-License-Identifier: LGPL-2.1-or-later
"""Assemblages défaits par un déplacement, au relâchement (ADR 0026, B7 modifié), sans FreeCAD :
essai du plan avant tout recalcul, choix injecté, suppression avec les pièces usinées, annulation,
et branchement de la fenêtre dans le glissement et le panneau de distance."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

from tests.unit.aides import ROOT
from tests.unit.aides_freecad import simulated_freecad

GUI = ROOT / "freecad" / "menuiserie" / "gui"


class Document:
    """Document de test : garde les noms supprimés et retire les liens des pièces usinées."""

    def __init__(self, machined: list[Any]) -> None:
        self.removed: list[str] = []
        self.machined = machined

    def removeObject(self, name: str) -> None:
        self.removed.append(name)
        for part in self.machined:
            part.Joints = [joint for joint in part.Joints if joint.Name != name]


def joint(name: str, document: Document, host: Any = None, guest: Any = None) -> SimpleNamespace:
    return SimpleNamespace(
        Name=name,
        Label=name,
        State=[],
        Document=document,
        HostPart=host,
        GuestPart=guest,
        impossible=False,
    )


@pytest.fixture
def module(monkeypatch: pytest.MonkeyPatch) -> Iterator[ModuleType]:
    """``features.drag_joints`` avec ``plan_for`` et ``is_joint`` de test : un assemblage dont
    ``impossible`` est vrai lève ``ValueError`` comme le vrai plan."""
    with simulated_freecad(monkeypatch):
        from freecad.menuiserie.features import drag_joints

        def plan_for(item: Any) -> None:
            if item.impossible:
                raise ValueError("impossible")

        monkeypatch.setattr(drag_joints, "plan_for", plan_for)
        monkeypatch.setattr(drag_joints, "is_joint", lambda obj: hasattr(obj, "impossible"))
        yield drag_joints


def scene(module: ModuleType, monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    """Une pièce ``V`` (pièce usinée ``MV``), deux assemblages vers deux pièces voisines."""
    machined = SimpleNamespace(Name="MV", Joints=[])
    other = SimpleNamespace(Name="MJ", Joints=[])
    document = Document([machined, other])
    part = SimpleNamespace(Name="V", InList=[])
    neighbour = SimpleNamespace(Name="J")
    first = joint("Aronde", document, part, neighbour)
    second = joint("Tourillons", document, neighbour, part)
    machined.Joints, other.Joints = [first, second], [first, second]
    part.InList = [machined, first, second]
    monkeypatch.setattr(
        module, "machined_part_of", lambda p: {"V": machined, "J": other}.get(p.Name)
    )
    removed_parts: list[str] = []
    monkeypatch.setattr(module, "remove_machined_part", lambda m: removed_parts.append(m.Name))
    return SimpleNamespace(
        part=part,
        first=first,
        second=second,
        document=document,
        machined=machined,
        removed_parts=removed_parts,
    )


class Chooser:
    """Fonction de choix de test : garde les libellés reçus, répond ``answer``."""

    def __init__(self, answer: bool) -> None:
        self.answer = answer
        self.asked: list[list[str]] = []

    def __call__(self, labels: Any) -> bool:
        self.asked.append(list(labels))
        return self.answer


# --- Essai avant recalcul ---------------------------------------------------------------------


def test_assemblages_impossibles_trouves_sans_recalcul(
    module: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    s = scene(module, monkeypatch)
    assert module.broken_joints(s.part) == []
    s.second.impossible = True
    assert module.broken_joints(s.part) == [s.second]


def test_assemblage_deja_defait_avant_le_deplacement_ne_compte_pas(
    module: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    s = scene(module, monkeypatch)
    s.first.impossible = s.second.impossible = True
    assert module.broken_joints(s.part, frozenset({"Aronde"})) == [s.second]


# --- Choix ------------------------------------------------------------------------------------


def test_rien_n_est_demande_si_tout_tient(
    module: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    s = scene(module, monkeypatch)
    choose = Chooser(True)
    assert module.settle_joints(s.part, frozenset(), choose) == []
    assert choose.asked == [] and s.document.removed == []


def test_sans_fonction_de_choix_rien_n_est_decide(
    module: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Script ou API : B7 d'origine, les assemblages restent (le recalcul prévient)."""
    s = scene(module, monkeypatch)
    s.first.impossible = True
    assert module.settle_joints(s.part, frozenset(), None) == []
    assert s.document.removed == []


def test_annuler_le_deplacement_ne_supprime_rien(
    module: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    s = scene(module, monkeypatch)
    s.first.impossible = True
    choose = Chooser(False)
    with pytest.raises(module.DragCancelledError):
        module.settle_joints(s.part, frozenset(), choose)
    assert choose.asked == [["« Aronde »"]]
    assert s.document.removed == [] and s.removed_parts == []


def test_supprimer_l_assemblage_et_la_piece_usinee_devenue_vide(
    module: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    s = scene(module, monkeypatch)
    s.first.impossible = s.second.impossible = True
    choose = Chooser(True)
    messages = module.settle_joints(s.part, frozenset(), choose)
    assert choose.asked == [["« Aronde »", "« Tourillons »"]]  # un seul choix pour tous
    assert s.document.removed == ["Aronde", "Tourillons"]
    assert s.removed_parts == ["MV", "MJ"]  # plus d'assemblage : pièces usinées retirées
    assert len(messages) == 1 and "« Aronde », « Tourillons »" in messages[0]
    assert "ont été supprimés" in messages[0]


def test_une_piece_usinee_qui_garde_un_assemblage_reste(
    module: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    s = scene(module, monkeypatch)
    s.first.impossible = True
    [message] = module.settle_joints(s.part, frozenset(), Chooser(True))
    assert s.document.removed == ["Aronde"]
    assert s.removed_parts == []  # « Tourillons » tient encore sur les deux pièces usinées
    assert "a été supprimé" in message and "« Aronde »" in message


# --- Écriture du relâchement ------------------------------------------------------------------


@pytest.fixture
def drag(monkeypatch: pytest.MonkeyPatch) -> Iterator[ModuleType]:
    with simulated_freecad(monkeypatch):
        from freecad.menuiserie.features import part_drag

        yield part_drag


def release(drag: ModuleType, monkeypatch: pytest.MonkeyPatch, events: list[str]) -> Any:
    """Mémento de test : ``restore``, la liaison et le recalcul notent leur appel."""

    def note(name: str) -> list[str]:
        events.append(name)
        return []

    document = SimpleNamespace(recompute=lambda: note("recompute"))
    memento = SimpleNamespace(part=SimpleNamespace(Document=document), invalid_joints=frozenset())
    monkeypatch.setattr(drag, "restore", lambda m: note("restore"))
    monkeypatch.setattr(drag, "_relink", lambda m: note("relink"))
    monkeypatch.setattr(drag, "_joint_warnings", lambda m: [])
    return memento


def test_le_choix_precede_la_liaison_et_le_recalcul(
    drag: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    events: list[str] = []
    memento = release(drag, monkeypatch, events)

    def settle(part: Any, invalid: Any, choose: Any) -> list[str]:
        events.append("settle")
        return ["supprimé"]

    monkeypatch.setattr(drag, "settle_joints", settle)
    assert drag.end_drag(memento, object()) == ["supprimé", "supprimé"]
    assert events == ["settle", "relink", "settle", "recompute"]


def test_annuler_remet_la_piece_sans_recalcul(
    drag: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    events: list[str] = []
    memento = release(drag, monkeypatch, events)

    def settle(part: Any, invalid: Any, choose: Any) -> list[str]:
        raise drag.DragCancelledError

    monkeypatch.setattr(drag, "settle_joints", settle)
    with pytest.raises(drag.DragCancelledError):
        drag.end_drag(memento, object())
    assert events == ["restore"]  # la pièce revient ; ni liaison ni recalcul


# --- Branchement de la fenêtre ----------------------------------------------------------------


def source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_le_glissement_et_le_panneau_de_distance_proposent_le_choix() -> None:
    session = source(GUI / "drag" / "session.py")
    assert "end_drag(state.memento, joint_choice.choose)" in session
    assert "except DragCancelledError" in session
    panel = source(GUI / "task_panels" / "distance.py")
    assert "choose=joint_choice.choose" in panel
    assert "except DragCancelledError" in panel


def test_la_fenetre_a_deux_boutons_et_annuler_par_defaut() -> None:
    text = source(GUI / "joint_choice.py")
    for expected in (
        "Annuler le déplacement",
        "Supprimer l'assemblage",
        "Supprimer les assemblages",
        "setDefaultButton(cancel)",
        "setEscapeButton(cancel)",
    ):
        assert expected in text
    assert "chooser: JointChoice = ask" in text  # remplaçable hors écran


# --- Rotation du panneau de la pièce ----------------------------------------------------------


def rotating(module: ModuleType, monkeypatch: pytest.MonkeyPatch, s: SimpleNamespace) -> list[str]:
    """``rotate_part`` de test : change le ``Placement`` de la pièce et de sa pièce usinée ; la
    liste renvoyée reçoit les avertissements écrits dans la vue rapport."""
    s.part.Placement = "avant"
    s.machined.Placement = "avant"
    written: list[str] = []

    def rotate(part: Any, turn: Any, session: Any = None) -> bool:
        part.Placement = "apres"
        return True

    monkeypatch.setattr(module, "rotate_part", rotate)
    monkeypatch.setattr(module, "App", SimpleNamespace(Placement=lambda value: value))
    monkeypatch.setattr(module, "report_warning", written.append)
    return written


def test_rotation_qui_defait_un_assemblage_annulee(
    module: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    s = scene(module, monkeypatch)
    rotating(module, monkeypatch, s)
    s.first.impossible = True
    assert module.rotate_checked(s.part, "X", None, Chooser(False)) is False
    assert s.part.Placement == "avant" and s.machined.Placement == "avant"
    assert s.document.removed == []


def test_rotation_qui_defait_un_assemblage_supprime(
    module: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    s = scene(module, monkeypatch)
    written = rotating(module, monkeypatch, s)
    s.first.impossible = True
    assert module.rotate_checked(s.part, "X", None, Chooser(True)) is True
    assert s.part.Placement == "apres"  # rotation gardée
    assert s.document.removed == ["Aronde"]
    assert len(written) == 1 and "« Aronde »" in written[0]


def test_rotation_en_creation_ou_sans_choix_n_essaie_rien(
    module: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    s = scene(module, monkeypatch)
    rotating(module, monkeypatch, s)
    s.first.impossible = True
    choose = Chooser(False)
    assert module.rotate_checked(s.part, "X", object(), choose) is True  # création : accrochage
    assert module.rotate_checked(s.part, "X", None, None) is True  # script : B7 d'origine
    assert choose.asked == [] and s.document.removed == []


# --- Création d'un assemblage : essai avant le premier recalcul --------------------------------


def test_la_commande_essaie_l_assemblage_avant_son_premier_recalcul() -> None:
    """Un assemblage impossible ne doit jamais être recalculé (trace Python de FreeCAD) : la
    commande passe ``feasible_joint`` à la fabrique, qui l'appelle avant ``recompute``."""
    command = source(GUI / "commands" / "joints.py")
    assert "FACTORY(host, guest, check=feasible_joint)" in command
    api_text = source(ROOT / "freecad" / "menuiserie" / "api.py")
    body = api_text[api_text.index("def _make_joint") : api_text.index("def _shown_and_recomputed")]
    assert body.index("check(joint)") < body.index("_shown_and_recomputed(joint)")


def test_essai_de_l_assemblage_avec_inversion_des_roles(monkeypatch: pytest.MonkeyPatch) -> None:
    with simulated_freecad(monkeypatch):
        from freecad.menuiserie.features.joints import feasible

        plans: list[tuple[str, str]] = []

        def plan_for(joint: Any) -> None:
            plans.append((joint.HostPart, joint.GuestPart))
            if joint.HostPart != "B":
                raise ValueError("impossible")

        monkeypatch.setattr(feasible, "plan_for", plan_for)
        monkeypatch.setattr(feasible, "joint_label", lambda joint: "inversé")
        joint = SimpleNamespace(HostPart="A", GuestPart="B", Label="")
        assert feasible.feasible_joint(joint) is joint
        assert (joint.HostPart, joint.Label) == ("B", "inversé")  # rôles inversés
        impossible = SimpleNamespace(HostPart="A", GuestPart="C", Label="")
        with pytest.raises(ValueError, match="impossible"):
            feasible.feasible_joint(impossible)
        assert (impossible.HostPart, impossible.GuestPart) == ("A", "C")  # rôles d'origine
