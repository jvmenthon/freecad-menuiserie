# SPDX-License-Identifier: LGPL-2.1-or-later
"""Règles de sélection par ensemble dans la vue 3D (ADR 0047)."""

from __future__ import annotations

import pytest

from freecad.menuiserie.core.selection_chain import click_target, double_click_target, up_target

CHAIN = ["meuble", "caisson", "tiroir", "facade"]


@pytest.mark.parametrize(
    ("current", "expected"),
    [
        (None, "meuble"),
        ("autre", "meuble"),
        ("meuble", "meuble"),
        ("tiroir", "tiroir"),
        ("facade", "facade"),
    ],
)
def test_clic_simple(current: str | None, expected: str) -> None:
    assert click_target(CHAIN, current) == expected


def test_clic_simple_sans_ensemble() -> None:
    assert click_target([], "x") is None


@pytest.mark.parametrize(
    ("current", "expected"),
    [
        (None, "meuble"),
        ("autre", "meuble"),
        ("meuble", "caisson"),
        ("caisson", "tiroir"),
        ("tiroir", "facade"),
        ("facade", None),  # la pièce est sélectionnée : son panneau s'ouvre
    ],
)
def test_double_clic_descend(current: str | None, expected: str | None) -> None:
    assert double_click_target(CHAIN, current) == expected


def test_double_clic_sans_ensemble() -> None:
    assert double_click_target([], None) is None


def test_double_clic_dans_le_vide_remonte() -> None:
    assert up_target(CHAIN) == "tiroir"
    assert up_target(["meuble", "caisson"]) == "meuble"
    assert up_target(["meuble"]) is None
    assert up_target([]) is None
