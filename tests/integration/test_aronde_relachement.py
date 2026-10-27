# SPDX-License-Identifier: LGPL-2.1-or-later
"""Assemblages défaits par un déplacement, au relâchement (ADR 0024, B7 modifié) : « Annuler le
déplacement » remet la pièce, « Supprimer l'assemblage » supprime les assemblages (et leurs pièces
usinées) et garde le déplacement, une seule transaction annulable, aucun recalcul en erreur."""

from __future__ import annotations

from typing import Any

import pytest

from tests.integration.bureau import build_parts
from tests.integration.cadre import stale_or_invalid

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
api = pytest.importorskip("freecad.menuiserie.api")
geometry = pytest.importorskip("freecad.menuiserie.core.geometry")
drag = pytest.importorskip("freecad.menuiserie.features.part_drag")
joints = pytest.importorskip("freecad.menuiserie.features.joints.base")
machined = pytest.importorskip("freecad.menuiserie.features.machined_part")
drag_joints = pytest.importorskip("freecad.menuiserie.features.drag_joints")
feasible = pytest.importorskip("freecad.menuiserie.features.joints.feasible")
snap = pytest.importorskip("freecad.menuiserie.core.snap")

Vec3 = geometry.Vec3
FAR = Vec3(1000, 0, 0)  # le voile n'arrive plus à toucher ses joues
TRANSACTION = "Déplacer la pièce"


class Chooser:
    """Fonction de choix de test (la fenêtre ne se clique pas hors écran)."""

    def __init__(self, answer: bool) -> None:
        self.answer = answer
        self.asked: list[list[str]] = []

    def __call__(self, labels: Any) -> bool:
        self.asked.append(list(labels))
        return self.answer


def assembled(document: Any, *sides: str) -> tuple[Any, list[Any]]:
    """Bureau de pièces avec un assemblage à tourillons du voile à chacune des ``sides``."""
    bureau = build_parts(document)
    made = [api.make_dowels(bureau.parts[side], bureau.parts["V"]) for side in sides]
    document.recompute()
    return bureau, made


def moved(document: Any, voile: Any, choose: Any) -> Any:
    """Glissement de ``FAR`` dans la transaction de la commande ; renvoie les avertissements."""
    document.openTransaction(TRANSACTION)
    memento = drag.begin_drag(voile)
    drag.move_part(memento, FAR)
    try:
        messages = drag.end_drag(memento, choose)
    except drag.DragCancelledError:
        document.abortTransaction()
        raise
    document.commitTransaction()
    return messages


def test_annuler_le_deplacement_remet_la_piece(document: Any) -> None:
    bureau, [joint] = assembled(document, "JG")
    voile = bureau.parts["V"]
    start = App.Placement(voile.Placement)
    choose = Chooser(False)
    with pytest.raises(drag.DragCancelledError):
        moved(document, voile, choose)
    assert choose.asked == [["« " + joint.Label + " »"]]
    assert voile.Placement == start
    assert document.getObject(joint.Name) is not None  # l'assemblage est resté
    document.recompute()
    assert stale_or_invalid(document) == []


def test_annuler_sans_transaction_propre_remet_aussi_la_piece(document: Any) -> None:
    """Panneau ouvert : la transaction est celle du panneau, la pièce revient par ``restore``."""
    bureau, [joint] = assembled(document, "JG")
    voile = bureau.parts["V"]
    start = App.Placement(voile.Placement)
    memento = drag.begin_drag(voile)
    drag.move_part(memento, FAR)
    with pytest.raises(drag.DragCancelledError):
        drag.end_drag(memento, Chooser(False))
    assert voile.Placement == start
    assert machined.machined_part_of(voile).Placement == start
    assert "Invalid" not in joint.State


def test_supprimer_l_assemblage_garde_le_deplacement(document: Any) -> None:
    bureau, [joint] = assembled(document, "JG")
    voile, joue = bureau.parts["V"], bureau.parts["JG"]
    name, label = joint.Name, joint.Label  # l'objet supprimé n'est plus lisible
    start = App.Placement(voile.Placement)
    choose = Chooser(True)
    messages = moved(document, voile, choose)
    assert choose.asked == [["« " + label + " »"]]
    assert document.getObject(name) is None  # assemblage supprimé
    assert machined.machined_part_of(voile) is None  # avec ses pièces usinées
    assert machined.machined_part_of(joue) is None
    assert voile.Visibility and joue.Visibility  # les brutes sont réaffichées
    assert voile.Placement.Base.x == pytest.approx(start.Base.x + FAR.x)  # déplacement gardé
    assert len(messages) == 1 and "supprimé" in messages[0]
    document.recompute()
    assert stale_or_invalid(document) == []


