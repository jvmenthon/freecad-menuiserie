# SPDX-License-Identifier: LGPL-2.1-or-later
"""Options « fixe » par défaut des membres qui entrent dans l'ensemble (J4a, critères F3, F4).

Module privé : la façade ``core.furniture`` ré-exporte l'API publique. Réponse de jv à Q7
(« La pièce bouge par défaut ») : toute distance au bord est fixe par défaut, nulle ou non ; sur
l'axe de son épaisseur, qui n'est jamais étiré, une pièce ne garde que la face la plus proche de
son bord. Le menuisier décoche ensuite « fixe » là où la pièce doit rester en place.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import replace

from freecad.menuiserie.core.furniture._model import Edge, FurnitureAxis, FurnitureBox, Member
from freecad.menuiserie.core.furniture._spans import Spans, distances, square_spans
from freecad.menuiserie.core.geometry import CONTACT_TOLERANCE_MM


def fixed_by_default(distance: float) -> bool:
    """Option par défaut d'une distance au bord de l'ensemble, quelle que soit sa valeur.

    **Q7**, réponse de jv (2026-10-21) : « La pièce bouge par défaut » : toute distance est
    fixe, la pièce suit le bord de son côté. Cette fonction est le seul endroit où se décide
    l'option par défaut d'une distance.
    """
    del distance  # toute distance, nulle ou non (Q7)
    return True


def thickness_edge(
    fixed: frozenset[Edge], axis: FurnitureAxis, edge_distance: Mapping[Edge, float]
) -> Edge | None:
    """Seule face fixe d'un axe non étirable : la plus proche de son bord (égalité → début),
    ``None`` si aucune n'est fixe."""
    start, end = Edge.of(axis, False), Edge.of(axis, True)
    chosen = [edge for edge in (start, end) if edge in fixed]
    if len(chosen) < 2:
        return chosen[0] if chosen else None
    return end if edge_distance[end] < edge_distance[start] - CONTACT_TOLERANCE_MM else start


def _member_defaults(spans: Spans, box: FurnitureBox) -> frozenset[Edge]:
    edge_distance = distances(spans, box)
    fixed: set[Edge] = set()
    for axis, span in spans.items():
        sides = (Edge.of(axis, False), Edge.of(axis, True))
        chosen = frozenset(edge for edge in sides if fixed_by_default(edge_distance[edge]))
        if not span.stretchable:  # épaisseur : une seule face fixe, la plus proche de son bord
            kept = thickness_edge(chosen, axis, edge_distance)
            chosen = frozenset() if kept is None else frozenset({kept})
        fixed |= chosen
    return frozenset(fixed)


def default_fixed(box: FurnitureBox, members: Sequence[Member]) -> Mapping[str, frozenset[Edge]]:
    """Options par défaut des membres dont ``fixed`` est ``None`` ; les autres gardent les
    leurs. Un membre qui n'est pas d'équerre n'a aucune distance fixe."""
    result: dict[str, frozenset[Edge]] = {}
    for member in members:
        if member.fixed is None:
            spans = square_spans(member)
            result[member.key] = frozenset() if spans is None else _member_defaults(spans, box)
    return result


def with_default_options(box: FurnitureBox, members: Sequence[Member]) -> tuple[Member, ...]:
    """Membres dont les options manquantes (``fixed`` = ``None``) sont remplacées par les
    options par défaut ; les autres sont rendus tels quels."""
    defaults = default_fixed(box, members)
    return tuple(
        replace(member, fixed=defaults[member.key]) if member.key in defaults else member
        for member in members
    )
