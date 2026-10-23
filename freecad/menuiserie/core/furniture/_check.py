"""Aperçu d'un redimensionnement, refus et cycle d'ensembles (J4a, critères F10, F11 ; ADR 0019).

Module privé : la façade ``core.furniture`` ré-exporte l'API publique.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import replace

from freecad.menuiserie.core._validation import MAX_DIMENSION_MM, MIN_DIMENSION_MM
from freecad.menuiserie.core.contact import classify
from freecad.menuiserie.core.furniture._bindings import is_driven, position_property
from freecad.menuiserie.core.furniture._blocked import check_blocked, size_text
from freecad.menuiserie.core.furniture._follow import FollowRule, Rules, follow_rules
from freecad.menuiserie.core.furniture._messages import (
    FURNITURE_CYCLE,
    JOINT_LOST,
    TOO_LARGE,
    TOO_SMALL,
)
from freecad.menuiserie.core.furniture._model import (
    PIECE_AXES,
    THICKNESS,
    FurnitureAxis,
    FurnitureBox,
    FurnitureError,
    Member,
    NoticeKind,
    notice,
)
from freecad.menuiserie.core.furniture._spans import (
    Span,
    Spans,
    frame_block,
    member_spans,
    square_spans,
)
from freecad.menuiserie.core.geometry import CONTACT_TOLERANCE_MM, PlacedBlock, RigidTransform, Vec3
from freecad.menuiserie.core.notice import Notice
from freecad.menuiserie.core.part_model import Dimensions


def _checked_size(member: Member, prop: str, value: float) -> float:
    if MIN_DIMENSION_MM <= value <= MAX_DIMENSION_MM:
        return value
    template = TOO_SMALL if value < MIN_DIMENSION_MM else TOO_LARGE
    params = {"member": member.name, "property": prop, "value": size_text(value)}
    raise FurnitureError(template, params)


def _thicknesses(members: Sequence[Member]) -> dict[str, float]:
    """Épaisseur actuelle de chaque pièce d'équerre (clé → mm)."""
    found: dict[str, float] = {}
    for member in members:
        for span in (square_spans(member) or {}).values():
            if not span.stretchable:
                found[member.key] = span.size
    return found


def _new_axis(
    member: Member, rule: FollowRule, span: Span, target: float, values: Mapping[str, float]
) -> tuple[float, float]:
    """Nouvelle origine locale et nouvelle étendue du membre sur l'axe de ``rule``, pour la
    cote ``target`` de l'ensemble et les épaisseurs ``values``."""
    moved = not is_driven(member, position_property(member, rule.axis))
    origin = rule.position.at(target, values) if moved else span.origin
    if rule.size is None:
        return origin, values[member.key]
    if rule.local is None or is_driven(member, rule.local):
        return origin, span.size
    return origin, _checked_size(member, rule.local, rule.size.at(target, values))


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
    new: FurnitureBox,
    members: Sequence[Member],
    rules: Rules,
    thicknesses: Mapping[str, float] | None = None,
) -> Mapping[str, Member]:
    """Membres tels que les placeraient les liaisons pour les cotes ``new`` de l'ensemble
    (``rules`` : règles calculées pour ses cotes actuelles) et les nouvelles épaisseurs
    ``thicknesses`` (clé de pièce → mm ; les autres gardent la leur).

    Seuls les membres qui ont des règles figurent dans le résultat ; une propriété pilotée par
    l'utilisateur garde sa valeur. :class:`FurnitureError` si une cote sortirait des bornes.
    """
    values = {**_thicknesses(members), **(thicknesses or {})}
    result: dict[str, Member] = {}
    for member in members:
        if member.key not in rules:
            continue
        spans = member_spans(member)
        axes = {
            rule.axis: _new_axis(member, rule, spans[rule.axis], new.size(rule.axis), values)
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


def _axis_changed(
    rule: FollowRule, old: FurnitureBox, new: FurnitureBox, changed: Mapping[str, float]
) -> bool:
    """Vrai si la cote de l'ensemble sur l'axe de ``rule`` ou une épaisseur citée change."""
    cited = rule.position.keys | (rule.size.keys if rule.size is not None else frozenset())
    return old.size(rule.axis) != new.size(rule.axis) or bool(cited & changed.keys())


def _user_formulas(
    member: Member,
    rules: tuple[FollowRule, ...],
    old: FurnitureBox,
    new: FurnitureBox,
    changed: Mapping[str, float],
) -> Iterator[Notice]:
    for rule in rules:
        if not _axis_changed(rule, old, new, changed):
            continue
        props = [rule.local] if rule.local is not None else []
        for prop in [*props, position_property(member, rule.axis)]:
            if is_driven(member, prop):
                yield notice(NoticeKind.USER_FORMULA, member, property=prop)


def _check(
    old: FurnitureBox,
    new: FurnitureBox,
    members: Sequence[Member],
    rules: Rules,
    joined: Sequence[tuple[str, str]],
    changed: Mapping[str, float],
) -> tuple[Notice, ...]:
    check_blocked(old, new, members, rules, changed)
    after = predict(new, members, rules, changed)
    before = {member.key: member for member in members}
    _check_joints(before, after, joined)
    notices: list[Notice] = []
    for member in members:
        if member.key not in after:
            continue
        notices.extend(_user_formulas(member, rules[member.key], old, new, changed))
        if _outside(member_spans(after[member.key]), new):
            notices.append(notice(NoticeKind.OUTSIDE_BOX, member))
    return tuple(notices)


def check_resize(
    old: FurnitureBox,
    new: FurnitureBox,
    members: Sequence[Member],
    rules: Rules,
    joined: Sequence[tuple[str, str]],
) -> tuple[Notice, ...]:
    """Contrôle d'un redimensionnement, avant toute écriture (``rules`` : règles calculées
    pour ``old``).

    Refus (:class:`FurnitureError`) : rangée bloquée sur un axe qui change
    (:class:`BlockedRowError`, qui nomme les pièces verrouillées) ; cote d'une pièce hors
    bornes ; paire d'assemblage ``joined`` (clés hôte, invitée) dont la position relative
    changerait de classe (``Contact``, ``Overlap``, ``Separated``). Avertissements :
    ``UserFormula`` pour une propriété pilotée sur un axe qui change, ``OutsideBox`` pour un
    membre qui dépasserait.
    """
    return _check(old, new, members, rules, joined, {})


def check_thickness(
    box: FurnitureBox,
    members: Sequence[Member],
    key: str,
    thickness: float,
    joined: Sequence[tuple[str, str]],
) -> tuple[Notice, ...]:
    """Contrôle d'une épaisseur nouvelle de la pièce ``key`` (``members`` à leur géométrie
    actuelle, options renseignées), avant toute écriture : mêmes refus et avertissements que
    :func:`check_resize`. Sans effet pour une pièce qui n'est pas d'équerre ; ``ValueError``
    si ``key`` n'est pas un membre."""
    current = _thicknesses(members)
    target = next((member for member in members if member.key == key), None)
    if target is None:
        raise ValueError(f"membre inconnu : « {key} »")
    if key not in current:
        return ()
    _checked_size(target, THICKNESS, thickness)
    rules, _ = follow_rules(box, members)
    changed = {key: thickness} if abs(thickness - current[key]) > CONTACT_TOLERANCE_MM else {}
    return _check(box, box, members, rules, joined, changed)


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
