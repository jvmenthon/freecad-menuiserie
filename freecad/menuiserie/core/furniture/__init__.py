# SPDX-License-Identifier: LGPL-2.1-or-later
"""Ensembles (J4a) : règles de suivi des membres et liaisons, en Python pur (ADR 0009).

Ce module est une façade : il ré-exporte l'API publique des sous-modules et ne contient aucune
logique. Enchaînement : ``with_default_options`` (options par défaut des nouveaux membres) →
``follow_rules`` (rangée, position et cote affines de chaque membre, ADR 0019) →
``bindings_for`` (expressions FreeCAD) ; avant un redimensionnement ou un changement
d'épaisseur, ``predict``, ``check_resize`` et ``check_thickness``.
"""

from __future__ import annotations

from freecad.menuiserie.core.furniture._bindings import (
    bindings_for,
    bound_by_workshop,
    driven_properties,
    expression_text,
    is_driven,
    label_reference,
    piece_reference,
    same_binding,
)
from freecad.menuiserie.core.furniture._blocked import check_kept
from freecad.menuiserie.core.furniture._check import (
    check_membership,
    check_resize,
    check_thickness,
    predict,
)
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
from freecad.menuiserie.core.furniture._follow import FollowRule, Rules, follow_rules
from freecad.menuiserie.core.furniture._gaps import gap_values
from freecad.menuiserie.core.furniture._linear import Linear
from freecad.menuiserie.core.furniture._model import (
    Binding,
    BlockedRowError,
    Edge,
    FurnitureAxis,
    FurnitureBox,
    FurnitureError,
    InteriorMode,
    KeptGap,
    Member,
    NoticeKind,
    gap_term,
)
from freecad.menuiserie.core.furniture._rows import Row
from freecad.menuiserie.core.furniture._spans import Span, edge_distances, member_spans
from freecad.menuiserie.core.notice import Notice

__all__ = [
    "Binding",
    "BlockedRowError",
    "Edge",
    "EdgeEdit",
    "Follow",
    "FollowRule",
    "FurnitureAxis",
    "FurnitureBox",
    "FurnitureError",
    "InteriorMode",
    "KeptGap",
    "Linear",
    "Member",
    "Notice",
    "NoticeKind",
    "Row",
    "Rules",
    "Span",
    "bindings_for",
    "bound_by_workshop",
    "check_kept",
    "check_membership",
    "check_resize",
    "check_thickness",
    "default_fixed",
    "driven_edges",
    "driven_properties",
    "edge_distances",
    "edge_edit",
    "expression_text",
    "fixed_by_default",
    "follow_rules",
    "follow_summary",
    "gap_term",
    "gap_values",
    "is_driven",
    "label_reference",
    "member_spans",
    "piece_reference",
    "predict",
    "same_binding",
    "with_default_options",
]
