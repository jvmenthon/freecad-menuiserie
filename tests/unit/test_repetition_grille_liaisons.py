# SPDX-License-Identifier: LGPL-2.1-or-later
"""Expressions et suivi du redimensionnement d'une répétition en grille, sans FreeCAD."""

from __future__ import annotations

from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any

import pytest

from freecad.menuiserie.core.repeat import (
    AxisRepeat,
    RepeatAxis,
    RepeatParams,
    ResolvedAxis,
    ResolvedGrid,
    SpacingMode,
)
from tests.unit.aides_freecad import simulated_freecad

X, Y, Z = RepeatAxis.X, RepeatAxis.Y, RepeatAxis.Z


@pytest.fixture
def modules(monkeypatch: pytest.MonkeyPatch) -> Iterator[SimpleNamespace]:
    """``features.repeat_links``, ``repeat_follow`` et ``repeat_furniture_links`` importés dans le
    bloc qui isole ``features/`` des autres tests."""
    with simulated_freecad(monkeypatch):
        from freecad.menuiserie.features import (
            repeat_follow,
            repeat_furniture_links,
            repeat_links,
            repeat_props,
        )

        yield SimpleNamespace(
            follow=repeat_follow,
            furniture=repeat_furniture_links,
            links=repeat_links,
            props=repeat_props,
        )


def test_noms_des_proprietes_de_chaque_ligne(modules: SimpleNamespace) -> None:
    name = modules.props.line_name
    assert [name("Step", line) for line in range(3)] == ["Step", "Step2", "Step3"]
    assert [name("Reverse", line) for line in range(3)] == ["Reverse", "Reverse2", "Reverse3"]
    created = [spec.name for spec in modules.props.GRID_PROPERTIES]
    assert created == [
        f"{field}{n}" for n in (2, 3) for field in ("Axis", "Count", "Step", "Span", "Reverse")
    ]


def test_chaque_composante_porte_le_pas_de_sa_ligne(modules: SimpleNamespace) -> None:
    shifts = modules.furniture.shift_terms("Rep", (3, 2, 1), [X, Y, Z])
    assert shifts == {
        X: "3 * (Rep.Reverse ? -1 : 1) * Rep.Step",
        Y: "2 * (Rep.Reverse2 ? -1 : 1) * Rep.Step2",
        Z: "1 * (Rep.Reverse3 ? -1 : 1) * Rep.Step3",
    }
    expressions = modules.links.cell_expressions("S", shifts)
    assert expressions["Placement.Base.x"] == "S.Placement.Base.x + " + shifts[X]
    assert expressions["Placement.Base.y"] == "S.Placement.Base.y + " + shifts[Y]
    assert expressions["Placement.Base.z"] == "S.Placement.Base.z + " + shifts[Z]


def test_la_ligne_est_celle_de_l_ordre_et_non_de_l_axe(modules: SimpleNamespace) -> None:
    """Y seul : première ligne (``Step``) ; Y après X : deuxième ligne (``Step2``)."""
    alone = modules.furniture.shift_terms("R", (0, 2, 0), [Y])
    assert alone == {Y: "2 * (R.Reverse ? -1 : 1) * R.Step"}
    second = modules.furniture.shift_terms("R", (0, 2, 0), [X, Y])
    assert second == {Y: "2 * (R.Reverse2 ? -1 : 1) * R.Step2"}


def test_un_axe_a_l_original_n_a_pas_de_terme(modules: SimpleNamespace) -> None:
    shifts = modules.furniture.shift_terms("R", (0, 1, 0), [X, Y])
    assert list(shifts) == [Y]
    expressions = modules.links.cell_expressions("S", shifts)
    assert expressions["Placement.Base.x"] == "S.Placement.Base.x"


def test_copie_d_ensemble_en_grille_avec_et_sans_std_part(modules: SimpleNamespace) -> None:
    shifts = modules.furniture.shift_terms("R", (1, 2, 0), [X, Y])
    plain = modules.furniture.furniture_cell_expressions("E", shifts)
    assert plain["Origin.x"] == "E.Origin.x + " + shifts[X]
    assert plain["Origin.y"] == "E.Origin.y + " + shifts[Y]
    assert plain["Origin.z"] == "E.Origin.z"
    carried = modules.furniture.furniture_cell_expressions("E", shifts, "E_Part")
    assert carried["Origin.x"] == "E.Origin.x"  # le décalage est dans le Std Part
    assert carried["Placement.Base.x"] == "E_Part.Placement.Base.x + " + shifts[X]
    assert carried["Placement.Base.y"] == "E_Part.Placement.Base.y + " + shifts[Y]
    assert carried["Placement.Rotation"] == "E_Part.Placement.Rotation"


class Recorder:
    """Répétition factice : enregistre les expressions posées."""

    def __init__(self) -> None:
        self.expressions: dict[str, str | None] = {}
        self.ExpressionEngine: list[tuple[str, str]] = []

    def setExpression(self, path: str, text: str | None) -> None:
        self.expressions[path] = text
        self.ExpressionEngine = [(p, t) for p, t in self.expressions.items() if t is not None]


def furniture(**sizes: float) -> Any:
    return SimpleNamespace(Name="Meuble", **{k: SimpleNamespace(Value=v) for k, v in sizes.items()})


def test_le_suivi_s_applique_axe_par_axe(modules: SimpleNamespace) -> None:
    grid = ResolvedGrid((ResolvedAxis(X, 3, 150.0), ResolvedAxis(Z, 2, 100.0)))
    extents = {X: 18.0, Y: 5.0, Z: 20.0}
    repeat = Recorder()
    meuble = furniture(Width=318.0 + 402.0, Depth=500.0, Height=120.0 + 80.0)
    modules.follow.bind_follow_grid(repeat, meuble, grid, extents)
    assert repeat.expressions == {
        "Span": "Meuble.Width - 402 mm",  # X : Width, ligne 1
        "Step": "(Span - 18 mm) / 2",
        "Span2": "Meuble.Height - 80 mm",  # Z : Height, ligne 2
        "Step2": "(Span2 - 20 mm) / 1",
    }
    modules.follow.unbind_follow(repeat)
    assert all(text is None for text in repeat.expressions.values())
    assert set(repeat.expressions) == {"Span", "Step", "Span2", "Step2"}


def test_parametres_ecrits_par_le_suivi(modules: SimpleNamespace) -> None:
    params = RepeatParams(
        grid=(AxisRepeat(X, 3, 150.0), AxisRepeat(Y, 2, 60.0, reverse=True)), follow_resize=True
    )
    grid = ResolvedGrid((ResolvedAxis(X, 3, 150.0), ResolvedAxis(Y, 2, 60.0, True)))
    written = modules.follow.follow_grid_params(params, grid, {X: 18.0, Y: 40.0, Z: 1.0})
    assert written.spacing is SpacingMode.COUNT_ON_SPAN and written.follow_resize is True
    assert [(ln.axis, ln.count, ln.step, ln.span, ln.reverse) for ln in written.lines] == [
        (X, 3, 150.0, 318.0, False),
        (Y, 2, 60.0, 100.0, True),
    ]
