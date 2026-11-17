# SPDX-License-Identifier: LGPL-2.1-or-later
"""Épaisseur d'une pièce d'ensemble assemblée : mêmes choix qu'une pièce seule, puis l'ensemble
est relié d'après le résultat (ADR 0060, jv 2026-11-17).

Bureau de référence : joue gauche « JG » (22 mm, x de 0 à 22), voile « V » entre les joues,
tourillons JG-V et JD-V ; ensemble de 1200 mm de large.
"""

from __future__ import annotations

from typing import Any

import pytest

App = pytest.importorskip("FreeCAD")
choice = pytest.importorskip("freecad.menuiserie.features.thickness_choice")
base = pytest.importorskip("freecad.menuiserie.features.joints.base")
bindings = pytest.importorskip("freecad.menuiserie.features.furniture_bindings")
common = pytest.importorskip("freecad.menuiserie.features.thickness_common")
furniture = pytest.importorskip("freecad.menuiserie.features.furniture")

pytestmark = pytest.mark.integration

Choice = choice.Choice


def _state(bureau: Any) -> dict[str, tuple[Any, ...]]:
    return {
        mark: (
            tuple(round(v, 6) for v in part.Placement.Base),
            part.Length.Value,
            part.Width.Value,
            part.Thickness.Value,
        )
        for mark, part in bureau.parts.items()
    }


def _all_hold(document: Any) -> bool:
    for obj in document.Objects:
        if base.is_joint(obj):
            try:
                base.plan_for(obj)
            except ValueError:
                return False
    return True


@pytest.fixture
def bureau(document: Any) -> Any:
    from tests.integration.bureau import build_desk

    return build_desk(document)


def test_piece_d_ensemble_assemblee_a_les_choix(bureau: Any) -> None:
    joue = bureau.parts["JG"]
    assert common.offers_thickness_choice(joue)
    assert not common.offers_thickness_choice(bureau.parts["P"])  # plateau sans assemblage
    edit = choice.ThicknessEdit(joue)
    conflict = edit.probe(30)
    assert conflict is not None
    assert [o.choice for o in conflict.options] == [
        Choice.AS_TYPED,
        Choice.OTHER_SIDE,
        Choice.EXTEND,
        Choice.REVERT,
    ]
    offered = {o.choice: o.reason for o in conflict.options}
    assert offered[Choice.AS_TYPED] is None and offered[Choice.OTHER_SIDE] is None
    assert "membre d'un ensemble" not in (offered[Choice.EXTEND] or "")
    edit.restore()
    edit.finish()


def test_piece_a_cotes_fixes_garde_le_comportement_de_l_ensemble(bureau: Any) -> None:
    joue = bureau.parts["JG"]
    joue.Locked = True
    assert not common.offers_thickness_choice(joue)


@pytest.mark.parametrize("picked", [Choice.AS_TYPED, Choice.OTHER_SIDE])
def test_choix_puis_ensemble_relie_d_apres_le_resultat(
    bureau: Any, document: Any, picked: Any
) -> None:
    joue = bureau.parts["JG"]
    edit = choice.ThicknessEdit(joue)
    assert edit.probe(30) is not None
    edit.apply(30, picked)
    before = _state(bureau)
    edit.finish()
    assert edit.finish() == []  # une seule fois
    document.recompute()
    assert _state(bureau) == before  # liaisons refaites d'après la géométrie : rien ne bouge
    assert joue.Thickness.Value == 30
    assert bureau.furniture.Width.Value == pytest.approx(1208)  # boîte à l'enveloppe
    assert _all_hold(document)
    assert bindings.workshop_expressions(bureau.parts["V"])  # liaisons rendues aux membres


def test_choix_de_l_autre_cote_pousse_les_pieces_assemblees(bureau: Any) -> None:
    joue, voile, droite = (bureau.parts[m] for m in ("JG", "V", "JD"))
    x_voile, x_droite = voile.Placement.Base.x, droite.Placement.Base.x
    edit = choice.ThicknessEdit(joue)
    edit.probe(30)
    edit.apply(30, Choice.OTHER_SIDE)
    assert voile.Placement.Base.x == pytest.approx(x_voile + 8)
    assert droite.Placement.Base.x == pytest.approx(x_droite + 8)
    edit.finish()


def test_saisie_trop_mince_rien_d_ecrit_puis_relie(bureau: Any, document: Any) -> None:
    joue = bureau.parts["JG"]
    start = _state(bureau)
    edit = choice.ThicknessEdit(joue)
    conflict = edit.probe(10)  # tourillons trop profonds pour 10 mm
    assert conflict is not None and conflict.preferred() is None
    assert _state(bureau) == start
    edit.finish()
    document.recompute()
    assert _state(bureau) == start
    assert _all_hold(document)


def test_liaisons_mises_de_cote_pendant_les_saisies(bureau: Any) -> None:
    voile = bureau.parts["V"]
    assert bindings.workshop_expressions(voile)
    edit = choice.ThicknessEdit(bureau.parts["JG"])
    assert not bindings.workshop_expressions(voile)
    edit.finish()
    assert bindings.workshop_expressions(voile)


def test_membre_bloque_hors_de_son_ensemble_libere(bureau: Any) -> None:
    joue = bureau.parts["JG"]
    reason = common.blocker(joue, ("Length",))
    assert reason is not None and "membre d'un ensemble" in reason
    edit = choice.ThicknessEdit(joue)  # liaisons de l'atelier mises de côté
    assert common.blocker(joue, ("Length",), bureau.furniture) is None
    with furniture.writing(joue):  # sans relier l'ensemble
        joue.Locked = True
    locked = common.blocker(joue, ("Length",), bureau.furniture)
    assert locked is not None and "cotes fixes" in locked
    assert common.blocker(joue, ("Placement",), bureau.furniture) is None
    edit.finish()
