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
    bound_by_workshop,
    driven_properties,
    expression_text,
    is_driven,
    label_reference,
    same_binding,
)
from freecad.menuiserie.core.furniture._check import check_membership, check_resize, predict
from freecad.menuiserie.core.furniture._defaults import (
    default_fixed,
    fixed_by_default,
    with_default_options,
)
from freecad.menuiserie.core.furniture._edit import (
    EdgeEdit,
    Follow,
    driven_edges,
    edge_edit,
    follow_summary,
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
    NoticeKind,
)
from freecad.menuiserie.core.furniture._spans import Span, edge_distances, member_spans
from freecad.menuiserie.core.notice import Notice

__all__ = [
    "Anchor",
    "Binding",
    "Edge",
    "EdgeEdit",
    "Follow",
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
    "bound_by_workshop",
    "check_membership",
    "check_resize",
    "default_fixed",
    "driven_edges",
    "driven_properties",
    "edge_distances",
    "edge_edit",
    "expression_text",
    "fixed_by_default",
    "follow_rules",
    "follow_summary",
    "is_driven",
    "label_reference",
    "member_spans",
    "predict",
    "same_binding",
    "with_default_options",
]
