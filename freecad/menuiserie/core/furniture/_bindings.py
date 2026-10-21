# SPDX-License-Identifier: LGPL-2.1-or-later
"""Liaisons : expressions FreeCAD posées sur les membres d'un ensemble (J4a, critères F8, F9).

Module privé : la façade ``core.furniture`` ré-exporte l'API publique. Format :
``<<Label>>.Cote``, puis ``* ratio`` (9 décimales au plus), puis ``+ k mm`` ou ``- k mm``
(6 décimales au plus) ; zéros inutiles retirés, ratio 1 et constante nulle omis.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from typing import Final

from freecad.menuiserie.core._validation import has_forbidden_character
from freecad.menuiserie.core.furniture._follow import Linear, Rules, axis_motion
from freecad.menuiserie.core.furniture._messages import INVALID_LABEL
from freecad.menuiserie.core.furniture._model import (
    Binding,
    FollowRule,
    FurnitureAxis,
    FurnitureBox,
    FurnitureError,
    Member,
    Notice,
    NoticeKind,
    notice,
)
from freecad.menuiserie.core.furniture._spans import Span, member_spans
from freecad.menuiserie.core.geometry import Vec3
from freecad.menuiserie.core.text import quoted_value

RATIO_DECIMALS: Final = 9
CONSTANT_DECIMALS: Final = 6
_ZERO: Final = Vec3(0.0, 0.0, 0.0)


def number_text(value: float, decimals: int) -> str:
    """Nombre écrit pour une expression : ``decimals`` décimales au plus, sans zéros inutiles."""
    text = f"{value:.{decimals}f}".rstrip("0").rstrip(".")
    return "0" if text == "-0" else text


def expression_text(reference: str, axis: FurnitureAxis, linear: Linear) -> str:
    """Texte ``<<Label>>.Cote * ratio ± k mm`` de ``linear`` (``reference`` = ``<<Label>>``)."""
    text = f"{reference}.{axis.value}"
    ratio = number_text(linear.coef, RATIO_DECIMALS)
    if ratio != "1":
        text += f" * {ratio}"
    constant = number_text(linear.const, CONSTANT_DECIMALS)
    if constant.startswith("-"):
        text += f" - {constant[1:]} mm"
    elif constant != "0":
        text += f" + {constant} mm"
    return text


def label_reference(label: str) -> str:
    """``<<label>>`` ; :class:`FurnitureError` pour un libellé vide, qui contient ``>`` (dès
    ``label>`` + ``>>``, l'expression viserait un autre objet) ou un caractère invisible."""
    if not isinstance(label, str) or not label or ">" in label or has_forbidden_character(label):
        raise FurnitureError(INVALID_LABEL, {"label": quoted_value(label)})
    return f"<<{label}>>"


def is_driven(member: Member, prop: str) -> bool:
    """Vrai si ``prop`` (ou une propriété qui la contient, ``Placement``) est pilotée par
    l'utilisateur."""
    return any(prop == name or prop.startswith(name + ".") for name in member.driven)


def driven_properties(current: Mapping[str, str], recorded: Mapping[str, str]) -> frozenset[str]:
    """Propriétés dont l'expression actuelle n'est pas celle que l'atelier a posée
    (``FurnitureBindings``) : formules de l'utilisateur, ou liaisons réécrites (cas sûr)."""
    return frozenset(prop for prop, text in current.items() if recorded.get(prop) != text)


def position_property(member: Member, axis: FurnitureAxis) -> str:
    """Propriété de position liée sur ``axis`` : ``Placement.Base.x`` ou ``Origin.x``…"""
    root = "Placement.Base" if member.block is not None else "Origin"
    return f"{root}.{'xyz'[axis.index]}"


def _motions(
    member: Member, rule: FollowRule, span: Span, size0: float
) -> Iterator[tuple[str, Linear]]:
    position, size = axis_motion(rule, span, size0)
    if size is not None and rule.local is not None:
        yield rule.local, size
    yield position_property(member, rule.axis), position


def _member_bindings(
    reference: str, box: FurnitureBox, member: Member, rules: tuple[FollowRule, ...], origin: Vec3
) -> Iterator[Binding]:
    spans = member_spans(member)
    for rule in rules:
        for prop, linear in _motions(member, rule, spans[rule.axis], box.size(rule.axis)):
            if linear.constant or is_driven(member, prop):
                continue
            offset = 0.0 if prop == rule.local else origin.component(rule.axis.index)
            shifted = Linear(linear.coef, linear.const + offset)
            yield Binding(member.key, prop, expression_text(reference, rule.axis, shifted))


def bindings_for(
    label: str,
    box: FurnitureBox,
    members: Sequence[Member],
    rules: Rules,
    *,
    origin: Vec3 = _ZERO,
) -> tuple[tuple[Binding, ...], tuple[Notice, ...]]:
    """Liaisons des membres qui ont des règles (``follow_rules``), et avertissements
    ``UserFormula`` pour chaque propriété pilotée par l'utilisateur, qui n'en reçoit aucune.

    ``origin`` : ``Origin`` de l'ensemble dans le repère de son conteneur, ajoutée aux
    constantes des positions (coordonnées relatives dans ``core``, absolues dans le document).
    Aucune liaison qui ne changerait rien (face qui ne bouge pas, cote constante).
    """
    reference = label_reference(label)
    bindings: list[Binding] = []
    notices: list[Notice] = []
    for member in members:
        for prop in sorted(member.driven):
            notices.append(notice(NoticeKind.USER_FORMULA, member, property=prop))
        if member.key in rules:
            found = _member_bindings(reference, box, member, rules[member.key], origin)
            bindings.extend(found)
    return tuple(bindings), tuple(notices)
