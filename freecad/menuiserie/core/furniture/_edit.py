# SPDX-License-Identifier: LGPL-2.1-or-later
"""Ce que le panneau de l'ensemble montre et modifie (J4c, critères P3 et P5).

Module privé : la façade ``core.furniture`` ré-exporte l'API publique. Pour chaque membre :
ce qu'il fait quand une cote change (colonne « Suit »), les faces pilotées par une formule de
l'utilisateur (champs inactifs) et le changement qu'entraîne une distance au bord saisie.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from freecad.menuiserie.core._validation import MAX_DIMENSION_MM, MIN_DIMENSION_MM, decimal_text
from freecad.menuiserie.core.furniture._bindings import (
    bound_by_workshop,
    is_driven,
    position_property,
)
from freecad.menuiserie.core.furniture._follow import axis_motion
from freecad.menuiserie.core.furniture._messages import TOO_LARGE, TOO_SMALL, USER_FORMULA
from freecad.menuiserie.core.furniture._model import (
    Anchor,
    Edge,
    FollowRule,
    FurnitureAxis,
    FurnitureBox,
    FurnitureError,
    Member,
)
from freecad.menuiserie.core.furniture._spans import Span, member_spans, square_spans


class Follow(str, Enum):
    """Ce que fait un membre quand une cote de l'ensemble change (colonne « Suit »), dans
    l'ordre d'affichage."""

    NOT_SQUARE = "NotSquare"  # pas d'équerre : exclu des liaisons
    FORMULA = "Formula"  # une propriété liée par l'atelier suit une formule de l'utilisateur
    STRETCHED = "Stretched"  # une cote de la pièce change
    MOVED = "Moved"  # la pièce suit un bord
    PROPORTION = "Proportion"  # la pièce garde sa proportion de la cote
    STAYS = "Stays"  # rien ne bouge


def _axis_follows(member: Member, rule: FollowRule, span: Span, size0: float) -> set[Follow]:
    position, size = axis_motion(rule, span, size0)
    found: set[Follow] = set()
    local = rule.local
    stretched = size is not None and local is not None and not size.constant
    if stretched and not is_driven(member, str(local)):
        found.add(Follow.STRETCHED)
    if not position.constant and not is_driven(member, position_property(member, rule.axis)):
        ratio = Anchor.RATIO in (rule.start, rule.end)
        found.add(Follow.PROPORTION if ratio else Follow.MOVED)
    return found


def follow_summary(
    box: FurnitureBox, member: Member, rules: tuple[FollowRule, ...] | None
) -> tuple[Follow, ...]:
    """Ce que fait ``member`` selon ses règles (``None`` : pas d'équerre, aucune règle) ;
    ``STAYS`` seulement si rien ne bouge et qu'aucune formule n'est en jeu."""
    if rules is None:
        return (Follow.NOT_SQUARE,)
    found: set[Follow] = set()
    if any(bound_by_workshop(member, prop) for prop in member.driven):
        found.add(Follow.FORMULA)
    spans = member_spans(member)
    for rule in rules:
        found |= _axis_follows(member, rule, spans[rule.axis], box.size(rule.axis))
    if not found:
        found.add(Follow.STAYS)
    return tuple(follow for follow in Follow if follow in found)


def _axis_driven(member: Member, axis: FurnitureAxis, span: Span) -> bool:
    if is_driven(member, position_property(member, axis)):
        return True
    return span.stretchable and is_driven(member, span.local)


def driven_edges(member: Member) -> frozenset[Edge]:
    """Bords dont la distance dépend d'une propriété pilotée par l'utilisateur (position ou
    cote sur cet axe) ; tous pour un membre qui n'est pas d'équerre."""
    spans = square_spans(member)
    if spans is None:
        return frozenset(Edge)
    return frozenset(edge for edge in Edge if _axis_driven(member, edge.axis, spans[edge.axis]))


@dataclass(frozen=True)
class EdgeEdit:
    """Changement d'un membre pour une distance au bord saisie : déplacement de son origine
    locale le long de ``axis`` (mm) et, si la face opposée est gardée, nouvelle cote ``size``
    de la propriété ``prop`` (``None`` : la cote ne change pas)."""

    axis: FurnitureAxis
    shift: float
    prop: str | None = None
    size: float | None = None


def _checked(member: Member, prop: str, value: float) -> float:
    if MIN_DIMENSION_MM <= value <= MAX_DIMENSION_MM:
        return value
    template = TOO_SMALL if value < MIN_DIMENSION_MM else TOO_LARGE
    text = decimal_text(round(value, 6)).replace("-", "\N{MINUS SIGN}")
    raise FurnitureError(template, {"member": member.name, "property": prop, "value": text})


def edge_edit(member: Member, box: FurnitureBox, edge: Edge, distance: float) -> EdgeEdit:
    """Distance ``distance`` (mm) entre la face ``edge`` du membre et ce bord de l'ensemble.

    La pièce est déplacée, sauf sur un axe étirable dont la distance opposée est fixe : la face
    opposée reste alors en place et la cote change. Saisir une distance ne change aucune
    option. :class:`FurnitureError` pour un membre qui n'est pas d'équerre, une face pilotée
    par une formule de l'utilisateur ou une cote hors bornes."""
    spans = member_spans(member)
    span = spans[edge.axis]
    if _axis_driven(member, edge.axis, span):
        prop = position_property(member, edge.axis)
        raise FurnitureError(USER_FORMULA, {"member": member.name, "property": prop})
    current = box.size(edge.axis) - span.hi if edge.at_end else span.lo
    move = current - distance if edge.at_end else distance - current  # face, sens de l'axe
    if not (span.stretchable and edge.opposite() in (member.fixed or frozenset())):
        return EdgeEdit(edge.axis, move)
    size = _checked(member, span.local, span.size + (move if edge.at_end else -move))
    origin_on_face = edge.at_end == span.reversed
    return EdgeEdit(edge.axis, move if origin_on_face else 0.0, span.local, size)
