# SPDX-License-Identifier: LGPL-2.1-or-later
"""Épaisseur d'une pièce d'ensemble : liaisons jamais perdues si l'ensemble ne peut pas être
relié ou si leur mise de côté échoue (revue de sécurité de la PR #264, ADR 0060 point 5)."""

from __future__ import annotations

from typing import Any

import pytest

App = pytest.importorskip("FreeCAD")
choice = pytest.importorskip("freecad.menuiserie.features.thickness_choice")
reframe = pytest.importorskip("freecad.menuiserie.features.furniture_reframe")
bindings = pytest.importorskip("freecad.menuiserie.features.furniture_bindings")

pytestmark = pytest.mark.integration


@pytest.fixture
def bureau(document: Any) -> Any:
    from tests.integration.bureau import build_desk

    return build_desk(document)


def _liaisons(bureau: Any) -> dict[str, tuple[dict[str, str], dict[str, str]]]:
    return {
        mark: (dict(bindings.workshop_expressions(part)), dict(part.FurnitureBindings))
        for mark, part in bureau.parts.items()
    }


def test_ensemble_non_relie_retrouve_ses_liaisons(
    bureau: Any, document: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    avant = _liaisons(bureau)
    edit = choice.ThicknessEdit(bureau.parts["JG"])
    edit.probe(30)
    edit.apply(30, choice.Choice.OTHER_SIDE)

    def cycle(_furniture: Any) -> None:
        raise ValueError("cycle simulé")

    monkeypatch.setattr(reframe, "bind_furniture", cycle)
    with pytest.raises(ValueError, match="cycle simulé"):
        edit.finish()
    assert _liaisons(bureau) == avant
    assert bureau.furniture.Width.Value == pytest.approx(1200)  # boîte rendue
    assert edit.finish() == []  # plus rien à rendre


def test_mise_de_cote_qui_echoue_rend_tout(bureau: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    avant = _liaisons(bureau)
    original = reframe.remove_bindings
    appels: list[str] = []

    def panne(obj: Any) -> None:
        appels.append(obj.Name)
        if len(appels) == 2:
            raise RuntimeError("panne simulée")
        original(obj)

    monkeypatch.setattr(reframe, "remove_bindings", panne)
    with pytest.raises(RuntimeError):
        choice.ThicknessEdit(bureau.parts["JG"])
    monkeypatch.setattr(reframe, "remove_bindings", original)
    assert _liaisons(bureau) == avant
