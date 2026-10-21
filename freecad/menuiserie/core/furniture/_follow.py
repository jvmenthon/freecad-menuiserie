# SPDX-License-Identifier: LGPL-2.1-or-later
"""Règles de suivi des membres et mouvement qui en découle (J4a, critères F5 à F7).

Module privé : la façade ``core.furniture`` ré-exporte l'API publique. Chaîne de règles d'une
face, première qui s'applique : distance fixe → bord de son côté ; sinon le mode du membre
(``Stay`` → ``START``, ``Proportional`` → ``RATIO``). Les formules de l'utilisateur sont
écartées à la liaison (``bindings_for``).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from freecad.menuiserie.core.furniture._model import (
    Anchor,
    Edge,
    FollowRule,
    FurnitureAxis,
    FurnitureBox,
    InteriorMode,
    Member,
    Notice,
    NoticeKind,
    notice,
)
from freecad.menuiserie.core.furniture._spans import Span, distances, square_spans
from freecad.menuiserie.core.geometry import CONTACT_TOLERANCE_MM

Rules = Mapping[str, tuple[FollowRule, ...]]


def thickness_edge(
    fixed: frozenset[Edge], axis: FurnitureAxis, edge_distance: Mapping[Edge, float]
) -> tuple[Edge | None, bool]:
    """Bord que suivent les deux faces d'un axe non étirable, et vrai si deux faces étaient
    fixes (la plus proche de son bord l'emporte, égalité → début)."""
    start, end = Edge.of(axis, False), Edge.of(axis, True)
    chosen = [edge for edge in (start, end) if edge in fixed]
    if len(chosen) < 2:
        return (chosen[0] if chosen else None), False
    closer_end = edge_distance[end] < edge_distance[start] - CONTACT_TOLERANCE_MM
    return (end if closer_end else start), True


def _mode_anchor(mode: InteriorMode) -> Anchor:
    return Anchor.RATIO if mode is InteriorMode.PROPORTIONAL else Anchor.START


def _face_anchor(side: Edge, member: Member, fixed: frozenset[Edge]) -> Anchor:
    return side.anchor if side in fixed else _mode_anchor(member.mode)


def _axis_rule(
    member: Member, axis: FurnitureAxis, span: Span, edge_distance: Mapping[Edge, float]
) -> tuple[FollowRule, bool]:
    fixed = member.fixed or frozenset()
    if not span.stretchable:
        edge, kept = thickness_edge(fixed, axis, edge_distance)
        anchor = edge.anchor if edge is not None else _mode_anchor(member.mode)
        return FollowRule(axis, anchor, anchor, None), kept
    start = _face_anchor(Edge.of(axis, False), member, fixed)
    end = _face_anchor(Edge.of(axis, True), member, fixed)
    return FollowRule(axis, start, end, span.local), False


def follow_rules(box: FurnitureBox, members: Sequence[Member]) -> tuple[Rules, tuple[Notice, ...]]:
    """Règles de suivi de chaque membre d'équerre, par axe (X, Y, Z), et avertissements
    (``NotSquare`` : membre exclu ; ``ThicknessKept``). Les options ``fixed`` doivent être
    renseignées (``with_default_options``) : ``ValueError`` sinon."""
    rules: dict[str, tuple[FollowRule, ...]] = {}
    notices: list[Notice] = []
    for member in members:
        if member.fixed is None:
            raise ValueError(f"options de « {member.key} » à calculer (default_fixed)")
        spans = square_spans(member)
        if spans is None:
            notices.append(notice(NoticeKind.NOT_SQUARE, member))
            continue
        edge_distance = distances(spans, box)
        results = [_axis_rule(member, axis, spans[axis], edge_distance) for axis in FurnitureAxis]
        rules[member.key] = tuple(rule for rule, _ in results)
        if any(kept for _, kept in results):
            notices.append(notice(NoticeKind.THICKNESS_KEPT, member))
    return rules, tuple(notices)


@dataclass(frozen=True)
class Linear:
    """Coordonnée ou cote affine de la cote ``C`` de l'ensemble : ``coef * C + const``."""

    coef: float
    const: float

    def at(self, size: float) -> float:
        """Valeur pour une cote d'ensemble ``size``."""
        return self.coef * size + self.const

    def minus(self, other: Linear) -> Linear:
        """Différence de deux fonctions affines."""
        return Linear(self.coef - other.coef, self.const - other.const)

    @property
    def constant(self) -> bool:
        """Vrai si la valeur ne dépend pas de la cote (aucune liaison utile)."""
        return abs(self.coef) < 1e-12


def anchor_linear(anchor: Anchor, coordinate: float, size0: float) -> Linear:
    """Coordonnée d'une face selon son ancre : ``f(START) = c``, ``f(END) = C - (C0 - c)``,
    ``f(RATIO) = C * c / C0`` (``c`` et ``C0`` à la liaison)."""
    if anchor is Anchor.START:
        return Linear(0.0, coordinate)
    if anchor is Anchor.END:
        return Linear(1.0, coordinate - size0)
    return Linear(coordinate / size0, 0.0)


def axis_motion(rule: FollowRule, span: Span, size0: float) -> tuple[Linear, Linear | None]:
    """Origine locale du membre et cote étirée (``None`` sur l'épaisseur) en fonction de la
    cote de l'ensemble sur l'axe de ``rule``."""
    if rule.local is None:
        if rule.start is Anchor.RATIO:  # le milieu garde sa proportion
            middle = (span.lo + span.hi) / 2
            return Linear(middle / size0, span.origin - middle), None
        return anchor_linear(rule.start, span.origin, size0), None
    low = anchor_linear(rule.start, span.lo, size0)
    high = anchor_linear(rule.end, span.hi, size0)
    return (high if span.reversed else low), high.minus(low)
