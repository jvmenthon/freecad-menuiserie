# SPDX-License-Identifier: LGPL-2.1-or-later
"""Ensembles (J4a) : règles de suivi des membres et liaisons, en Python pur (ADR 0009).

Ce module est une façade : il ré-exporte l'API publique des sous-modules et ne contient aucune
logique. Enchaînement : ``with_default_options`` (options par défaut des nouveaux membres) →
``follow_rules`` (ancres de chaque face) → ``bindings_for`` (expressions FreeCAD) ; avant un
redimensionnement, ``predict`` et ``check_resize``.
"""

from __future__ import annotations

from freecad.menuiserie.core.furniture._bindings import (
    bindings_for,
    driven_properties,
    expression_text,
    is_driven,
    label_reference,
)
from freecad.menuiserie.core.furniture._check import check_membership, check_resize, predict
from freecad.menuiserie.core.furniture._defaults import (
    default_fixed,
    fixed_by_default,
    with_default_options,
)
from freecad.menuiserie.core.furniture._follow import Linear, Rules, follow_rules
from freecad.menuiserie.core.furniture._model import (
    Anchor,
    Binding,
    Edge,
    FollowRule,
    FurnitureAxis,
    FurnitureBox,
    FurnitureError,
    InteriorMode,
    Member,
    Notice,
    NoticeKind,
)
from freecad.menuiserie.core.furniture._spans import Span, edge_distances, member_spans

__all__ = [
    "Anchor",
    "Binding",
    "Edge",
    "FollowRule",
    "FurnitureAxis",
    "FurnitureBox",
    "FurnitureError",
    "InteriorMode",
    "Linear",
    "Member",
    "Notice",
    "NoticeKind",
    "Rules",
    "Span",
    "bindings_for",
    "check_membership",
    "check_resize",
    "default_fixed",
    "driven_properties",
    "edge_distances",
    "expression_text",
    "fixed_by_default",
    "follow_rules",
    "is_driven",
    "label_reference",
    "member_spans",
    "predict",
    "with_default_options",
]
