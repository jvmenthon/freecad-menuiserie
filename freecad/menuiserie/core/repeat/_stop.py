# SPDX-License-Identifier: LGPL-2.1-or-later
"""Répétition jusqu'à une butée : longueur calculée, refus (ADR 0047).

La butée est une face, une arête, un sommet ou une pièce entière. Seul le calcul de la longueur est
ici : ``longueur`` = distance, sur l'axe et dans le sens de la répétition, entre la face de départ
des sources et la butée. Elle remplace la longueur saisie des modes « sur une longueur » (nombre ou
pas) ; avec la déduction de l'épaisseur (:attr:`RepeatParams.deduct_thickness`), la dernière copie
arrive à fleur de la butée, sans elle elle **commence** à la butée.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Final

from freecad.menuiserie.core._validation import decimal_text
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.repeat._model import RepeatAxis, RepeatError

__all__ = [
    "BEHIND",
    "NOT_A_FACE",
    "TOO_CLOSE",
    "StopKind",
    "stop_kind",
    "stop_reverse",
    "stop_span",
]

NOT_A_FACE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Répétition : la butée « {sub} » n'est ni une face, ni une arête, ni un sommet ; choisissez "
    "une face, une arête, un sommet ou une pièce entière.",
)
BEHIND: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Répétition : la butée chevauche la pièce d'origine sur l'axe {axis} (distance de "
    "{distance} mm dans le sens de la répétition) ; choisissez une butée d'un seul côté de la "
    "pièce.",
)
TOO_CLOSE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Répétition : la butée est trop proche sur l'axe {axis} : {distance} mm pour une pièce de "
    "{extent} mm ; la distance doit dépasser l'épaisseur de la pièce (ou décochez « Déduire "
    "l'épaisseur de la pièce »).",
)
_ELEMENT: Final = re.compile(r"(Face|Edge|Vertex)[1-9]\d*")


class StopKind(str, Enum):
    """Nature de la butée choisie."""

    PART = "part"
    FACE = "face"
    EDGE = "edge"
    VERTEX = "vertex"


def stop_kind(sub: str) -> StopKind:
    """Nature de la butée d'après son sous-élément : vide = pièce entière, ``FaceN`` ou
    ``EdgeN`` ou ``VertexN``. :class:`RepeatError` pour tout autre sous-élément."""
    if not sub:
        return StopKind.PART
    if _ELEMENT.fullmatch(sub) is None:
        raise RepeatError(NOT_A_FACE, {"sub": sub})
    kinds = {"Face": StopKind.FACE, "Edge": StopKind.EDGE}
    return next((kind for prefix, kind in kinds.items() if sub.startswith(prefix)), StopKind.VERTEX)


def stop_reverse(bounds: tuple[float, float], stop_bounds: tuple[float, float]) -> bool:
    """Sens de la répétition déduit de la butée : vrai (sens inverse) si le milieu de la butée
    (``stop_bounds`` : bas, haut sur l'axe) est sous le milieu des sources (``bounds``). Avec une
    butée, la case « Inverser » ne sert donc pas : la répétition va toujours vers la butée."""
    return stop_bounds[0] + stop_bounds[1] < bounds[0] + bounds[1]


def stop_span(
    bounds: tuple[float, float],
    near: float,
    axis: RepeatAxis,
    *,
    reverse: bool = False,
    deduct: bool = True,
) -> float:
    """Longueur (mm) de la répétition sur ``axis`` jusqu'à la butée.

    ``bounds`` : (bas, haut) des sources sur l'axe ; ``near`` : coordonnée du bord de la butée le
    plus proche dans le sens de la répétition (son minimum, ou son maximum si ``reverse``). La
    longueur part de la face de départ des sources (leur bas, ou leur haut si ``reverse``).
    :class:`RepeatError` si la butée est derrière l'original (distance nulle ou négative) ou, avec
    ``deduct``, plus proche que l'épaisseur des sources."""
    low, high = bounds
    distance = high - near if reverse else near - low
    shown = {"axis": axis.value, "distance": decimal_text(round(distance, 6))}
    if distance <= 0.0:
        raise RepeatError(BEHIND, shown)
    if deduct and distance < high - low:
        raise RepeatError(TOO_CLOSE, {**shown, "extent": decimal_text(high - low)})
    return distance
