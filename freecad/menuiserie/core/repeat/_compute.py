# SPDX-License-Identifier: LGPL-2.1-or-later
"""Nombre, pas et décalages effectifs d'une répétition linéaire (ADR 0043)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final

from freecad.menuiserie.core._validation import decimal_text
from freecad.menuiserie.core.geometry import Vec3
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.repeat._model import (
    MAX_COPIES,
    RepeatAxis,
    RepeatError,
    RepeatParams,
    SpacingMode,
    positive,
)

OVERLAP_TOLERANCE_MM: Final = 0.01
_COUNT_TOLERANCE: Final = 1e-6  # absorbe l'erreur de flottant de (longueur - cote) / pas

NO_ROOM: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Répétition : la longueur de {span} mm ne laisse pas de place pour {count} copies "
    "de {extent} mm ; il faut une longueur supérieure à {extent} mm.",
)
NO_COPY: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Répétition : un pas de {step} mm sur {span} mm ne laisse place à aucune copie de {extent} mm.",
)
TOO_MANY: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Répétition : un pas de {step} mm sur {span} mm donnerait {count} copies ; "
    "le maximum est {max}.",
)

_DIRECTIONS: Final = {
    RepeatAxis.X: Vec3(1.0, 0.0, 0.0),
    RepeatAxis.Y: Vec3(0.0, 1.0, 0.0),
    RepeatAxis.Z: Vec3(0.0, 0.0, 1.0),
}


@dataclass(frozen=True)
class Resolved:
    """Nombre de copies et pas (mm) effectifs d'une répétition."""

    count: int
    step: float


def resolve(params: RepeatParams, source_extent: float) -> Resolved:
    """Nombre et pas effectifs selon le mode de saisie.

    ``source_extent`` : cote de la source le long de l'axe (mm, finie et positive).
    ``CountOnSpan`` : ``pas = (longueur - cote) / nombre`` ; ``StepOnSpan`` :
    ``nombre = floor((longueur - cote) / pas)``. Refus (:class:`RepeatError`) si le pas calculé est
    nul ou négatif, si aucune copie ne tient ou si le nombre dépasse ``MAX_COPIES``.
    """
    extent = positive("extent", source_extent)
    if params.spacing is SpacingMode.COUNT_AND_STEP:
        return Resolved(params.count, params.step)
    room = params.span - extent
    if params.spacing is SpacingMode.COUNT_ON_SPAN:
        if room <= 0.0:
            raise RepeatError(
                NO_ROOM,
                {
                    "span": decimal_text(params.span),
                    "count": str(params.count),
                    "extent": decimal_text(extent),
                },
            )
        return Resolved(params.count, room / params.count)
    return _step_on_span(params, extent, room)


def _step_on_span(params: RepeatParams, extent: float, room: float) -> Resolved:
    count = math.floor(room / params.step + _COUNT_TOLERANCE)
    shown = {"step": decimal_text(params.step), "span": decimal_text(params.span)}
    if count < 1:
        raise RepeatError(NO_COPY, {**shown, "extent": decimal_text(extent)})
    if count > MAX_COPIES:
        raise RepeatError(TOO_MANY, {**shown, "count": str(count), "max": str(MAX_COPIES)})
    return Resolved(count, params.step)


def offsets(params: RepeatParams, source_extent: float) -> tuple[Vec3, ...]:
    """Décalage de chaque copie (k = 1 à nombre) : ``k x pas`` le long de l'axe, inversé si
    ``reverse``. La source (k = 0) n'est pas comprise."""
    resolved = resolve(params, source_extent)
    direction = _DIRECTIONS[params.axis]
    sign = -1.0 if params.reverse else 1.0
    return tuple(direction.scaled(sign * k * resolved.step) for k in range(1, resolved.count + 1))


def overlaps(resolved: Resolved, source_extent: float) -> bool:
    """Vrai si les copies se chevauchent (pas inférieur à la cote moins 0,01 mm).

    Avertissement non bloquant : le pas reste accepté.
    """
    return resolved.step < source_extent - OVERLAP_TOLERANCE_MM
