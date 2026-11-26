# SPDX-License-Identifier: LGPL-2.1-or-later
"""Déplacer une copie dissociée qui défait son assemblage (signalé par jv le 2026-11-24) :
``InList`` cite un objet une fois par lien, un assemblage qui cite la pièce deux fois n'est donc
proposé et supprimé qu'une fois (plus de ``TypeError`` de ``removeObject(None)``)."""

from __future__ import annotations

from typing import Any

import pytest

from freecad.menuiserie.core.geometry import Vec3
from tests.integration.cadre import placement
from tests.integration.test_repetition_assemblages import TRAVERSE, part

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
api = pytest.importorskip("freecad.menuiserie.api")
drag = pytest.importorskip("freecad.menuiserie.features.part_drag")
drag_joints = pytest.importorskip("freecad.menuiserie.features.drag_joints")
repeat = pytest.importorskip("freecad.menuiserie.features.repeat")


def dissociated_copy(document: Any) -> tuple[Any, Any]:
    """Copie dissociée d'une traverse assemblée (assemblages recopiés) et son assemblage, qui
    cite la copie par un second lien."""
    host = part(document, "Montant", TRAVERSE, placement(0, 0))
    guest = part(document, "Traverse", (280, 60, 22), placement(60, 60, 90))
    api.make_mortise_tenon(host, guest, tenon_thickness=8)
    params = api.RepeatParams(count=1, step=30.0, axis="Z", copy_joints=True)
    rep = api.make_repeat([host, guest], params)
    copy = repeat.copies_of(rep, guest)[0]
    api.dissociate(rep)
    document.recompute()
    (joint,) = [obj for obj in copy.InList if obj.Name.startswith("MortiseTenon")]
    joint.addProperty("App::PropertyLink", "SecondLink")
    joint.SecondLink = copy
    assert [obj.Name for obj in copy.InList].count(joint.Name) == 2
    return copy, joint


def test_glisser_loin_supprime_l_assemblage_une_fois(document: Any) -> None:
    copy, joint = dissociated_copy(document)
    name = joint.Name
    asked: list[list[str]] = []

    def choose(labels: Any) -> bool:
        asked.append(list(labels))
        return True

    memento = drag.begin_drag(copy)
    drag.move_part(memento, Vec3(1000.0, 0.0, 0.0))
    messages = drag.end_drag(memento, choose)
    assert [len(labels) for labels in asked] == [1]
    assert document.getObject(name) is None
    assert len(messages) == 1


def test_supprimer_deux_fois_le_meme_assemblage(document: Any) -> None:
    _copy, joint = dissociated_copy(document)
    name = joint.Name
    drag_joints.remove_joints([joint, joint])
    assert document.getObject(name) is None


# --- Autres chemins qui parcourent InList : rotation, suppression de la pièce usinée ------------


def doubly_linked_desk(document: Any) -> tuple[Any, Any]:
    """Voile du bureau assemblé à une joue, l'assemblage citant le voile par un second lien."""
    from tests.integration.bureau import build_parts

    bureau = build_parts(document)
    voile = bureau.parts["V"]
    joint = api.make_dowels(bureau.parts["JG"], voile)
    document.recompute()
    joint.addProperty("App::PropertyLink", "SecondLink")
    joint.SecondLink = voile
    assert [obj.Name for obj in voile.InList].count(joint.Name) >= 2
    document.UndoMode = 1
    document.clearUndos()
    return voile, joint


def test_rotation_supprime_l_assemblage_cite_deux_fois_une_fois(document: Any) -> None:
    from freecad.menuiserie.core import snap

    voile, joint = doubly_linked_desk(document)
    name = joint.Name
    asked: list[list[str]] = []

    def choose(labels: Any) -> bool:
        asked.append(list(labels))
        return True

    assert drag_joints.rotate_checked(voile, snap.Turn.Z, None, choose) is True
    assert [len(labels) for labels in asked] == [1]
    assert document.getObject(name) is None


def test_supprimer_la_piece_usinee_avec_assemblage_cite_deux_fois(document: Any) -> None:
    from freecad.menuiserie.features import machined_part

    voile, joint = doubly_linked_desk(document)
    usinee = machined_part.machined_part_of(voile)
    assert usinee is not None
    names = [joint.Name, usinee.Name, voile.Name]
    asked: list[list[str]] = []

    def choose(_part: str, labels: Any) -> bool:
        asked.append(list(labels))
        return True

    assert drag_joints.delete_machined_part(usinee, choose) is False
    assert [len(labels) for labels in asked] == [1]
    assert all(document.getObject(name) is None for name in names)
