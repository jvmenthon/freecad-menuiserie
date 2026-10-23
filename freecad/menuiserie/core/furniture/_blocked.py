# SPDX-License-Identifier: LGPL-2.1-or-later
"""Refus d'un changement de cote ou d'épaisseur dans une rangée bloquée (ADR 0019, point 5).

Module privé : la façade ``core.furniture`` ré-exporte l'API publique. Une rangée est bloquée
quand aucune de ses cellules ne peut absorber la différence (pièces verrouillées, épaisseurs qui
remplissent la cote) : le changement est refusé avant toute écriture, et l'erreur nomme les
pièces verrouillées de la rangée.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from freecad.menuiserie.core._validation import decimal_text
from freecad.menuiserie.core.furniture._follow import FollowRule, Rules
from freecad.menuiserie.core.furniture._messages import (
    BLOCKED_SIZE,
    BLOCKED_SIZE_FILLED,
    BLOCKED_THICKNESS,
    BLOCKED_THICKNESS_FILLED,
    BOX_FIELDS,
)
from freecad.menuiserie.core.furniture._model import (
    BlockedRowError,
    FurnitureAxis,
    FurnitureBox,
    Member,
)
from freecad.menuiserie.core.furniture._spans import square_spans

_MINUS = "\N{MINUS SIGN}"


def size_text(value: float) -> str:
    """Cote écrite à la française pour un message (« 1300 », « 0,05 », vrai signe moins)."""
    return decimal_text(round(value, 6)).replace("-", _MINUS)


def _names(by_key: Mapping[str, Member], keys: Sequence[str]) -> str:
    return ", ".join(f"« {by_key[key].name} »" for key in keys)


def _error(
    templates: tuple[str, str], rule: FollowRule, by_key: Mapping[str, Member], **params: str
) -> BlockedRowError:
    row = rule.row
    texts = {"members": _names(by_key, row.keys), "locked": _names(by_key, row.locked), **params}
    template = templates[0] if row.locked else templates[1]
    return BlockedRowError(template, texts, locked=row.locked, members=row.keys)


def _thickness_axes(
    members: Sequence[Member], changed: Mapping[str, float]
) -> dict[str, FurnitureAxis]:
    """Axe de l'épaisseur de chaque pièce dont l'épaisseur change."""
    found: dict[str, FurnitureAxis] = {}
    for member in members:
        if member.key not in changed:
            continue
        for axis, span in (square_spans(member) or {}).items():
            if not span.stretchable:
                found[member.key] = axis
    return found


def check_blocked(
    old: FurnitureBox,
    new: FurnitureBox,
    members: Sequence[Member],
    rules: Rules,
    changed: Mapping[str, float],
) -> None:
    """Lève :class:`BlockedRowError` si la cote de l'ensemble passe de ``old`` à ``new`` ou si
    l'épaisseur d'une pièce de ``changed`` (clé → nouvelle épaisseur) change dans une rangée
    bloquée (``rules`` : règles calculées pour ``old``)."""
    by_key = {member.key: member for member in members}
    axes = _thickness_axes(members, changed)
    for member in members:
        for rule in rules.get(member.key, ()):
            if not rule.row.blocked:
                continue
            if old.size(rule.axis) != new.size(rule.axis):
                field = BOX_FIELDS[rule.axis.name.lower()]
                value = size_text(new.size(rule.axis))
                templates = (BLOCKED_SIZE, BLOCKED_SIZE_FILLED)
                raise _error(templates, rule, by_key, field=field, value=value)
            for key, axis in axes.items():
                if axis is rule.axis and key in rule.row.keys:
                    templates = (BLOCKED_THICKNESS, BLOCKED_THICKNESS_FILLED)
                    value = size_text(changed[key])
                    raise _error(templates, rule, by_key, member=by_key[key].name, value=value)
