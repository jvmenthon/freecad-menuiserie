# SPDX-License-Identifier: LGPL-2.1-or-later
"""Suppression d'une pièce usinée qui porte des assemblages : la fonction de choix injectée décide
(fenêtre « assemblage lié »), une seule transaction annulable, aucun objet détruit supprimé deux
fois. ``ui_delete`` rejoue ce que fait la commande « Supprimer » de FreeCAD autour de ``onDelete``
(``delete_machined_part``) : transaction, ``onDelete``, puis ``removeObject`` si le résultat est
vrai."""

from __future__ import annotations

from typing import Any

import pytest

from tests.integration.bureau import build_parts
from tests.integration.cadre import stale_or_invalid

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
api = pytest.importorskip("freecad.menuiserie.api")
machined = pytest.importorskip("freecad.menuiserie.features.machined_part")
drag_joints = pytest.importorskip("freecad.menuiserie.features.drag_joints")


class Chooser:
    """Fonction de choix de test (la fenêtre ne se clique pas hors écran)."""

    def __init__(self, answer: bool) -> None:
        self.answer = answer
        self.asked: list[tuple[str, list[str]]] = []

    def __call__(self, part: str, labels: Any) -> bool:
        self.asked.append((part, list(labels)))
        return self.answer


def assembled(document: Any, *sides: str) -> tuple[Any, list[Any]]:
    """Bureau de pièces avec un assemblage à tourillons du voile à chacune des ``sides``."""
    bureau = build_parts(document)
    made = [api.make_dowels(bureau.parts[side], bureau.parts["V"]) for side in sides]
    document.recompute()
    document.UndoMode = 1
    document.clearUndos()
    return bureau, made


def ui_delete(document: Any, part: Any, choose: Chooser) -> bool:
    """Suppression de ``part`` comme la commande de FreeCAD ; renvoie le résultat d'``onDelete``."""
    name = part.Name
    document.openTransaction("Delete")
    allowed: bool = drag_joints.delete_machined_part(part, choose)
    if allowed:
        document.removeObject(name)
    document.commitTransaction()
    document.recompute()
    return allowed


def test_un_assemblage_supprime_avec_la_piece(document: Any) -> None:
    bureau, [joint] = assembled(document, "JG")
    voile, joue = bureau.parts["V"], bureau.parts["JG"]
    usinee = machined.machined_part_of(voile)
    names = [joint.Name, usinee.Name]
    labels = (usinee.Label, joint.Label)
    choose = Chooser(True)
    assert ui_delete(document, usinee, choose) is False  # déjà détruite : FreeCAD n'y touche pas
    assert choose.asked == [(f"« {labels[0]} »", [f"« {labels[1]} »"])]
    assert all(document.getObject(name) is None for name in names)
    assert machined.machined_part_of(voile) is None and machined.machined_part_of(joue) is None
    assert voile.Visibility and joue.Visibility  # les brutes sont réaffichées
    assert stale_or_invalid(document) == []


def test_plusieurs_assemblages_en_une_seule_fenetre(document: Any) -> None:
    bureau, made = assembled(document, "JG", "JD")
    voile = bureau.parts["V"]
    usinee = machined.machined_part_of(voile)
    labels = sorted(f"« {joint.Label} »" for joint in made)
    names = [joint.Name for joint in made]
    choose = Chooser(True)
    assert ui_delete(document, usinee, choose) is False
    assert len(choose.asked) == 1 and sorted(choose.asked[0][1]) == labels
    assert all(document.getObject(name) is None for name in names)
    assert all(machined.machined_part_of(part) is None for part in bureau.parts.values())
    assert stale_or_invalid(document) == []


@pytest.mark.parametrize("sides", [("JG",), ("JG", "JD")])
def test_annuler_ne_change_rien(document: Any, sides: tuple[str, ...]) -> None:
    bureau, made = assembled(document, *sides)
    usinee = machined.machined_part_of(bureau.parts["V"])
    objects = [obj.Name for obj in document.Objects]
    choose = Chooser(False)
    assert ui_delete(document, usinee, choose) is False
    assert len(choose.asked) == 1
    assert [obj.Name for obj in document.Objects] == objects
    assert all(document.getObject(joint.Name) is not None for joint in made)
    assert not bureau.parts["V"].Visibility  # la brute reste cachée sous sa pièce usinée
    assert stale_or_invalid(document) == []


@pytest.mark.parametrize("sides", [("JG",), ("JG", "JD")])
def test_une_seule_transaction_annulable(document: Any, sides: tuple[str, ...]) -> None:
    bureau, made = assembled(document, *sides)
    voile = bureau.parts["V"]
    names = [joint.Name for joint in made]
    usinee = machined.machined_part_of(voile)
    ui_delete(document, usinee, Chooser(True))
    assert document.UndoNames == ["Delete"]
    document.undo()  # un seul Ctrl+Z : assemblages et pièces usinées reviennent
    assert document.UndoNames == []
    assert all(document.getObject(name) is not None for name in names)
    restored = machined.machined_part_of(voile)
    assert restored is not None and len(restored.Joints) == len(names)
    assert not voile.Visibility
    document.recompute()
    assert stale_or_invalid(document) == []


def test_sans_assemblage_la_suppression_est_normale(document: Any) -> None:
    bureau, [joint] = assembled(document, "JG")
    voile = bureau.parts["V"]
    document.removeObject(joint.Name)  # la pièce usinée garde ses liens à jour, mais reste là
    usinee = machined.machined_part_of(voile)
    assert usinee is not None and list(usinee.Joints) == []
    choose = Chooser(True)
    assert ui_delete(document, usinee, choose) is True  # FreeCAD supprime lui-même
    assert choose.asked == []  # ni fenêtre ni trace
    assert machined.machined_part_of(voile) is None
    assert voile.Visibility
    assert stale_or_invalid(document) == []


def test_l_api_garde_son_refus(document: Any) -> None:
    bureau, _ = assembled(document, "JG")
    usinee = machined.machined_part_of(bureau.parts["V"])
    with pytest.raises(ValueError, match="porte encore des assemblages"):
        api.remove_machined_part(usinee)
