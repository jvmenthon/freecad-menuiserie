# SPDX-License-Identifier: LGPL-2.1-or-later
"""Nombre, pas et décalages effectifs d'une répétition linéaire (ADR 0043)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final

from freecad.menuiserie.core._validation import decimal_text
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.repeat._model import (
    MAX_COPIES,
    AxisRepeat,
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
NO_COPY_FREE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Répétition : un pas de {step} mm sur {span} mm ne laisse place à aucune copie "
    "(épaisseur non déduite).",
)
TOO_MANY: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Répétition : un pas de {step} mm sur {span} mm donnerait {count} copies ; "
    "le maximum est {max}.",
)


@dataclass(frozen=True)
class Resolved:
    """Nombre de copies et pas (mm) effectifs d'une répétition (le long d'un axe)."""

    count: int
    step: float


def resolve_line(
    spacing: SpacingMode,
    line: AxisRepeat,
    extent: float,
    *,
    deduct: bool = True,
    gap: bool = False,
) -> Resolved:
    """Copies (en plus de l'original) et pas effectifs de la ligne ``line`` selon le mode de saisie
    ``spacing`` ; ``extent`` : cote des sources le long de l'axe (mm, finie et positive).
    ``CountOnSpan`` : ``pas = (longueur - cote) / copies`` ; ``StepOnSpan`` : ``copies =
    floor((longueur - cote) / pas)``. ``deduct`` faux : la cote n'est pas déduite (``pas = longueur
    / copies``), la dernière copie **commence** à la fin de la longueur au lieu de s'y arrêter.
    ``gap`` vrai : la longueur est partagée en autant d'intervalles que d'éléments (``pas = longueur
    / éléments``, ``éléments = floor(longueur / pas)``), la dernière pièce s'arrête un intervalle
    avant la fin ; ``deduct`` est alors sans effet. Refus (:class:`RepeatError`) si le pas calculé
    est nul ou négatif, si aucune copie ne tient ou si le nombre dépasse ``MAX_COPIES``."""
    extent = positive("extent", extent)
    copies = line.count - 1
    if spacing is SpacingMode.COUNT_AND_STEP:
        return Resolved(copies, line.step)
    deduct = deduct and not gap
    room = line.span - (extent if deduct else 0.0)
    if spacing is SpacingMode.COUNT_ON_SPAN:
        if room <= 0.0:
            raise RepeatError(
                NO_ROOM,
                {
                    "span": decimal_text(line.span),
                    "count": str(copies),
                    "extent": decimal_text(extent),
                },
            )
        return Resolved(copies, room / (copies + 1 if gap else copies))
    return _step_on_span(line, extent, room, deduct=deduct, gap=gap)


def resolve(params: RepeatParams, source_extent: float) -> Resolved:
    """Nombre et pas effectifs de la répétition **sur un axe** (la ligne unique ; la première d'une
    grille : voir :func:`~freecad.menuiserie.core.repeat.resolve_grid`) selon le mode de saisie."""
    return resolve_line(
        params.spacing,
        params.lines[0],
        source_extent,
        deduct=params.deduct_thickness,
        gap=params.end_gap,
    )


def _step_on_span(
    line: AxisRepeat, extent: float, room: float, *, deduct: bool, gap: bool = False
) -> Resolved:
    count = math.floor(room / line.step + _COUNT_TOLERANCE) - (1 if gap else 0)
    shown = {"step": decimal_text(line.step), "span": decimal_text(line.span)}
    if count < 1:
        if not deduct:
            raise RepeatError(NO_COPY_FREE, shown)
        raise RepeatError(NO_COPY, {**shown, "extent": decimal_text(extent)})
    if count > MAX_COPIES:
        raise RepeatError(TOO_MANY, {**shown, "count": str(count), "max": str(MAX_COPIES)})
    return Resolved(count, line.step)


def overlaps(resolved: Resolved, source_extent: float) -> bool:
    """Vrai si les copies se chevauchent (pas inférieur à la cote moins 0,01 mm).

    Avertissement non bloquant : le pas reste accepté.
    """
    return resolved.step < source_extent - OVERLAP_TOLERANCE_MM
