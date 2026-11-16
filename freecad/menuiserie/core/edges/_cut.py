# SPDX-License-Identifier: LGPL-2.1-or-later
"""Coupe d'un profil d'arête : bornes et balayage de la section (ADR 0029). Module privé."""

from __future__ import annotations

import math
from typing import Final

from freecad.menuiserie.core._extrusion import Extrusion
from freecad.menuiserie.core._validation import decimal_text
from freecad.menuiserie.core.edges._families import (
    BROKEN_EDGE_MM,
    EdgeFamily,
    SecondSize,
    family_for,
)
from freecad.menuiserie.core.edges._ids import FACE_NAMES, EdgeError, EdgeId
from freecad.menuiserie.core.geometry import Vec3
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.part_model import Dimensions

__all__ = ["MAX_SIZE_RATIO", "MIN_SIZE_MM", "OVERSHOOT_MM", "broken_edge_cut", "edge_cut"]

MIN_SIZE_MM: Final = 0.1  # cote minimale d'un profil
MAX_SIZE_RATIO: Final = 0.5  # encombrement au plus la moitié de la pièce, dans chaque sens
OVERSHOOT_MM: Final = 0.01  # dépassement du balayage à chaque bout : coupe franche

BAD_SIZE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Profil de l'arête {edge} : les cotes doivent être des nombres d'au moins {minimum} mm.",
)
TOO_BIG: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Profil de l'arête {edge} trop grand : il peut occuper au plus {first} mm le long de la "
    "face {first_face} et {second} mm le long de la face {second_face}.",
)


def _resolved(family: EdgeFamily, edge: EdgeId, a: float, b: float) -> tuple[float, float]:
    """Cotes ``(a, b)`` utilisables, ``b`` ramenée à ``a`` quand la famille l'impose."""
    strategy = family_for(family)
    numbers = (a, b)
    if not all(isinstance(n, int | float) and math.isfinite(n) for n in numbers):
        raise EdgeError(BAD_SIZE, {"edge": edge.name, "minimum": decimal_text(MIN_SIZE_MM)})
    if strategy.second is SecondSize.IGNORED or (
        strategy.second is SecondSize.SAME_IF_ZERO and b == 0
    ):
        b = a
    if a < MIN_SIZE_MM or b < MIN_SIZE_MM:
        raise EdgeError(BAD_SIZE, {"edge": edge.name, "minimum": decimal_text(MIN_SIZE_MM)})
    return float(a), float(b)


def edge_cut(
    dimensions: Dimensions, edge: EdgeId, family: EdgeFamily, a: float, b: float = 0.0
) -> Extrusion:
    """Section du profil balayée sur toute la longueur de l'arête, dans le repère local.

    ``a`` et ``b`` en mm (voir :class:`~.EdgeFamily` ; ``b == 0`` : égale à ``a`` pour le
    chanfrein et le quart de rond). Le balayage dépasse l'arête de :data:`OVERSHOOT_MM` à
    chaque bout. ``EdgeError`` si une cote est trop petite ou si l'encombrement dépasse la
    moitié de la pièce dans l'un des deux sens.
    """
    a, b = _resolved(family, edge, a, b)
    strategy = family_for(family)
    sizes = (dimensions.length, dimensions.width, dimensions.thickness)
    first, second = edge.first, edge.second
    room_first = MAX_SIZE_RATIO * sizes[second.index]  # le long de la première face
    room_second = MAX_SIZE_RATIO * sizes[first.index]  # le long de la seconde face
    extent = strategy.extent(a, b)
    if extent[0] > room_first + 1e-9 or extent[1] > room_second + 1e-9:
        raise EdgeError(
            TOO_BIG,
            {
                "edge": edge.name,
                "first": decimal_text(round(room_first, 2)),
                "first_face": FACE_NAMES[first],
                "second": decimal_text(round(room_second, 2)),
                "second_face": FACE_NAMES[second],
            },
        )
    corner = [0.0, 0.0, 0.0]
    for face in (first, second):
        corner[face.index] = sizes[face.index] if face.sign > 0 else 0.0
    corner[edge.along] = -OVERSHOOT_MM
    direction = [0.0, 0.0, 0.0]
    direction[edge.along] = 1.0
    return Extrusion(
        section=strategy.section(a, b),
        origin=Vec3.of(corner),
        u_axis=second.opposite().unit(),
        v_axis=first.opposite().unit(),
        direction=Vec3.of(direction),
        length=sizes[edge.along] + 2 * OVERSHOOT_MM,
    )


def broken_edge_cut(dimensions: Dimensions, edge: EdgeId) -> Extrusion:
    """« Arête cassée » : quart de rond préréglé à :data:`~._families.BROKEN_EDGE_MM`."""
    return edge_cut(dimensions, edge, EdgeFamily.ROUND, BROKEN_EDGE_MM)
