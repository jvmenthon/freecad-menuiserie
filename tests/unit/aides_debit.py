# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fabriques de pièces et d'entrées pour les tests de ``core.cutlist`` (J2b)."""

from __future__ import annotations

from typing import Any

from freecad.menuiserie.core.cutlist import NO_ADDITIONS, CutEntry
from freecad.menuiserie.core.materials import MaterialKind
from freecad.menuiserie.core.part_model import (
    Allowances,
    Dimensions,
    GrainDirection,
    PartRecord,
    default_allowances,
)

OAK_DENSITY = 710.0
PLYWOOD_DENSITY = 600.0
SIZE = (800.0, 100.0, 22.0)


def record(
    mark: str = "M1",
    size: tuple[float, float, float] = SIZE,
    *,
    material: str = "chene",
    kind: MaterialKind = MaterialKind.SOLID,
    allowances: Allowances | None = None,
    grain: GrainDirection = GrainDirection.LENGTH,
) -> PartRecord:
    """Pièce de ``size`` (L, l, e) ; surcotes par défaut de la famille si non précisées."""
    return PartRecord(
        mark=mark,
        material_id=material,
        material_name=material.capitalize(),
        kind=kind,
        finished=Dimensions(*size),
        allowances=default_allowances(kind) if allowances is None else allowances,
        grain=grain,
        density=PLYWOOD_DENSITY if kind is MaterialKind.PLYWOOD else OAK_DENSITY,
    )


def entry(
    mark: str = "M1",
    size: tuple[float, float, float] = SIZE,
    *,
    quantity: int = 1,
    additions: Allowances = NO_ADDITIONS,
    furniture: str = "",
    **options: Any,
) -> CutEntry:
    """Entrée de débit (chêne massif par défaut) ; ``options`` va à :func:`record`."""
    return CutEntry(record(mark, size, **options), quantity, additions, furniture)


def plywood(mark: str = "P1", size: tuple[float, float, float] = (600.0, 400.0, 18.0)) -> CutEntry:
    """Entrée en contreplaqué (panneau, sans surcote)."""
    part = record(
        mark,
        size,
        material="cp",
        kind=MaterialKind.PLYWOOD,
    )
    return CutEntry(part)
