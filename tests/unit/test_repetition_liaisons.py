# SPDX-License-Identifier: LGPL-2.1-or-later
"""Expressions qui lient une copie à sa source (``features.repeat_links``), sans FreeCAD."""

from __future__ import annotations

from collections.abc import Iterator
from types import ModuleType

import pytest

from freecad.menuiserie.core.repeat import RepeatAxis
from tests.unit.aides_freecad import simulated_freecad


@pytest.fixture
def links(monkeypatch: pytest.MonkeyPatch) -> Iterator[ModuleType]:
    """``features.repeat_links`` importé dans le bloc qui isole ``features/`` des autres tests."""
    with simulated_freecad(monkeypatch):
        from freecad.menuiserie.features import repeat_links

        yield repeat_links


def test_seule_la_composante_de_l_axe_porte_le_pas(links: ModuleType) -> None:
    expressions = links.copy_expressions("Barre", "Repeat", 3, RepeatAxis.Y)
    assert expressions["Placement.Base.x"] == "Barre.Placement.Base.x"
    assert expressions["Placement.Base.z"] == "Barre.Placement.Base.z"
    assert expressions["Placement.Base.y"] == (
        "Barre.Placement.Base.y + 3 * (Repeat.Reverse ? -1 : 1) * Repeat.Step"
    )


@pytest.mark.parametrize(("axis", "component"), [("X", "x"), ("Y", "y"), ("Z", "z")])
def test_chaque_axe(links: ModuleType, axis: str, component: str) -> None:
    expressions = links.copy_expressions("S", "R", 1, RepeatAxis(axis))
    stepped = [path for path, text in expressions.items() if "Step" in text]
    assert stepped == [f"Placement.Base.{component}"]


def test_cotes_matiere_et_rotation_viennent_de_la_source(links: ModuleType) -> None:
    expressions = links.copy_expressions("S", "R", 2, RepeatAxis.X)
    assert set(expressions) == set(links.BOUND_PATHS)
    for path in ("Length", "Width", "Thickness", "Material", "GrainDirection", "LengthAllowance"):
        assert expressions[path] == f"S.{path}"
    assert expressions["Placement.Rotation"] == "S.Placement.Rotation"


def test_aucune_expression_sur_le_repere_ou_le_libelle(links: ModuleType) -> None:
    assert "Mark" not in links.BOUND_PATHS and "Label" not in links.BOUND_PATHS


@pytest.mark.parametrize(
    ("text", "cited"),
    [
        ("WoodPart.Length", True),
        ("2 * WoodPart001.Width + 1", True),
        ("Repeat.Step", True),
        ("WoodPart00.Length", False),  # un autre objet dont le nom commence pareil
        ("Autre.WoodPart.Length", False),
        ("Jeu.Value + 0", False),
    ],
)
def test_expression_qui_cite_un_objet(links: ModuleType, text: str, cited: bool) -> None:
    names = {"WoodPart", "WoodPart001", "Repeat"}
    assert links._cites(text, names) is cited  # pylint: disable=protected-access