def test_supprimer_les_assemblages_au_pluriel(document: Any) -> None:
    bureau, made = assembled(document, "JG", "JD")
    voile = bureau.parts["V"]
    names = [joint.Name for joint in made]
    labels = ["« " + joint.Label + " »" for joint in made]
    choose = Chooser(True)
    messages = moved(document, voile, choose)
    assert len(choose.asked) == 1  # une seule fenêtre pour les deux assemblages
    assert sorted(choose.asked[0]) == sorted(labels)
    assert all(document.getObject(name) is None for name in names)
    assert "ont été supprimés" in messages[0]
    document.recompute()
    assert stale_or_invalid(document) == []


def test_un_assemblage_qui_tient_encore_ne_demande_rien(document: Any) -> None:
    bureau, [joint] = assembled(document, "JG")
    voile = bureau.parts["V"]
    choose = Chooser(True)
    document.openTransaction(TRANSACTION)
    memento = drag.begin_drag(voile)
    drag.move_part(memento, Vec3(0, 0, -100))
    assert drag.end_drag(memento, choose) == []
    document.commitTransaction()
    assert choose.asked == []
    assert document.getObject(joint.Name) is not None


def test_une_seule_transaction_annulable(document: Any) -> None:
    document.UndoMode = 1
    bureau, [joint] = assembled(document, "JG")
    voile = bureau.parts["V"]
    name = joint.Name
    start = App.Placement(voile.Placement)
    document.clearUndos()
    moved(document, voile, Chooser(True))
    assert document.UndoNames == [TRANSACTION]
    document.undo()  # un seul Ctrl+Z : pièce, assemblage et pièces usinées reviennent
    assert document.UndoNames == []
    assert voile.Placement == start
    restored = document.getObject(name)
    assert restored is not None
    assert machined.machined_part_of(voile) is not None
    document.recompute()
    assert stale_or_invalid(document) == []
    assert joints.is_joint(restored)


def test_sans_fonction_de_choix_le_deplacement_est_garde(document: Any) -> None:
    """Script ou API : B7 d'origine (déplacement gardé, avertissement)."""
    bureau, [joint] = assembled(document, "JG")
    voile = bureau.parts["V"]
    memento = drag.begin_drag(voile)
    drag.move_part(memento, FAR)
    [warning] = drag.end_drag(memento)
    assert "ne touche plus" in warning
    assert document.getObject(joint.Name) is not None


# --- Rotation du panneau de la pièce ----------------------------------------------------------


def test_rotation_annulee_remet_la_piece(document: Any) -> None:
    bureau, [joint] = assembled(document, "JG")
    voile = bureau.parts["V"]
    start = App.Placement(voile.Placement)
    choose = Chooser(False)
    assert drag_joints.rotate_checked(voile, snap.Turn.Z, None, choose) is False
    assert len(choose.asked) == 1
    assert voile.Placement == start
    assert machined.machined_part_of(voile).Placement == start
    assert document.getObject(joint.Name) is not None
    document.recompute()
    assert stale_or_invalid(document) == []


def test_rotation_qui_supprime_l_assemblage(document: Any) -> None:
    bureau, [joint] = assembled(document, "JG")
    voile = bureau.parts["V"]
    start = App.Placement(voile.Placement)
    name = joint.Name
    assert drag_joints.rotate_checked(voile, snap.Turn.Z, None, Chooser(True)) is True
    assert voile.Placement != start  # rotation gardée
    assert document.getObject(name) is None
    document.recompute()
    assert stale_or_invalid(document) == []


# --- Création d'un assemblage entre pièces qui ne sont pas d'équerre ---------------------------


def test_assemblage_impossible_refuse_avant_tout_recalcul(document: Any) -> None:
    """La commande passe ``feasible_joint`` (mot-clé ``check``) : le refus vient avant le premier
    recalcul, donc sans trace de FreeCAD ; la transaction abandonnée ne laisse rien."""
    document.UndoMode = 1  # sans historique, abandonner la transaction ne retire rien
    host = api.make_wood_part(600, 100, 20, "chene", doc=document)
    guest = api.make_wood_part(400, 100, 20, "chene", doc=document)
    guest.Placement = App.Placement(App.Vector(300, 0, 0), App.Rotation(App.Vector(0, 0, 1), 30))
    document.recompute()
    before = {obj.Name for obj in document.Objects}
    document.openTransaction("Créer un assemblage tenon-mortaise")
    with pytest.raises(ValueError, match="équerre") as raised:
        api.make_mortise_tenon(host, guest, check=feasible.feasible_joint)
    document.abortTransaction()
    assert str(raised.value).count("équerre") == 1  # un seul message
    assert {obj.Name for obj in document.Objects} == before  # rien de créé
    document.recompute()
    assert stale_or_invalid(document) == []


def test_assemblage_possible_cree_par_la_commande(document: Any) -> None:
    bureau = build_parts(document)
    joint = api.make_dowels(bureau.parts["JG"], bureau.parts["V"], check=feasible.feasible_joint)
    assert "Invalid" not in joint.State
    assert stale_or_invalid(document) == []
