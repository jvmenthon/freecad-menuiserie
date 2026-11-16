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
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.text import bounded_text, quoted_value
from freecad.menuiserie.features.distance import distances_of, is_distance
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.furniture import furniture_of, is_furniture
from freecad.menuiserie.features.furniture_bindings import (
    common_furniture,
    members_of,
    notice_messages,
    read_members,
)
from freecad.menuiserie.features.i18n import translated, translated_errors
from freecad.menuiserie.features.joints.base import is_joint
from freecad.menuiserie.features.joints.feasible import joints_in_error
from freecad.menuiserie.features.machined_part import machined_part_of

__all__ = [
    "MemberView",
    "furniture_children",
    "invalid_joints_below",
    "member_views",
    "pieces_below",
    "shown_object",
    "undone_joints",
]

_UNDONE = QT_TRANSLATE_NOOP("Menuiserie", "{label} n'est plus réalisable : {detail}")


@dataclass(frozen=True)
class MemberView:
    """Un membre vu par le panneau. ``distances`` est vide pour un membre qui n'est pas
    d'équerre ; ``driven`` : bords dont la distance suit une formule de l'utilisateur ;
    ``locked`` : pièce aux cotes fixes ; ``drawn`` : cotes dessinées (pièce en bois), fixes et
    sans option pour les libérer."""

    obj: DocumentObject
    mode: str
    follows: tuple[Follow, ...]
    distances: Mapping[Edge, float]
    fixed: frozenset[Edge]
    driven: frozenset[Edge]
    locked: bool = False
    drawn: bool = False


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
            drawn=member.drawn,
        )
        for member in members.members
    )
    return views, notice_messages([*notices, *formulas])


def pieces_below(furniture: DocumentObject) -> list[DocumentObject]:
    """Pièces de ``furniture`` et de ses sous-ensembles (sans les ensembles)."""
    return _pieces_below(furniture, set())


def _pieces_below(furniture: DocumentObject, seen: set[str]) -> list[DocumentObject]:
    # ``seen`` : un document retouché à la main pourrait citer un ensemble dans lui-même.
    if furniture.Name in seen:
        return []
    seen.add(furniture.Name)
    found: list[DocumentObject] = []
    for member in members_of(furniture):
        found.extend(_pieces_below(member, seen) if is_furniture(member) else [member])
    return found


def invalid_joints_below(furniture: DocumentObject) -> dict[str, DocumentObject]:
    """Assemblages et quincailleries en erreur des pièces de ``furniture`` et de ses
    sous-ensembles, par nom."""
    found: dict[str, DocumentObject] = {}
    for piece in pieces_below(furniture):
        found.update(joints_in_error(piece))
    return found


def undone_joints(
    furniture: DocumentObject, invalid_before: frozenset[str] = frozenset()
) -> list[str]:
    """Un message traduit par assemblage ou quincaillerie de ``furniture`` en erreur après un
    recalcul (cote de l'ensemble qui ne lui laisse plus la place), triés par nom d'objet. Ceux
    de ``invalid_before`` (noms), en erreur avant, ne comptent pas : le panneau ne bloque pas
    « OK » pour une erreur qu'il n'a pas causée, même si une cote l'aggrave."""
    return [
        translated(
            _UNDONE,
            {
                "label": quoted_value(joint.Label),
                "detail": bounded_text(str(joint.getStatusString())),
            },
        )
        for name, joint in sorted(invalid_joints_below(furniture).items())
        if name not in invalid_before
    ]


def furniture_children(furniture: DocumentObject) -> list[DocumentObject]:
    """Enfants de l'ensemble dans l'arbre : membres visibles, assemblages dont l'ensemble est le
    plus proche contenant leurs deux pièces (même au travers d'un sous-ensemble), puis
    Distances gardées."""
    members = members_of(furniture)
    joints = {
        parent.Name: parent
        for piece in pieces_below(furniture)
        for parent in piece.InList
        if is_joint(parent)
        and parent.HostPart is not None
        and parent.GuestPart is not None
        and common_furniture(parent.HostPart, parent.GuestPart) == furniture
    }
    return [
        *(shown_object(member) for member in members),
        *(joints[n] for n in sorted(joints)),
        *distances_of(furniture),
    ]
