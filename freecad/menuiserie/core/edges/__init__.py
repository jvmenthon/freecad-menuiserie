# SPDX-License-Identifier: LGPL-2.1-or-later
"""Profils d'arête (issue #5, ADR 0029) : calcul pur des arêtes, des sections et des coupes.

Ce module est une façade : il ré-exporte l'API publique des sous-modules et ne contient aucune
logique. Une arête se désigne par son code local (``"Z+Y-"``) ; :func:`edge_cut` renvoie la
section du profil balayée le long de l'arête (:class:`~freecad.menuiserie.core._extrusion.
Extrusion`), que ``features/`` soustrait de la pièce.
"""

from __future__ import annotations

from freecad.menuiserie.core.edges._cut import (
    MAX_SIZE_RATIO,
    MIN_SIZE_MM,
    OVERSHOOT_MM,
    broken_edge_cut,
    edge_cut,
)
from freecad.menuiserie.core.edges._families import (
    BROKEN_EDGE_MM,
    FAMILIES,
    EdgeFamily,
    FamilyStrategy,
    SecondSize,
    family_for,
)
from freecad.menuiserie.core.edges._ids import (
    FACE_NAMES,
    EdgeError,
    EdgeId,
    all_edges,
    edge_code,
    face_edges,
    loop_edges,
    parse_edge,
    parse_face,
)
from freecad.menuiserie.core.edges._pick import edges_at, nearest_edge

__all__ = [
    "BROKEN_EDGE_MM",
    "FACE_NAMES",
    "FAMILIES",
    "MAX_SIZE_RATIO",
    "MIN_SIZE_MM",
    "OVERSHOOT_MM",
    "EdgeError",
    "EdgeFamily",
    "EdgeId",
    "FamilyStrategy",
    "SecondSize",
    "all_edges",
    "broken_edge_cut",
    "edge_code",
    "edge_cut",
    "edges_at",
    "face_edges",
    "family_for",
    "loop_edges",
    "nearest_edge",
    "parse_edge",
    "parse_face",
]
