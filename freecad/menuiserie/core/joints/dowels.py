# SPDX-License-Identifier: LGPL-2.1-or-later
"""Tourillons : paramètres (J3a) ; la stratégie arrive avec J3c."""

from __future__ import annotations

from dataclasses import dataclass

from freecad.menuiserie.core.joints._base import (
    count_param,
    length_param,
    offset_param,
    validate_params,
)

__all__ = ["DowelParams"]


@dataclass(frozen=True)
class DowelParams:
    """Paramètres des tourillons (mm) ; 0 = automatique."""

    diameter: float = length_param(0.0)
    dowel_length: float = length_param(0.0)
    host_depth: float = length_param(0.0)
    count: int = count_param(0)
    edge_distance: float = length_param(0.0)
    thickness_offset: float = offset_param(0.0)
    hole_clearance: float = length_param(1.0)

    def __post_init__(self) -> None:
        validate_params(self)
