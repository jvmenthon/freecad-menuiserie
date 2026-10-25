# SPDX-License-Identifier: LGPL-2.1-or-later
"""Distances gardées entre deux pièces (ADR 0022, règles 1 bis et 4.2 bis de la rangée).

Module privé : la façade ``core.furniture`` ré-exporte l'API publique. Une Distance gardée est un
bloc rigide virtuel entre une face de la pièce ``a`` et une face de la pièce ``b`` sur un axe de
l'ensemble : les deux pièces sont en vis-à-vis sur cet axe, et l'intervalle de leurs faces vaut
``Name.Value`` (une seule cellule) ou des constantes figées (coupé par une autre face).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence

from freecad.menuiserie.core.furniture._model import FurnitureAxis, KeptGap, Member, gap_term
from freecad.menuiserie.core.furniture._spans import Span, Spans, square_spans


def distinct_gaps(members: Iterable[Member], square: Iterable[str]) -> tuple[KeptGap, ...]:
    """Distances gardées des ``members`` (sans doublon, dans l'ordre) dont les deux pièces sont
    d'équerre (clés ``square``)."""
    kept = set(square)
    found: dict[str, KeptGap] = {}
    for member in members:
        for gap in member.gaps:
            if gap.a in kept and gap.b in kept:
                found.setdefault(gap.key, gap)
    return tuple(found.values())


def partners(key: str, axis: FurnitureAxis, gaps: Sequence[KeptGap]) -> list[str]:
    """Pièces reliées à ``key`` par une Distance gardée sur ``axis`` (règle 1 bis)."""
    found: list[str] = []
    for gap in gaps:
        if gap.axis is axis and key in (gap.a, gap.b):
            found.append(gap.b if gap.a == key else gap.a)
    return found


def face_of(span: Span, at_end: bool) -> float:
    """Coordonnée de la face de fin (``at_end``) ou de début de ``span``."""
    return span.hi if at_end else span.lo


def gap_length(gap: KeptGap, spans: Mapping[str, Spans]) -> float:
    """Distance actuelle entre les deux faces de ``gap`` (mm)."""
    first = face_of(spans[gap.a][gap.axis], gap.a_end)
    second = face_of(spans[gap.b][gap.axis], gap.b_end)
    return abs(second - first)


def gap_values(members: Sequence[Member]) -> dict[str, float]:
    """Valeur actuelle de chaque Distance gardée (clé de terme ``gap_term`` → mm), pour
    ``Linear.at`` et ``Linear.frozen``."""
    spans = {m.key: found for m in members if (found := square_spans(m)) is not None}
    return {
        gap_term(gap.key): gap_length(gap, spans) for gap in distinct_gaps(members, spans.keys())
    }
