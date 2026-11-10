# SPDX-License-Identifier: LGPL-2.1-or-later
"""Grille X x Y x Z d'une répétition : cellules, rangs, décalages, chevauchement (ADR 0045).

Une grille a une ligne par axe actif (:class:`~._model.AxisRepeat`) et un seul mode de saisie.
Chaque copie est repérée par sa **cellule** ``(i, j, k)`` (rang sur X, Y, Z) et non par un simple
rang : changer le nombre d'un axe ne change pas la cellule des copies qui restent. Le rang linéaire
(1 pour la première copie) ne sert qu'à l'ordre d'affichage : X varie le plus vite, puis Y, puis Z,
l'original ``(0, 0, 0)` n'ayant pas de rang.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from itertools import product
from typing import Final

from freecad.menuiserie.core.geometry import Vec3
from freecad.menuiserie.core.repeat._compute import (
    OVERLAP_TOLERANCE_MM,
    Resolved,
    overlaps,
    resolve_line,
)
from freecad.menuiserie.core.repeat._model import (
    GRID_TOO_MANY,
    MAX_COPIES,
    Cell,
    RepeatAxis,
    RepeatError,
    RepeatParams,
    counts_text,
)

ORIGIN: Final[Cell] = (0, 0, 0)
_INDEX: Final = {RepeatAxis.X: 0, RepeatAxis.Y: 1, RepeatAxis.Z: 2}

Extents = float | Mapping[RepeatAxis, float]


def axis_index(axis: RepeatAxis) -> int:
    """Indice 0, 1 ou 2 de l'axe X, Y ou Z dans une cellule."""
    return _INDEX[axis]


@dataclass(frozen=True)
class ResolvedAxis:
    """Réglage effectif d'un axe actif : ``cells`` éléments (original compris, au moins 2), pas
    (mm) et sens."""

    axis: RepeatAxis
    cells: int
    step: float
    reverse: bool = False

    @property
    def count(self) -> int:
        """Copies en plus de l'original le long de cet axe."""
        return self.cells - 1

    @property
    def signed_step(self) -> float:
        """Pas avec le signe du sens."""
        return -self.step if self.reverse else self.step


@dataclass(frozen=True)
class ResolvedGrid:
    """Grille effective : un :class:`ResolvedAxis` par axe actif, dans l'ordre X, Y, Z."""

    axes: tuple[ResolvedAxis, ...]

    def dims(self) -> Cell:
        """Nombre d'éléments sur X, Y et Z (1 pour un axe inactif)."""
        found = [1, 1, 1]
        for line in self.axes:
            found[axis_index(line.axis)] = line.cells
        return (found[0], found[1], found[2])

    @property
    def total(self) -> int:
        """Copies en plus de l'original : produit des nombres moins un."""
        nx, ny, nz = self.dims()
        return nx * ny * nz - 1

    def cells(self) -> tuple[Cell, ...]:
        """Cellules des copies dans l'ordre des rangs (sans l'original)."""
        return cells_of(self.dims())

    def offset(self, cell: Cell) -> Vec3:
        """Décalage (mm) de la copie de cellule ``cell`` : somme, sur chaque axe actif, de
        ``i x pas x sens``."""
        values = [0.0, 0.0, 0.0]
        for line in self.axes:
            index = axis_index(line.axis)
            values[index] = cell[index] * line.signed_step
        return Vec3(values[0], values[1], values[2])


def cells_of(dims: Cell) -> tuple[Cell, ...]:
    """Cellules d'une grille de ``dims`` éléments par axe, sans l'original, X en premier puis Y puis
    Z (ordre des rangs)."""
    nx, ny, nz = dims
    return tuple(
        (i, j, k) for k, j, i in product(range(nz), range(ny), range(nx)) if (i, j, k) != ORIGIN
    )


