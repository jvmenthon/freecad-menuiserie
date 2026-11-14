# SPDX-License-Identifier: LGPL-2.1-or-later
"""Assemblage posé à la main sur une copie de répétition (bug de jv, 2026-11-13) : la copie
change de rang ou de pas, l'assemblage ne la suit pas et devient impossible ; il reste (il est à
l'utilisateur) et la répétition le signale, avec le remède (assembler la pièce d'origine).
"""

from __future__ import annotations

from typing import Any

import pytest

from tests.integration.cadre import placement
from tests.integration.conftest import VueRapport
from tests.integration.test_repetition_assemblages import copies, part

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
api = pytest.importorskip("freecad.menuiserie.api")
repeat_joints = pytest.importorskip("freecad.menuiserie.features.repeat_joints")
SIGNAL = "posé à la main sur une copie ne tient plus"


def invalid(doc: Any) -> list[Any]:
    return [obj for obj in doc.Objects if "Invalid" in obj.State]


def test_assemblage_a_la_main_sur_une_copie_devenu_impossible_est_signale(
    document: Any, vue_rapport: VueRapport
) -> None:
    long = part(document, "B", (500, 60, 22), placement(0, 0))
    bar = part(document, "A", (280, 40, 22), placement(140, 60, 90))
    rep = api.make_repeat([bar], api.RepeatParams(count=1, step=100.0, axis="X", copy_joints=False))
    copy = copies(rep)[0]
    by_hand = api.make_loose_tenons(long, copy)  # à la main : pas un enfant
    assert repeat_joints.origin_of(by_hand) is None
    assert invalid(document) == []
    api.edit_repeat(rep, api.RepeatParams(count=1, step=900.0, axis="X", copy_joints=False))
    assert invalid(document) == [by_hand]  # jamais supprimé
    assert any(SIGNAL in w and by_hand.Label in w for w in vue_rapport.de_niveau("Warning"))
    assert SIGNAL in repeat_joints.hand_joints_warning(rep)


def test_aucun_signalement_quand_tout_tient(document: Any, vue_rapport: VueRapport) -> None:
    long = part(document, "B", (500, 60, 22), placement(0, 0))
    bar = part(document, "A", (280, 40, 22), placement(140, 60, 90))
    rep = api.make_repeat([bar], api.RepeatParams(count=1, step=100.0, axis="X"))
    api.make_loose_tenons(long, copies(rep)[0])
    api.edit_repeat(rep, api.RepeatParams(count=1, step=110.0, axis="X"))
    assert repeat_joints.hand_joints_warning(rep) == ""
    assert not any(SIGNAL in w for w in vue_rapport.de_niveau("Warning"))
