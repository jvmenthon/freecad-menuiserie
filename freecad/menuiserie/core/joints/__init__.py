# SPDX-License-Identifier: LGPL-2.1-or-later
"""Assemblages (J3) : stratégies de calcul pur, une par type, derrière un protocole commun.

Ce module est une façade : il ré-exporte l'API publique des sous-modules et ne contient
aucune logique. Chaque stratégie renvoie un :class:`JointPlan` (ajouts et enlèvements dans
le repère local de chaque pièce) ou lève :class:`JointError` (gabarit traduisible).
"""

from __future__ import annotations

from freecad.menuiserie.core.geometry import JointError
from freecad.menuiserie.core.joints._base import (
    MAX_COUNT,
    JointKind,
    JointPlan,
    JointStrategy,
    mm_round,
)
from freecad.menuiserie.core.joints._profile import ProfileValues
from freecad.menuiserie.core.joints._registry import STRATEGIES, strategy_for
from freecad.menuiserie.core.joints._roles import guess_roles
from freecad.menuiserie.core.joints.dowels import DowelParams
from freecad.menuiserie.core.joints.mortise_tenon import MortiseTenonParams, MortiseTenonStrategy
from freecad.menuiserie.core.joints.rabbet import RabbetParams, RabbetStrategy, RabbetValues
from freecad.menuiserie.core.joints.tongue_groove import (
    DEFAULT_TONGUE_LENGTH_MM,
    TongueGrooveParams,
    TongueGrooveStrategy,
)

__all__ = [
    "DEFAULT_TONGUE_LENGTH_MM",
    "MAX_COUNT",
    "STRATEGIES",
    "DowelParams",
    "JointError",
    "JointKind",
    "JointPlan",
    "JointStrategy",
    "MortiseTenonParams",
    "MortiseTenonStrategy",
    "ProfileValues",
    "RabbetParams",
    "RabbetStrategy",
    "RabbetValues",
    "TongueGrooveParams",
    "TongueGrooveStrategy",
    "guess_roles",
    "mm_round",
    "strategy_for",
]
