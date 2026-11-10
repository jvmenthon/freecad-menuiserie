# SPDX-License-Identifier: LGPL-2.1-or-later
"""Aperçu du panneau « Répéter » (jv, 2026-11-11) : pièces d'origine transparentes et teintes,
apparence d'origine rétablie ; transparence reposée après une transaction abandonnée."""

from __future__ import annotations

from typing import Any

from freecad.menuiserie.gui.task_panels.preview import PREVIEW_TRANSPARENCY, PartsPreview

BOIS = (0.6, 0.4, 0.2, 0.0)
BLEU = (70, 140, 230)


class FakeMaterial:
    def __init__(self, diffuse: tuple[float, ...]) -> None:
        self.DiffuseColor = diffuse


class FakeViewObject:
    def __init__(self) -> None:
        self.Transparency = 0
        self._appearance = [FakeMaterial(BOIS)]

    @property
    def ShapeAppearance(self) -> list[FakeMaterial]:  # pylint: disable=invalid-name
        return [FakeMaterial(m.DiffuseColor) for m in self._appearance]  # copies, comme FreeCAD

    @ShapeAppearance.setter
    def ShapeAppearance(self, value: list[FakeMaterial]) -> None:  # pylint: disable=invalid-name
        self._appearance = [FakeMaterial(m.DiffuseColor) for m in value]


class FakeObject:
    def __init__(self, name: str) -> None:
        self.Name = name
        self.ViewObject = FakeViewObject()

    def diffuse(self) -> tuple[int, ...]:
        color = self.ViewObject.ShapeAppearance[0].DiffuseColor
        return tuple(round(c * 255) for c in color[:3])


def _preview(*objects: Any) -> PartsPreview:
    return PartsPreview(lambda: list(objects), lambda _obj: True, BLEU)


def test_originale_teinte_puis_apparence_d_origine() -> None:
    piece = FakeObject("Barreau")
    preview = _preview(piece)
    assert piece.ViewObject.Transparency == PREVIEW_TRANSPARENCY
    assert piece.diffuse() == BLEU
    preview.restore()
    assert piece.ViewObject.Transparency == 0
    assert piece.ViewObject.ShapeAppearance[0].DiffuseColor == BOIS


def test_apercu_repose_apres_une_transaction_abandonnee() -> None:
    piece = FakeObject("Barreau")
    preview = _preview(piece)
    piece.ViewObject.Transparency = 0  # l'abandon de la transaction a tout rétabli
    piece.ViewObject.ShapeAppearance = [FakeMaterial(BOIS)]
    preview.sync()
    assert (piece.ViewObject.Transparency, piece.diffuse()) == (PREVIEW_TRANSPARENCY, BLEU)
    preview.restore()
    assert piece.ViewObject.ShapeAppearance[0].DiffuseColor == BOIS
