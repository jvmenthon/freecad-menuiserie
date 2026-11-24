# SPDX-License-Identifier: LGPL-2.1-or-later
"""Flèche du fil : cas limites de ``_dashes`` et de ``axes=False`` (sans FreeCAD)."""

from __future__ import annotations

import math
from itertools import pairwise

import pytest

from freecad.menuiserie.core.grain_band import rectangle
from freecad.menuiserie.gui.task_panels import part_axes_drawing as drawing_module
from freecad.menuiserie.gui.task_panels.part_axes_drawing import (
    DASH_RATIO,
    MAX_DASHES,
    MIN_DASHES,
    axes_drawing,
)

_dashes = drawing_module._dashes  # pylint: disable=protected-access


@pytest.mark.parametrize(
    ("start", "end", "shaft", "count"),
    [
        (0.0, 1.0, 1.0, MIN_DASHES),  # tige courte : le minimum
        (0.0, 1e6, 1.0, MAX_DASHES),  # tige très longue : le maximum
        (0.0, 60.0, 1.0, 10),  # 60 / (6 * 1) tirets
        (-50.0, 10.0, 1.0, 10),  # début négatif : même place
    ],
)
def test_dashes_nombre(start: float, end: float, shaft: float, count: int) -> None:
    assert len(_dashes(start, end, shaft)) == count


@pytest.mark.parametrize(("start", "end"), [(0.0, 100.0), (-30.0, 5.0), (12.5, 12.6)])
def test_dashes_dans_l_intervalle_et_reguliers(start: float, end: float) -> None:
    dashes = _dashes(start, end, 2.0)
    period = (end - start) / len(dashes)
    assert dashes[0][0] == pytest.approx(start)
    assert dashes[-1][1] <= end + 1e-9
    for a, b in dashes:
        assert start - 1e-9 <= a < b <= end + 1e-9
        assert b - a == pytest.approx(DASH_RATIO * period)
    starts = [a for a, _ in dashes]
    assert all(math.isclose(y - x, period) for x, y in pairwise(starts))


def test_dashes_sans_place_ou_sans_tige_aucun_tiret() -> None:
    assert not _dashes(5.0, 5.0, 1.0)  # longueur nulle
    assert not _dashes(10.0, 0.0, 1.0)  # intervalle inversé
    assert not _dashes(0.0, 10.0, 0.0)  # tige nulle
    assert not _dashes(0.0, math.nan, 1.0)


def test_fleche_seule_meme_marque_qu_avec_triedre() -> None:
    both = axes_drawing((720.0, 95.0, 45.0), grain=1)
    only = axes_drawing((720.0, 95.0, 45.0), grain=1, axes=False)
    assert only.solids == both.solids
    assert only.strokes == both.strokes[3:]


def test_fleche_seule_avec_contour_et_cas_degeneres() -> None:
    loops = rectangle(500.0, 80.0)
    assert len(axes_drawing((500.0, 80.0, 20.0), 0, loops, axes=False).strokes) == 2
    for extents in ((0.0, 80.0, 20.0), (-5.0, 80.0, 20.0), (math.nan, 80.0, 20.0)):
        assert axes_drawing(extents, 0, axes=False).strokes == ()
        assert axes_drawing(extents, 0, axes=False).solids == ()
    assert axes_drawing((500.0, 80.0, 20.0), 2, axes=False).strokes == ()  # axe de fil invalide
