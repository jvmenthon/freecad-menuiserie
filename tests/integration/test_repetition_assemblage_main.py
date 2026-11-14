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


def _hand_scene(document: Any, **values: Any) -> tuple[Any, Any, Any]:
    """Traverse de 500 mm, barreau, répétition sans recopie d'assemblage (pas de 100 mm)."""
    long = part(document, "B", (500, 60, 22), placement(0, 0))
    bar = part(document, "A", (280, 40, 22), placement(140, 60, 90))
    settings = {"count": 1, "step": 100.0, "axis": "X", "copy_joints": False, **values}
    return long, bar, api.make_repeat([bar], api.RepeatParams(**settings))


def _far(rep: Any, **values: Any) -> None:
    settings = {"count": 1, "step": 900.0, "axis": "X", "copy_joints": False, **values}
    api.edit_repeat(rep, api.RepeatParams(**settings))


def test_plusieurs_assemblages_a_la_main_pluriel_et_noms(
    document: Any, vue_rapport: VueRapport
) -> None:
    long, _bar, rep = _hand_scene(document, count=2)
    first, second = (api.make_loose_tenons(long, copy) for copy in copies(rep))
    assert invalid(document) == []
    _far(rep, count=2)
    assert set(invalid(document)) == {first, second}
    text = repeat_joints.hand_joints_warning(rep)
    assert "2 assemblages posés à la main" in text and "ne tiennent plus" in text
    assert first.Label in text and second.Label in text
    assert any("2 assemblages" in w for w in vue_rapport.de_niveau("Warning"))


def test_un_seul_assemblage_casse_parmi_plusieurs_singulier(document: Any) -> None:
    long, _bar, rep = _hand_scene(document, count=2)
    near, far = (api.make_loose_tenons(long, copy) for copy in copies(rep))
    # pas de 100 -> 300 : la copie 1 (x = 440) tient encore, la copie 2 (x = 740) non
    _far(rep, count=2, step=300.0)
    broken = invalid(document)
    assert broken == [far] and near not in broken
    text = repeat_joints.hand_joints_warning(rep)
    assert text.startswith("1 assemblage posé à la main") and "ne tient plus" in text
    assert far.Label in text and near.Label not in text


def test_enfant_devenu_impossible_n_est_pas_confondu_avec_un_assemblage_a_la_main(
    document: Any, vue_rapport: VueRapport
) -> None:
    long = part(document, "B", (500, 60, 22), placement(0, 0))
    bar = part(document, "A", (280, 40, 22), placement(140, 60, 90))
    api.make_loose_tenons(long, bar)
    document.recompute()
    rep = api.make_repeat([bar], api.RepeatParams(count=1, step=100.0, axis="X"))
    child = repeat_joints.joints_of_part(copies(rep)[0])[0]
    assert repeat_joints.origin_of(child) is not None
    rep.Step = 900.0  # simple recalcul : pas d'écriture de structure
    document.recompute()
    assert child.Name in [obj.Name for obj in invalid(document)]
    assert repeat_joints.hand_joints_warning(rep) == ""
    assert not any(SIGNAL in w for w in vue_rapport.de_niveau("Warning"))


def test_copie_dissociee_son_assemblage_n_est_plus_signale(document: Any) -> None:
    long, _bar, rep = _hand_scene(document, count=2)
    target, other = copies(rep)
    by_hand = api.make_loose_tenons(long, target)
    api.dissociate(target)
    target.Placement = placement(2000, 60, 90)  # la copie libre part : l'assemblage casse
    document.recompute()
    assert by_hand.Name in [obj.Name for obj in invalid(document)]  # jamais supprimé
    assert repeat_joints.hand_joints_warning(rep) == ""  # la copie est libre, plus à la répétition
    assert copies(rep) == [other]


def test_enfant_dissocie_sur_copie_liee_est_signale_comme_pose_a_la_main(
    document: Any,
) -> None:
    long = part(document, "B", (500, 60, 22), placement(0, 0))
    bar = part(document, "A", (280, 40, 22), placement(140, 60, 90))
    api.make_loose_tenons(long, bar)
    document.recompute()
    rep = api.make_repeat([bar], api.RepeatParams(count=1, step=100.0, axis="X"))
    child = repeat_joints.joints_of_part(copies(rep)[0])[0]
    repeat_joints.unlink_joint(child)  # dissocié : ne suit plus la copie, comme à la main
    rep.Step = 900.0  # simple recalcul : pas d'écriture de structure
    document.recompute()
    assert child.Name in [obj.Name for obj in invalid(document)]
    assert child.Label in repeat_joints.hand_joints_warning(rep)


def test_annuler_la_modification_retire_le_signalement(document: Any) -> None:
    document.UndoMode = 1
    long, _bar, rep = _hand_scene(document)
    by_hand = api.make_loose_tenons(long, copies(rep)[0])
    _far(rep)
    assert repeat_joints.hand_joints_warning(rep) != ""
    document.undo()
    document.recompute()
    assert by_hand in document.Objects and invalid(document) == []
    assert repeat_joints.hand_joints_warning(rep) == ""
    document.redo()
    document.recompute()
    assert invalid(document) == [by_hand]
    assert SIGNAL in repeat_joints.hand_joints_warning(rep)


def test_aucun_signalement_sans_transaction_ni_copie_cassee(
    document: Any, vue_rapport: VueRapport
) -> None:
    long, _bar, rep = _hand_scene(document)
    api.make_loose_tenons(long, copies(rep)[0])
    api.edit_repeat(
        rep,
        api.RepeatParams(count=1, step=900.0, axis="X", copy_joints=False),
        transaction=False,
    )
    assert not any(SIGNAL in w for w in vue_rapport.de_niveau("Warning"))  # le panneau l'affiche


def test_libelle_hostile_reste_sur_une_ligne_et_litteral(document: Any) -> None:
    long, _bar, rep = _hand_scene(document)
    by_hand = api.make_loose_tenons(long, copies(rep)[0])
    by_hand.Label = "x{y}<b>\nMenuiserie : fausse ligne " + "z" * 200
    _far(rep)
    text = repeat_joints.hand_joints_warning(rep)
    assert "\n" not in text and "{y}<b> Menuiserie : fausse ligne" in text and len(text) < 500
