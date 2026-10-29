# SPDX-License-Identifier: LGPL-2.1-or-later
"""Empreinte arrondie d'une forme, pour le regroupement de la liste de débit (C4)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final

SIGNIFICANT_DIGITS: Final = 4


def _rounded(field: str, value: float) -> float:
    if isinstance(value, bool) or not math.isfinite(value) or value <= 0.0:
        raise ValueError(f"{field} : valeur finie et > 0 attendue")
    return float(f"{value:.{SIGNIFICANT_DIGITS - 1}e}")


@dataclass(frozen=True)
class ShapeSignature:
    """Volume (mm³), aire (mm²) et nombre de faces d'une forme dans le repère de la pièce.

    Volume et aire sont arrondis à quatre chiffres significatifs à la construction : deux formes
    égales aux arrondis près ont des empreintes égales et de même hachage.
    """

    volume: float
    area: float
    faces: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "volume", _rounded("volume", self.volume))
        object.__setattr__(self, "area", _rounded("area", self.area))
        if isinstance(self.faces, bool) or not isinstance(self.faces, int) or self.faces < 1:
            raise ValueError("faces : entier >= 1 attendu")
