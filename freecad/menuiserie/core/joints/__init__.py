# SPDX-License-Identifier: LGPL-2.1-or-later
"""Assemblages (J3) : stratégies de calcul pur, une par type, derrière un protocole commun.

Ce module est une façade : il ré-exporte l'API publique des sous-modules et ne contient
aucune logique. Les stratégies s'obtiennent par :func:`strategy_for` ; les paramètres sont
dans les modules publics de chaque type (``core.joints.mortise_tenon``…). Chaque stratégie
renvoie un :class:`JointPlan` (ajouts et enlèvements dans le repère local de chaque pièce)
ou lève :class:`JointError` (gabarit traduisible).
"""

from __future__ import annotations

from freecad.menuiserie.core.geometry import JointError
from freecad.menuiserie.core.joints._base import (
    MAX_RATIO,
    MIN_RATIO,
    JointKind,
    JointPlan,
    JointStrategy,
    mm_round,
    mm_text,
)
from freecad.menuiserie.core.joints._registry import strategy_for
from freecad.menuiserie.core.joints._roles import guess_roles

__all__ = [
    "MAX_RATIO",
    "MIN_RATIO",
    "JointError",
    "JointKind",
    "JointPlan",
    "JointStrategy",
    "guess_roles",
    "mm_round",
    "mm_text",
    "strategy_for",
]
