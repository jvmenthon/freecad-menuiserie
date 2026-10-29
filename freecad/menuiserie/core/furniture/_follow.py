# SPDX-License-Identifier: LGPL-2.1-or-later
"""Règles de suivi des membres : position et cote affines par axe (J4a, ADR 0019).

Module privé : la façade ``core.furniture`` ré-exporte l'API publique. Pour chaque membre
d'équerre et chaque axe, la rangée du membre (``_rows``) donne la position de son origine
locale et sa cote étirée comme fonctions affines de la cote de l'ensemble et des épaisseurs.
Les formules de l'utilisateur sont écartées à la liaison (``bindings_for``).
"""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, replace

from freecad.menuiserie.core.furniture._gaps import distinct_gaps
from freecad.menuiserie.core.furniture._linear import Linear
from freecad.menuiserie.core.furniture._model import (
    FurnitureAxis,
    FurnitureBox,
    KeptGap,
    Member,
    NoticeKind,
    notice,
)
from freecad.menuiserie.core.furniture._rows import Row, SolvedRow, solve_row
from freecad.menuiserie.core.furniture._spans import Span, Spans, square_spans
from freecad.menuiserie.core.notice import Notice


@dataclass(frozen=True)
class FollowRule:
    """Règle d'un membre sur un axe : où va l'origine locale et ce que devient la cote.

    ``local`` : propriété étirée (``Length``, ``Width`` d'une pièce ; ``Width``, ``Depth``,
    ``Height`` d'un sous-ensemble), ``None`` sur l'axe de l'épaisseur (jamais étirée, ``size``
    est alors ``None``). ``position`` : coordonnée de l'origine locale, ``size`` : cote étirée.
    ``row`` : la rangée du membre sur l'axe (bloquée ou non, pièces verrouillées).
    """

    axis: FurnitureAxis
    local: str | None
    position: Linear
    size: Linear | None
    row: Row

    def __post_init__(self) -> None:
        if (self.local is None) != (self.size is None):
            raise ValueError("FollowRule : cote étirée et propriété étirée vont ensemble")


Rules = Mapping[str, tuple[FollowRule, ...]]


def _rule(axis: FurnitureAxis, span: Span, solved: SolvedRow) -> FollowRule:
    position = solved.coordinate(span.origin)
    if not span.stretchable:
        return FollowRule(axis, None, position, None, solved.row)
    size = solved.coordinate(span.hi).minus(solved.coordinate(span.lo))
    return FollowRule(axis, span.local, position, size, solved.row)


def _member_rules(
    key: str,
    box: FurnitureBox,
    members: Mapping[str, Member],
    spans: Mapping[str, Spans],
    gaps: tuple[KeptGap, ...],
) -> tuple[tuple[FollowRule, ...], bool, tuple[str, ...]]:
    """Règles du membre sur X, Y et Z, vrai si un écart fixe a dû absorber (``kept``) et clés
    des Distances gardées coupées par une autre face."""
    solved = [solve_row(key, axis, members, spans, box.size(axis), gaps) for axis in FurnitureAxis]
    rules = tuple(
        _rule(axis, spans[key][axis], one) for axis, one in zip(FurnitureAxis, solved, strict=True)
    )
    split = tuple(dict.fromkeys(name for one in solved for name in one.split))
    return rules, any(one.kept for one in solved), split


def _would_stretch(
    member: Member,
    box: FurnitureBox,
    members: Mapping[str, Member],
    spans: Mapping[str, Spans],
    gaps: tuple[KeptGap, ...],
) -> bool:
    """Vrai si les règles de ``member`` l'étireraient sur un axe sans ses cotes dessinées
    (ADR 0020, décision 8) : sa rangée est résolue comme s'il pouvait changer de cote."""
    free = replace(member, locked=False, drawn=False)
    rules, _kept, _split = _member_rules(
        member.key, box, {**members, member.key: free}, spans, gaps
    )
    return any(rule.size is not None and not rule.size.constant for rule in rules)


def follow_rules(
    box: FurnitureBox, members: Sequence[Member], keys: Collection[str] | None = None
) -> tuple[Rules, tuple[Notice, ...]]:
    """Règles de suivi de chaque membre d'équerre, par axe (X, Y, Z), et avertissements
    (``NotSquare`` : membre exclu ; ``ThicknessKept`` ; ``GapSplit`` : Distance gardée
    coupée par une autre face), seulement pour les membres ``keys``
    (tous par défaut). Chaque membre se règle sur sa rangée : tous les membres doivent donc
    être fournis. Les options ``fixed`` doivent être renseignées (``with_default_options``) :
    ``ValueError`` sinon."""
    square: dict[str, Spans] = {}
    for member in members:
        if member.fixed is None:
            raise ValueError(f"options de « {member.key} » à calculer (default_fixed)")
        found = square_spans(member)
        if found is not None:
            square[member.key] = found
    square_members = {member.key: member for member in members if member.key in square}
    gaps = distinct_gaps(members, square)
    labels = {gap.key: gap.name for gap in gaps}
    rules: dict[str, tuple[FollowRule, ...]] = {}
    notices: list[Notice] = []
    for member in members:
        wanted = keys is None or member.key in keys
        if member.key not in square:
            notices.extend([notice(NoticeKind.NOT_SQUARE, member)] if wanted else [])
            continue
        rules[member.key], kept, split = _member_rules(
            member.key, box, square_members, square, gaps
        )
        if kept and wanted:
            notices.append(notice(NoticeKind.THICKNESS_KEPT, member))
        if wanted and member.drawn and _would_stretch(member, box, square_members, square, gaps):
            notices.append(notice(NoticeKind.DRAWN_SIZE, member))
        if wanted:
            notices.extend(Notice(NoticeKind.GAP_SPLIT, {"member": labels[k]}) for k in split)
    return rules, tuple(dict.fromkeys(notices))
