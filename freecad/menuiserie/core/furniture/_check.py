# SPDX-License-Identifier: LGPL-2.1-or-later
"""Aperçu d'un redimensionnement, refus et cycle d'ensembles (J4a, critères F10, F11).

Module privé : la façade ``core.furniture`` ré-exporte l'API publique.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import replace
from typing import Final

from freecad.menuiserie.core._validation import MAX_DIMENSION_MM, MIN_DIMENSION_MM, decimal_text
from freecad.menuiserie.core.contact import classify
from freecad.menuiserie.core.furniture._bindings import is_driven, position_property
from freecad.menuiserie.core.furniture._follow import Rules, axis_motion
from freecad.menuiserie.core.furniture._messages import (
    FURNITURE_CYCLE,
    JOINT_LOST,
    TOO_LARGE,
    TOO_SMALL,
)
from freecad.menuiserie.core.furniture._model import (
    PIECE_AXES,
    FollowRule,
    FurnitureAxis,
    FurnitureBox,
    FurnitureError,
    Member,
    Notice,
    NoticeKind,
    notice,
)
from freecad.menuiserie.core.furniture._spans import Span, Spans, frame_block, member_spans
from freecad.menuiserie.core.geometry import CONTACT_TOLERANCE_MM, PlacedBlock, RigidTransform, Vec3
from freecad.menuiserie.core.part_model import Dimensions

_MINUS: Final = "\N{MINUS SIGN}"


def _size_text(value: float) -> str:
    return decimal_text(round(value, 6)).replace("-", _MINUS)


def _checked_size(member: Member, prop: str, value: float) -> float:
    if MIN_DIMENSION_MM <= value <= MAX_DIMENSION_MM:
        return value
    template = TOO_SMALL if value < MIN_DIMENSION_MM else TOO_LARGE
    params = {"member": member.name, "property": prop, "value": _size_text(value)}
    raise FurnitureError(template, params)


def _new_axis(
    member: Member, rule: FollowRule, span: Span, old: FurnitureBox, new: FurnitureBox
) -> tuple[float, float]:
    """Nouvelle origine locale et nouvelle étendue du membre sur l'axe de ``rule``."""
    position, size = axis_motion(rule, span, old.size(rule.axis))
    target = new.size(rule.axis)
    moved = not is_driven(member, position_property(member, rule.axis))
    origin = position.at(target) if moved else span.origin
    if size is None or rule.local is None or is_driven(member, rule.local):
        return origin, span.size
    return origin, _checked_size(member, rule.local, size.at(target))


def _moved_member(member: Member, axes: Mapping[FurnitureAxis, tuple[float, float]]) -> Member:
    origin = Vec3.of([axes[axis][0] for axis in FurnitureAxis])
    if member.block is None:
        sizes = [axes[axis][1] for axis in FurnitureAxis]
        return replace(member, box=FurnitureBox(*sizes), origin=origin)
    spans = member_spans(member)
    dimensions = [0.0, 0.0, 0.0]
    for axis in FurnitureAxis:
        dimensions[PIECE_AXES.index(spans[axis].local)] = axes[axis][1]
    placement = RigidTransform(member.block.placement.rotation, origin)
    return replace(member, block=PlacedBlock(Dimensions(*dimensions), placement))


def predict(
    old: FurnitureBox, new: FurnitureBox, members: Sequence[Member], rules: Rules
) -> Mapping[str, Member]:
    """Membres tels que les placeraient les liaisons après le passage de ``old`` à ``new``.

    Seuls les membres qui ont des règles figurent dans le résultat ; une propriété pilotée par
    l'utilisateur garde sa valeur. :class:`FurnitureError` si une cote sortirait des bornes.
    """
    result: dict[str, Member] = {}
    for member in members:
        if member.key not in rules:
            continue
        spans = member_spans(member)
        axes = {
            rule.axis: _new_axis(member, rule, spans[rule.axis], old, new)
            for rule in rules[member.key]
        }
        result[member.key] = _moved_member(member, axes)
    return result


def _block(member: Member) -> PlacedBlock:
    return member.block if member.block is not None else frame_block(member_spans(member))


def _check_joints(
    before: Mapping[str, Member], after: Mapping[str, Member], joined: Sequence[tuple[str, str]]
) -> None:
    for host, guest in joined:
        if not {host, guest} <= after.keys():
            continue
        was = classify(_block(before[host]), _block(before[guest]))
        will = classify(_block(after[host]), _block(after[guest]))
        if type(was) is not type(will):
            names = {"host": before[host].name, "guest": before[guest].name}
            raise FurnitureError(JOINT_LOST, names)


def _outside(spans: Spans, box: FurnitureBox) -> bool:
    return any(
        span.lo < -CONTACT_TOLERANCE_MM or span.hi > box.size(axis) + CONTACT_TOLERANCE_MM
        for axis, span in spans.items()
    )


def _user_formulas(
    member: Member, rules: tuple[FollowRule, ...], old: FurnitureBox, new: FurnitureBox
) -> Iterator[Notice]:
    for rule in rules:
        if old.size(rule.axis) == new.size(rule.axis):
            continue
        props = [rule.local] if rule.local is not None else []
        for prop in [*props, position_property(member, rule.axis)]:
            if is_driven(member, prop):
                yield notice(NoticeKind.USER_FORMULA, member, property=prop)


def check_resize(
    old: FurnitureBox,
    new: FurnitureBox,
    members: Sequence[Member],
    rules: Rules,
    joined: Sequence[tuple[str, str]],
) -> tuple[Notice, ...]:
    """Contrôle d'un redimensionnement, avant toute écriture.

    Refus (:class:`FurnitureError`) : cote d'une pièce hors bornes ; paire d'assemblage
    ``joined`` (clés hôte, invitée) dont la position relative changerait de classe
    (``Contact``, ``Overlap``, ``Separated``). Avertissements : ``UserFormula`` pour une
    propriété pilotée sur un axe qui change, ``OutsideBox`` pour un membre qui dépasserait.
    """
    after = predict(old, new, members, rules)
    before = {member.key: member for member in members}
    _check_joints(before, after, joined)
    notices: list[Notice] = []
    for member in members:
        if member.key not in after:
            continue
        notices.extend(_user_formulas(member, rules[member.key], old, new))
        if _outside(member_spans(after[member.key]), new):
            notices.append(notice(NoticeKind.OUTSIDE_BOX, member))
    return tuple(notices)


def check_membership(
    furniture: str, candidate: str, parents: Mapping[str, str], labels: Mapping[str, str]
) -> None:
    """Refuse (:class:`FurnitureError`) que l'ensemble ``candidate`` entre dans ``furniture``
    s'il est ``furniture`` lui-même ou l'un de ses ancêtres (``parents`` : ensemble → ensemble
    dont il est membre ; ``labels`` : noms cités dans le message)."""
    ancestors: set[str] = set()
    current: str | None = furniture
    while current is not None and current not in ancestors:
        ancestors.add(current)
        current = parents.get(current)
    if candidate in ancestors:
        names = {"member": labels.get(candidate, candidate)}
        raise FurnitureError(
            FURNITURE_CYCLE, {**names, "furniture": labels.get(furniture, furniture)}
        )
