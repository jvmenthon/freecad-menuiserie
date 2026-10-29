# SPDX-License-Identifier: LGPL-2.1-or-later
"""Contrôle de la matière réelle d'un enlèvement sur une forme dessinée (E3)."""

from __future__ import annotations

import math
from typing import Final

MISSING_MATERIAL_THRESHOLD: Final = 0.05


def missing_material_ratio(on_box: float, on_shape: float) -> float:
    """Part (0 à 1) de la matière à enlever qui manque sur la forme réelle.

    ``on_box`` : volume enlevé sur la boîte d'encombrement ; ``on_shape`` : volume enlevé sur la
    forme réelle (mm³). Vaut 0 si rien n'est à enlever sur la boîte. ``ValueError`` citant le
    champ si une valeur est négative ou non finie.
    """
    for field, value in (("on_box", on_box), ("on_shape", on_shape)):
        if not math.isfinite(value) or value < 0.0:
            raise ValueError(f"{field} : volume fini et >= 0 attendu")
    if on_box == 0.0:
        return 0.0
    return min(1.0, max(0.0, (on_box - on_shape) / on_box))


def missing_material_warning_due(on_box: float, on_shape: float) -> bool:
    """Vrai s'il manque **plus de** 5 % de la matière à enlever (avertissement, sans refus)."""
    return missing_material_ratio(on_box, on_shape) > MISSING_MATERIAL_THRESHOLD
