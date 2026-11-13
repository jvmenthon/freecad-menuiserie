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
from freecad.menuiserie.core.edges._diagram import (
    HIDDEN_FACES,
    NET_CELLS,
    BoxView,
    Cell,
    DrawnEdge,
    DrawnFace,
    Hit,
    box_hit,
    box_view,
    face_corners,
    face_ring_codes,
    net_cells,
    net_hit,
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
from freecad.menuiserie.core.edges._layout import SIDES, face_sides, faces_covering
from freecad.menuiserie.core.edges._pick import edge_ends, edges_at, face_at, nearest_edge

__all__ = [
    "BROKEN_EDGE_MM",
    "FACE_NAMES",
    "FAMILIES",
    "HIDDEN_FACES",
    "MAX_SIZE_RATIO",
    "MIN_SIZE_MM",
    "NET_CELLS",
    "OVERSHOOT_MM",
    "SIDES",
    "BoxView",
    "Cell",
    "DrawnEdge",
    "DrawnFace",
    "EdgeError",
    "EdgeFamily",
    "EdgeId",
    "FamilyStrategy",
    "Hit",
    "SecondSize",
    "all_edges",
    "box_hit",
    "box_view",
    "broken_edge_cut",
    "edge_code",
    "edge_cut",
    "edge_ends",
    "edges_at",
    "face_at",
    "face_corners",
    "face_edges",
    "face_ring_codes",
    "face_sides",
    "faces_covering",
    "family_for",
    "loop_edges",
    "nearest_edge",
    "net_cells",
    "net_hit",
    "parse_edge",
    "parse_face",
]
