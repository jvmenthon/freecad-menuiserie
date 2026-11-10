# SPDX-License-Identifier: LGPL-2.1-or-later
"""« Suivre le redimensionnement » (``features.repeat_follow``), sans FreeCAD."""

from __future__ import annotations

from collections.abc import Iterator
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

from freecad.menuiserie.core.repeat import RepeatAxis, RepeatParams, Resolved, SpacingMode
from tests.unit.aides_freecad import simulated_freecad


@pytest.fixture
def follow(monkeypatch: pytest.MonkeyPatch) -> Iterator[ModuleType]:
    """``features.repeat_follow`` importé dans le bloc qui isole ``features/`` des autres tests."""
    with simulated_freecad(monkeypatch):
        from freecad.menuiserie.features import repeat_follow

        yield repeat_follow


class Recorder:
    """Répétition factice : enregistre les expressions posées."""

    def __init__(self) -> None:
        self.expressions: dict[str, str | None] = {}
        self.ExpressionEngine: list[tuple[str, str]] = []

    def setExpression(self, path: str, text: str | None) -> None:
        self.expressions[path] = text
        self.ExpressionEngine = [(p, t) for p, t in self.expressions.items() if t is not None]


def furniture(**sizes: float) -> Any:
    return SimpleNamespace(
        Name="Furniture", **{k: SimpleNamespace(Value=v) for k, v in sizes.items()}
    )


def test_la_repetition_passe_en_nombre_sur_une_longueur(follow: ModuleType) -> None:
    params = RepeatParams(count=2, step=150.0, axis=RepeatAxis.Z, follow_resize=True)
    written = follow.follow_params(params, Resolved(2, 150.0), 18.0)
    assert written.spacing is SpacingMode.COUNT_ON_SPAN
    assert (written.count, written.step, written.span) == (2, 150.0, 318.0)
    assert written.follow_resize is True and written.axis is RepeatAxis.Z


@pytest.mark.parametrize(
    ("axis", "size", "margins", "expected"),
    [
        (RepeatAxis.X, "Width", 402.0, "Furniture.Width - 402 mm"),
        (RepeatAxis.Y, "Depth", 5.5, "Furniture.Depth - 5.5 mm"),
        (RepeatAxis.Z, "Height", -20.0, "Furniture.Height + 20 mm"),  # copies hors de l'ensemble
        (RepeatAxis.Z, "Height", 0.0, "Furniture.Height - 0 mm"),
    ],
)
def test_longueur_et_pas_en_expressions(
    follow: ModuleType, axis: RepeatAxis, size: str, margins: float, expected: str
) -> None:
    resolved = Resolved(2, 150.0)
    span = 18.0 + 2 * 150.0
    repeat = Recorder()
    follow.bind_follow(repeat, furniture(**{size: span + margins}), axis, 18.0, resolved)
    assert repeat.expressions == {"Span": expected, "Step": "(Span - 18 mm) / 2"}


def test_retrait_des_expressions(follow: ModuleType) -> None:
    repeat = Recorder()
    follow.bind_follow(repeat, furniture(Height=720.0), RepeatAxis.Z, 18.0, Resolved(2, 150.0))
    follow.unbind_follow(repeat)
    assert repeat.expressions == {"Span": None, "Step": None}
    follow.unbind_follow(repeat)  # sans expression : rien à retirer
    assert repeat.expressions == {"Span": None, "Step": None}
