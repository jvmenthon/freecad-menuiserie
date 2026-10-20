# SPDX-License-Identifier: LGPL-2.1-or-later
"""Registre figé des stratégies : une par type d'assemblage. Module privé."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any, Final

from freecad.menuiserie.core.joints._base import JointKind, JointStrategy
from freecad.menuiserie.core.joints.mortise_tenon import MortiseTenonStrategy
from freecad.menuiserie.core.joints.rabbet import RabbetStrategy
from freecad.menuiserie.core.joints.tongue_groove import TongueGrooveStrategy

STRATEGIES: Final[Mapping[JointKind, JointStrategy[Any, Any]]] = MappingProxyType(
    {
        strategy.kind: strategy
        for strategy in (MortiseTenonStrategy(), TongueGrooveStrategy(), RabbetStrategy())
    }
)


def strategy_for(kind: JointKind) -> JointStrategy[Any, Any]:
    """Stratégie du type ``kind``."""
    return STRATEGIES[kind]
