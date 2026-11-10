# SPDX-License-Identifier: LGPL-2.1-or-later
"""Où ranger des lignes du panneau « Structure » quand des assemblages les relient à des pièces qui
restent (ADR 0046), sans FreeCAD ni Qt.

Les lignes déplacées, liées entre elles par un assemblage, forment une **partie** : elle va d'un
seul bloc au même endroit. Cet endroit est celui qu'on demande, ou, s'il séparerait un assemblage
d'une pièce qui reste, l'endroit cohérent le plus proche (``core/assembly_scope.destination``).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from freecad.menuiserie.core.assembly_scope import destination, keeps_assembly
from freecad.menuiserie.core.structure_move_facts import MoveFacts

__all__ = ["Part", "plan_parts"]


@dataclass(frozen=True)
class Part:
    """Lignes qui vont ensemble. ``dest`` : chaîne d'ensembles où elles vont (vide : hors
    ensemble), ``None`` s'il n'y a aucun rangement cohérent. ``piece`` et ``other`` : la première
    pièce déplacée et la pièce assemblée qui restent à l'origine d'un autre endroit (vides si
    l'endroit demandé convient)."""

    keys: tuple[str, ...]
    dest: tuple[str, ...] | None
    piece: str = ""
    other: str = ""


def _components(facts: MoveFacts, moving: Sequence[str]) -> list[list[str]]:
    """Lignes de ``moving`` regroupées par assemblage entre leurs pièces."""
    pieces = {key: facts.pieces_under(key) for key in moving}
    groups: list[list[str]] = []
    for key in moving:
        linked = [
            group
            for group in groups
            if any(facts.links.get(p, frozenset()) & pieces[k] for k in group for p in pieces[key])
        ]
        merged = [key, *(k for group in linked for k in group)]
        groups = [group for group in groups if group not in linked]
        groups.append(sorted(merged, key=moving.index))

    def first_index(group: list[str]) -> int:
        return moving.index(group[0])

    return sorted(groups, key=first_index)


def plan_parts(
    facts: MoveFacts, moving: Sequence[str], wanted: Sequence[str], *, ignore_free: bool = False
) -> list[Part]:
    """Parties de ``moving`` et endroit de chacune, quand on voudrait les ranger dans les
    ensembles ``wanted`` (du plus proche au plus éloigné ; vide : hors ensemble)."""
    moved = set[str]().union(*(facts.pieces_under(key) for key in moving))
    parts = []
    for group in _components(facts, moving):
        pairs = [
            (piece, other)
            for key in group
            for piece in sorted(facts.pieces_under(key))
            for other in sorted(facts.links.get(piece, frozenset()) - moved)
            if not (ignore_free and other not in facts.parent)
        ]
        chains = [facts.chain(other) for _piece, other in pairs]
        dest = destination(wanted, chains, ignore_free=ignore_free)
        broken = next(
            (p for p, c in zip(pairs, chains, strict=True) if not keeps_assembly(wanted, c)),
            ("", ""),
        )
        parts.append(Part(tuple(group), dest, *broken))
    return parts