def rank_of(cell: Cell, dims: Cell) -> int:
    """Rang linéaire (à partir de 1) de la cellule ``cell`` dans une grille de ``dims`` ; ``0`` si
    elle n'est pas dans la grille (ou est l'original)."""
    found = cells_of(dims)
    return found.index(cell) + 1 if cell in found else 0


def _extent(extents: Extents, axis: RepeatAxis) -> float:
    return extents[axis] if isinstance(extents, Mapping) else extents


def resolve_grid(params: RepeatParams, extents: Extents) -> ResolvedGrid:
    """Nombre et pas effectifs de chaque axe actif, selon le mode de saisie commun.

    ``extents`` : cote des sources le long de chaque axe (mm), ou une seule cote pour tous les axes.
    Refus (:class:`RepeatError`) comme :func:`~._compute.resolve_line`, et si le total des copies
    dépasse ``MAX_COPIES``.
    """
    axes = []
    for line in params.lines:
        resolved = resolve_line(
            params.spacing,
            line,
            _extent(extents, line.axis),
            deduct=params.deduct_thickness,
            gap=params.end_gap,
        )
        axes.append(ResolvedAxis(line.axis, resolved.count + 1, resolved.step, line.reverse))
    grid = ResolvedGrid(tuple(axes))
    if grid.total > MAX_COPIES:
        raise RepeatError(
            GRID_TOO_MANY,
            {"counts": grid_text(grid), "count": str(grid.total), "max": str(MAX_COPIES)},
        )
    return grid


def offsets(params: RepeatParams, extents: Extents) -> tuple[Vec3, ...]:
    """Décalage de chaque copie (rangs 1 à N) : ``i x pas`` le long de chaque axe actif, inversé si
    ``reverse``. L'original n'est pas compris ; un seul axe : ``k x pas`` pour k de 1 à nombre."""
    return tuple(cell_offsets(params, extents).values())


def cell_offsets(params: RepeatParams, extents: Extents) -> dict[Cell, Vec3]:
    """Décalage de chaque copie, par cellule, dans l'ordre des rangs."""
    grid = resolve_grid(params, extents)
    return {cell: grid.offset(cell) for cell in grid.cells()}


def overlapping_axes(grid: ResolvedGrid, extents: Extents) -> tuple[RepeatAxis, ...]:
    """Axes dont le pas est inférieur à la cote des sources (copies voisines qui se chevauchent)."""
    return tuple(
        line.axis
        for line in grid.axes
        if overlaps(Resolved(line.count, line.step), _extent(extents, line.axis))
    )


def _intervals(grid: ResolvedGrid, cell: Cell, extents: Extents) -> list[tuple[float, float]]:
    """Intervalle occupé par l'élément ``cell`` sur chaque axe actif. Les axes inactifs sont les
    mêmes pour tous les éléments : ils ne départagent rien."""
    offset = grid.offset(cell)
    return [
        (
            offset.component(axis_index(line.axis)),
            offset.component(axis_index(line.axis)) + _extent(extents, line.axis),
        )
        for line in grid.axes
    ]


def grid_overlaps(grid: ResolvedGrid, extents: Extents) -> bool:
    """Vrai si deux éléments quelconques de la grille complète (original compris) se chevauchent :
    leurs boîtes (cote des sources sur chaque axe actif) se recouvrent de plus de 0,01 mm sur tous
    les axes à la fois. ``extents`` n'a besoin que des axes actifs."""
    boxes = [_intervals(grid, cell, extents) for cell in (ORIGIN, *grid.cells())]
    for index, first in enumerate(boxes):
        for second in boxes[index + 1 :]:
            if all(
                min(a[1], b[1]) - max(a[0], b[0]) > OVERLAP_TOLERANCE_MM
                for a, b in zip(first, second, strict=True)
            ):
                return True
    return False


def grid_text(grid: ResolvedGrid) -> str:
    """Nombres d'éléments par axe actif, ``4 x 3`` par exemple."""
    return counts_text(line.cells for line in grid.axes)
