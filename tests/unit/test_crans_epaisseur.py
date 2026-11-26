# SPDX-License-Identifier: LGPL-2.1-or-later
"""Crans d'épaisseur d'un panneau tiré à la souris (jv, 2026-11-26) : ``core.thickness_steps``."""

from __future__ import annotations

import math

import pytest

from freecad.menuiserie.core.thickness_steps import snap_thickness, thickness_steps

_STEPS = (4.0, 6.5, 9.0, 12.0, 15.0, 18.0, 21.0, 24.0)


def test_crans_tries_sans_doublon_ni_valeur_invalide() -> None:
    assert thickness_steps([18, 6.5, 18.0, 0, -3, math.nan, math.inf, 4]) == (4.0, 6.5, 18.0)
    assert thickness_steps([]) == ()


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (18.0, 18.0),
        (19.4, 18.0),
        (19.6, 21.0),
        (16.5, 15.0),  # à égale distance : le cran du dessous
        (0.1, 4.0),  # jamais sous la plus petite
        (500.0, 24.0),  # jamais au-dessus de la plus grande
        (-math.inf, 4.0),
        (math.inf, 24.0),
        (math.nan, 4.0),
    ],
)
def test_cran_le_plus_proche(value: float, expected: float) -> None:
    assert snap_thickness(value, _STEPS) == expected


def test_un_seul_cran() -> None:
    assert snap_thickness(3.0, (19.0,)) == 19.0


def test_sans_cran_refuse() -> None:
    with pytest.raises(ValueError):
        snap_thickness(18.0, ())
