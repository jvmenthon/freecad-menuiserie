# SPDX-License-Identifier: LGPL-2.1-or-later
"""Liste de débit : bouts coupés en biais (AB-c, C2 et C3, ADR 0024)."""

from __future__ import annotations

import dataclasses

import pytest

from freecad.menuiserie.core.cutlist import (
    BevelCut,
    InvalidCutEntryError,
    build_cut_list,
    line_remark,
)
from tests.unit.aides_debit import entry


def with_bevels(*bevels: BevelCut, mark: str = "T1") -> object:
    return dataclasses.replace(entry(mark, (280.0, 60.0, 22.0)), bevels=bevels)


def test_coupes_differentes_ne_sont_pas_regroupees() -> None:
    entries = [
        with_bevels(BevelCut(10.0, 0.0), mark="T1"),
        with_bevels(BevelCut(10.0, 0.0), mark="T2"),
        with_bevels(BevelCut(12.0, 0.0), mark="T3"),
        with_bevels(mark="T4"),
    ]
    lines = build_cut_list(entries).lines  # type: ignore[arg-type]
    assert sorted(line.quantity for line in lines) == [1, 1, 2]


def test_mention_de_la_coupe_simple_et_composee() -> None:
    simple = build_cut_list([with_bevels(BevelCut(10.0, 0.0))]).lines[0]  # type: ignore[list-item]
    compound = build_cut_list([with_bevels(BevelCut(8.0, 8.5))]).lines[0]  # type: ignore[list-item]
    assert line_remark(simple, str) == "bout biais 10°"
    assert line_remark(compound, str) == "coupe composée 8° / lame 8.5°"


def test_pas_de_mention_d_equerre() -> None:
    line = build_cut_list([with_bevels()]).lines[0]  # type: ignore[list-item]
    assert line.bevels == ()
    assert line_remark(line, str) == ""


def test_angle_invalide_refuse() -> None:
    for angle in (-1.0, 91.0, float("nan")):
        with pytest.raises(InvalidCutEntryError):
            BevelCut(angle, 0.0)
