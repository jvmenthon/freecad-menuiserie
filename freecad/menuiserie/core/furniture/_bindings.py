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
from freecad.menuiserie.core.furniture._spans import member_spans
from freecad.menuiserie.core.text import quoted_value

RATIO_DECIMALS: Final = 9
CONSTANT_DECIMALS: Final = 6
_FORBIDDEN_IN_LABEL: Final = (">", "\\")
_PIECE_BOUND: Final = ("Length", "Width", "Placement")  # propriétés que l'atelier lie
_FURNITURE_BOUND: Final = ("Width", "Depth", "Height", "Origin")


def number_text(value: float, decimals: int) -> str:
    """Nombre écrit pour une expression : ``decimals`` décimales au plus, sans zéros inutiles."""
    text = f"{value:.{decimals}f}".rstrip("0").rstrip(".")
    return "0" if text == "-0" else text


def expression_text(
    reference: str, axis: FurnitureAxis, linear: Linear, *, from_origin: bool = False
) -> str:
    """Texte ``[<<Label>>.Origin.x +] <<Label>>.Cote * ratio ± k mm`` de ``linear``
    (``reference`` = ``<<Label>>``) ; ``from_origin`` pour une position, relative à l'``Origin``
    de l'ensemble, qui suit donc un sous-ensemble dont l'``Origin`` bouge."""
    terms = [f"{reference}.Origin.{'xyz'[axis.index]}"] if from_origin else []
    ratio = number_text(linear.coef, RATIO_DECIMALS)
    if ratio != "0":
        terms.append(f"{reference}.{axis.value}" + ("" if ratio == "1" else f" * {ratio}"))
    text = " + ".join(terms)
    constant = number_text(linear.const, CONSTANT_DECIMALS)
    if not text:
        return f"{constant} mm"
    if constant.startswith("-"):
        return f"{text} - {constant[1:]} mm"
    return text if constant == "0" else f"{text} + {constant} mm"


def label_reference(label: str) -> str:
    """``<<label>>`` ; :class:`FurnitureError` pour un libellé vide, qui contient ``>`` (dès
    ``label>`` + ``>>``) ou ``\\`` (échappement de FreeCAD dans ``<<…>>`` : ``Bur\\'eau`` vise
    ``Bur'eau``), l'expression visant alors un autre objet, ou un caractère invisible."""
    valid = isinstance(label, str) and bool(label) and not has_forbidden_character(label)
    if not valid or any(char in label for char in _FORBIDDEN_IN_LABEL):
        raise FurnitureError(INVALID_LABEL, {"label": quoted_value(label)})
    return f"<<{label}>>"


def is_driven(member: Member, prop: str) -> bool:
    """Vrai si ``prop`` (ou une propriété qui la contient, ``Placement``) est pilotée par
    l'utilisateur."""
    return any(prop == name or prop.startswith(name + ".") for name in member.driven)


def driven_properties(current: Mapping[str, str], recorded: Mapping[str, str]) -> frozenset[str]:
    """Propriétés dont l'expression actuelle n'est pas celle que l'atelier a posée
    (``FurnitureBindings``) : formules de l'utilisateur, ou liaisons réécrites (cas sûr).

    Une liaison effacée par l'utilisateur (propriété enregistrée sans expression actuelle)
    n'est pas pilotée : « Relier les pièces » la remet."""
    return frozenset(prop for prop, text in current.items() if recorded.get(prop) != text)


def position_property(member: Member, axis: FurnitureAxis) -> str:
    """Propriété de position liée sur ``axis`` : ``Placement.Base.x`` ou ``Origin.x``…"""
    root = "Placement.Base" if member.block is not None else "Origin"
    return f"{root}.{'xyz'[axis.index]}"


def bound_by_workshop(member: Member, prop: str) -> bool:
    """Vrai si l'atelier lie lui-même ``prop`` : ``Length``, ``Width``, ``Placement`` d'une
    pièce ; ``Width``, ``Depth``, ``Height``, ``Origin`` d'un sous-ensemble (et sous-chemins)."""
    roots = _PIECE_BOUND if member.block is not None else _FURNITURE_BOUND
    return prop.split(".")[0] in roots


def _member_bindings(
    reference: str, box: FurnitureBox, member: Member, rules: tuple[FollowRule, ...], nested: bool
) -> Iterator[Binding]:
    spans = member_spans(member)
    for rule in rules:
        position, size = axis_motion(rule, spans[rule.axis], box.size(rule.axis))
        local = rule.local
        if (
            size is not None
            and local is not None
            and not (size.constant or is_driven(member, local))
        ):
            yield Binding(member.key, local, expression_text(reference, rule.axis, size))
        prop = position_property(member, rule.axis)
        if (nested or not position.constant) and not is_driven(member, prop):
            text = expression_text(reference, rule.axis, position, from_origin=True)
            yield Binding(member.key, prop, text)


def bindings_for(
    label: str,
    box: FurnitureBox,
    members: Sequence[Member],
    rules: Rules,
    *,
    nested: bool = False,
) -> tuple[tuple[Binding, ...], tuple[Notice, ...]]:
    """Liaisons des membres qui ont des règles (``follow_rules``), et avertissements
    ``UserFormula`` pour chaque propriété liée par l'atelier mais pilotée par l'utilisateur,
    qui n'en reçoit aucune.

    Les positions sont écrites relativement à ``<<Label>>.Origin`` ; ``core`` travaille en
    coordonnées relatives à cette ``Origin``. Aucune liaison qui ne changerait rien (face qui ne
    bouge pas, cote constante), sauf ``nested`` : l'ensemble est lui-même membre d'un autre,
    son ``Origin`` peut bouger, toutes les positions de ses membres la suivent.
    """
    reference = label_reference(label)
    bindings: list[Binding] = []
    notices: list[Notice] = []
    for member in members:
        for prop in sorted(member.driven):
            if bound_by_workshop(member, prop):
                notices.append(notice(NoticeKind.USER_FORMULA, member, property=prop))
        if member.key in rules:
            found = _member_bindings(reference, box, member, rules[member.key], nested)
            bindings.extend(found)
    return tuple(bindings), tuple(notices)
