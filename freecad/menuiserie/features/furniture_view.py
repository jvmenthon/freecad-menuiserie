# SPDX-License-Identifier: LGPL-2.1-or-later
"""Membres d'un ensemble tels que le panneau les montre (J4c, critères P3 à P5).

Lecture seule : pour chaque membre, son mode, ce qu'il fait quand une cote change (colonne
« Suit »), ses six distances aux bords, ses options « fixe » et les faces pilotées par une
formule de l'utilisateur ; puis les avertissements des liaisons (``UserFormula``,
``NotSquare``, ``ThicknessKept``), traduits. Rien n'est écrit dans le document.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from freecad.menuiserie.core.furniture import (
    Edge,
    Follow,
    FurnitureBox,
    FurnitureError,
    Member,
    bindings_for,
    driven_edges,
    edge_distances,
    follow_rules,
    follow_summary,
)
from freecad.menuiserie.features.distance import is_distance
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.furniture import furniture_of, is_furniture
from freecad.menuiserie.features.furniture_bindings import notice_messages, read_members
from freecad.menuiserie.features.i18n import translated_errors
from freecad.menuiserie.features.machined_part import machined_part_of

__all__ = ["MemberView", "member_views", "shown_object"]


@dataclass(frozen=True)
class MemberView:
    """Un membre vu par le panneau. ``distances`` est vide pour un membre qui n'est pas
    d'équerre ; ``driven`` : bords dont la distance suit une formule de l'utilisateur ;
    ``locked`` : pièce aux cotes fixes."""

    obj: DocumentObject
    mode: str
    follows: tuple[Follow, ...]
    distances: Mapping[Edge, float]
    fixed: frozenset[Edge]
    driven: frozenset[Edge]
    locked: bool = False


def shown_object(member: DocumentObject) -> DocumentObject:
    """Objet visible d'un membre : la pièce usinée de sa brute, sinon le membre lui-même (une
    Distance gardée aussi, qui n'a pas de pièce usinée)."""
    if is_furniture(member) or is_distance(member):
        return member
    machined = machined_part_of(member)
    return machined if machined is not None else member


def _distances(member: Member, box: FurnitureBox) -> Mapping[Edge, float]:
    try:
        return edge_distances(member, box)
    except FurnitureError:  # pas d'équerre
        return {}


def member_views(furniture: DocumentObject) -> tuple[tuple[MemberView, ...], tuple[str, ...]]:
    """Membres de ``furniture`` (par nom) et avertissements traduits de leurs liaisons.
    ``ValueError`` traduite si une cote ou le libellé de l'ensemble est illisible."""
    members = read_members(furniture)
    rules, notices = follow_rules(members.box, members.members)
    with translated_errors():
        _bindings, formulas = bindings_for(
            str(furniture.Label),
            members.members,
            rules,
            nested=furniture_of(furniture) is not None,
        )
    views = tuple(
        MemberView(
            obj=members.objects[member.key],
            mode=member.mode.value,
            follows=follow_summary(member, rules.get(member.key)),
            distances=_distances(member, members.box),
            fixed=member.fixed or frozenset(),
            driven=driven_edges(member),
            locked=member.locked,
        )
        for member in members.members
    )
    return views, notice_messages([*notices, *formulas])
