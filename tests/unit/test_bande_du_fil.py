# SPDX-License-Identifier: LGPL-2.1-or-later
"""Bande du fil : la marque dessinée reste sur le bois (contours variés)."""

from __future__ import annotations

import math
import random

import pytest

from freecad.menuiserie.core.grain_band import grain_band
from freecad.menuiserie.gui.task_panels.part_axes_drawing import axes_drawing

Loops = tuple[list[tuple[float, float]], ...]


def _inside(loops: Loops, x: float, y: float) -> bool:
    odd = False
    for loop in loops:
        for a, b in zip(loop, [*loop[1:], loop[0]], strict=True):
            if (a[1] > y) != (b[1] > y) and x < a[0] + (y - a[1]) / (b[1] - a[1]) * (b[0] - a[0]):
                odd = not odd
    return odd


def _contours(seed: int) -> list[Loops]:
    rng = random.Random(seed)  # noqa: S311
    found: list[Loops] = []
    for _ in range(40):
        n = rng.randint(3, 10)
        radii = [rng.uniform(80, 500) for _ in range(n)]
        found.append(
            (
                [
                    (
                        500 + r * math.cos(2 * math.pi * i / n),
                        500 + r * math.sin(2 * math.pi * i / n),
                    )
                    for i, r in enumerate(radii)
                ],
            )
        )
    found.append(
        (
            [(0, 0), (800, 0), (800, 200), (300, 200), (300, 500), (0, 500)],
            [(50, 50), (250, 50), (250, 150), (50, 150)],
        )
    )
    return found


@pytest.mark.parametrize("axis", [0, 1])
def test_marque_dessinee_reste_sur_le_bois(axis: int) -> None:
    for loops in _contours(3):
        drawing = axes_drawing((1000.0, 1000.0, 18.0), axis, loops)
        points = [p for s in drawing.solids for face in s.faces for p in face]
        points += [p for stroke in drawing.strokes[3:] for line in stroke.lines for p in line]
        for p in points:
            near = (
                _inside(loops, p.x + dx, p.y + dy) for dx in (-1e-4, 1e-4) for dy in (-1e-4, 1e-4)
            )
            assert any(near), (loops, p)


@pytest.mark.parametrize("axis", [0, 1])
def test_bande_entierement_dans_le_bois(axis: int) -> None:
    for loops in _contours(1):
        band = grain_band(loops, axis)
        if band is None:
            continue
        for i in range(15):
            for j in range(15):
                u = band.start + band.length * (0.0005 + 0.999 * i / 14)
                v = band.across + band.width * (j / 14 - 0.5) * 0.999
                x, y = (u, v) if axis == 0 else (v, u)
                assert _inside(loops, x, y), (loops, band, x, y)
