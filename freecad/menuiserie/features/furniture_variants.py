# SPDX-License-Identifier: LGPL-2.1-or-later
"""Membres d'un ensemble vus sous un autre jour, pour contrôler ou suivre un changement.

Variantes de :class:`~.furniture_bindings.MemberSet` (pièces déverrouillées, Distances non
gardées, épaisseur d'avant), contrôle d'un redimensionnement avant écriture
(:func:`resize_notices`) et mise à jour de la ``Value`` des Distances gardées après un
glissement à la souris (:func:`follow_distances`, B6).
"""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import replace

from freecad.menuiserie.core.furniture import (
    BlockedRowError,
    FurnitureBox,
    Member,
    Notice,
    check_resize,
    follow_rules,
    gap_term,
    gap_values,
    predict,
)
from freecad.menuiserie.core.geometry import CONTACT_TOLERANCE_MM, PlacedBlock
from freecad.menuiserie.core.part_model import Dimensions
from freecad.menuiserie.features.freecad_types import DocumentObject, has_expression
from freecad.menuiserie.features.furniture_bindings import (
    MemberSet,
    joined_pairs,
    locked_error,
    read_members,
)

__all__ = ["follow_distances", "resize_notices", "with_locks", "with_thickness"]


def follow_distances(furniture: DocumentObject, names: Collection[str]) -> None:
    """Met à jour la ``Value`` des Distances gardées ``names`` d'après la géométrie actuelle de
    leurs pièces (glissement à la souris, B6 : ce qu'on voit est ce qu'on garde). Une ``Value``
    pilotée par une expression de l'utilisateur n'est pas touchée."""
    members = read_members(furniture)
    lengths = gap_values(members.members)
    for name, obj in members.distances.items():
        length = lengths.get(gap_term(name))
        if name not in names or length is None or has_expression(obj, "Value"):
            continue
        if abs(obj.Value.Value - length) > CONTACT_TOLERANCE_MM:
            obj.Value = length


def with_locks(members: MemberSet, keys: Collection[str], locked: bool) -> MemberSet:
    """``members`` dont les membres ``keys`` sont verrouillés (``locked``) ou déverrouillés, les
    Distances gardées de ``keys`` n'étant plus gardées si ``locked`` est faux : pour contrôler
    un changement avant d'écrire le réglage."""

    def changed(member: Member) -> Member:
        if member.key in keys:
            member = replace(member, locked=locked)
        if locked:
            return member
        return replace(member, gaps=tuple(g for g in member.gaps if g.key not in keys))

    return replace(members, members=tuple(changed(member) for member in members.members))


def with_thickness(members: MemberSet, key: str, thickness: float) -> MemberSet:
    """``members`` dont la pièce ``key`` a l'épaisseur ``thickness`` (son placement ne
    change pas) : pour retrouver la géométrie d'avant une épaisseur saisie."""
    found: list[Member] = []
    for member in members.members:
        if member.key == key and member.block is not None:
            size = member.block.dimensions
            block = PlacedBlock(
                Dimensions(size.length, size.width, thickness), member.block.placement
            )
            member = replace(member, block=block)
        found.append(member)
    return replace(members, members=tuple(found))


def resize_notices(
    furniture: DocumentObject,
    old: FurnitureBox,
    new: FurnitureBox,
    unlocked: Collection[str] = (),
) -> list[Notice]:
    """Contrôle (``check_resize``) du passage de ``old`` à ``new``, puis, pour chaque
    sous-ensemble dont les cotes changeraient, de ses propres membres. ``unlocked`` : clés des
    pièces à considérer comme déverrouillées. :class:`FurnitureError` si le redimensionnement
    est refusé, :class:`LockedPiecesError` si une rangée est bloquée par des pièces
    verrouillées."""
    members = with_locks(read_members(furniture, box=old), unlocked, False)
    rules, _ = follow_rules(old, members.members)
    try:
        notices = list(check_resize(old, new, members.members, rules, joined_pairs(members)))
    except BlockedRowError as error:
        raise locked_error(error, members.named) from error
    after = predict(new, members.members, rules)
    for member in members.members:
        moved = after.get(member.key)
        new_box = moved.box if moved is not None else None
        if member.box is not None and new_box is not None and new_box != member.box:
            inner = members.objects[member.key]
            notices.extend(resize_notices(inner, member.box, new_box, unlocked))
    return notices
