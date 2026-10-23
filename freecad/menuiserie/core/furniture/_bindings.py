# SPDX-License-Identifier: LGPL-2.1-or-later
"""Liaisons : expressions FreeCAD posées sur les membres d'un ensemble (J4a, critères F8, F9).

Module privé : la façade ``core.furniture`` ré-exporte l'API publique. Format :
``<<Label>>.Cote``, puis ``* ratio`` (9 décimales au plus), puis un terme
``<<Pièce>>.Thickness [* coefficient]`` par épaisseur citée (triées par clé), puis ``k mm``
(6 décimales au plus), chacun précédé de ``+`` ou ``-`` ; zéros inutiles retirés, ratio 1,
coefficient 1 et constante nulle omis.
"""

from __future__ import annotations

import re
from collections.abc import Collection, Iterator, Mapping, Sequence
from typing import Final

from freecad.menuiserie.core._validation import has_forbidden_character
from freecad.menuiserie.core.furniture._follow import FollowRule, Rules
from freecad.menuiserie.core.furniture._linear import Linear
from freecad.menuiserie.core.furniture._messages import INVALID_LABEL
from freecad.menuiserie.core.furniture._model import (
    Binding,
    FurnitureAxis,
    FurnitureError,
    Member,
    NoticeKind,
    notice,
)
from freecad.menuiserie.core.notice import Notice
from freecad.menuiserie.core.text import quoted_value

RATIO_DECIMALS: Final = 9
CONSTANT_DECIMALS: Final = 6
_FORBIDDEN_IN_LABEL: Final = (">", "\\")
_PIECE_BOUND: Final = ("Length", "Width", "Placement")  # propriétés que l'atelier lie
_FURNITURE_BOUND: Final = ("Width", "Depth", "Height", "Origin")
# Référence ``<<…>>`` telle que FreeCAD l'écrit (``\'`` et ``\"`` échappés dans le libellé).
_REFERENCE: Final = re.compile(r"<<(?:[^>\\]|\\.)*>>")


def number_text(value: float, decimals: int) -> str:
    """Nombre écrit pour une expression : ``decimals`` décimales au plus, sans zéros inutiles."""
    text = f"{value:.{decimals}f}".rstrip("0").rstrip(".")
    return "0" if text == "-0" else text


def _signed(text: str) -> tuple[bool, str]:
    return text.startswith("-"), text.lstrip("-")


def _terms(
    reference: str,
    axis: FurnitureAxis,
    linear: Linear,
    pieces: Mapping[str, str],
    from_origin: bool,
) -> list[tuple[bool, str]]:
    """Termes (négatif, texte) de l'expression : origine, cote, épaisseurs, constante."""
    terms = [(False, f"{reference}.Origin.{'xyz'[axis.index]}")] if from_origin else []
    pending = [(f"{reference}.{axis.value}", linear.coef)]
    pending += [(f"{pieces.get(key, key)}.Thickness", coef) for key, coef in linear.thickness]
    for name, coef in pending:
        negative, ratio = _signed(number_text(coef, RATIO_DECIMALS))
        if ratio != "0":
            terms.append((negative, name if ratio == "1" else f"{name} * {ratio}"))
    negative, constant = _signed(number_text(linear.const, CONSTANT_DECIMALS))
    if constant != "0":
        terms.append((negative, f"{constant} mm"))
    return terms


def expression_text(
    reference: str,
    axis: FurnitureAxis,
    linear: Linear,
    pieces: Mapping[str, str] | None = None,
    *,
    from_origin: bool = False,
) -> str:
    """Texte ``[<<Label>>.Origin.x +] <<Label>>.Cote * ratio ± <<Pièce>>.Thickness ± k mm`` de
    ``linear`` (``reference`` = ``<<Label>>`` ; ``pieces`` : clé de pièce → référence citée dans
    l'expression, ``<<Libellé>>`` ou ``Name``, la clé elle-même si elle manque) ; ``from_origin``
    pour une position, relative à l'``Origin`` de l'ensemble, qui suit donc un sous-ensemble
    dont l'``Origin`` bouge."""
    terms = _terms(reference, axis, linear, pieces or {}, from_origin)
    if not terms:
        return "0 mm"
    negative, first = terms[0]
    parts = [f"-{first}" if negative else first]
    parts += [f"{'-' if negative else '+'} {term}" for negative, term in terms[1:]]
    return " ".join(parts)


def piece_reference(member: Member) -> str:
    """Référence à une pièce dans une expression : ``<<Libellé>>``, ou son ``Name`` (la clé)
    si le libellé est inutilisable (:func:`label_reference`)."""
    try:
        return label_reference(member.label)
    except FurnitureError:
        return member.key


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


def same_binding(current: str, recorded: str | None) -> bool:
    """Vrai si l'expression ``current`` est la liaison enregistrée ``recorded``, au libellé
    visé près : FreeCAD réécrit ``<<Bureau>>`` au renommage de l'ensemble, et une copie du
    document garde le libellé de l'original (« Relier les pièces » vise alors la copie)."""
    if recorded is None:
        return False
    return _REFERENCE.sub("<<>>", current) == _REFERENCE.sub("<<>>", recorded)


def driven_properties(current: Mapping[str, str], recorded: Mapping[str, str]) -> frozenset[str]:
    """Propriétés dont l'expression actuelle n'est pas celle que l'atelier a posée
    (``FurnitureBindings``, au libellé visé près : :func:`same_binding`) : formules de
    l'utilisateur, ou liaisons réécrites autrement (cas sûr).

    Une liaison effacée par l'utilisateur (propriété enregistrée sans expression actuelle)
    n'est pas pilotée : « Relier les pièces » la remet."""
    return frozenset(
        prop for prop, text in current.items() if not same_binding(text, recorded.get(prop))
    )


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
    reference: str,
    member: Member,
    rules: tuple[FollowRule, ...],
    pieces: Mapping[str, str],
    nested: bool,
) -> Iterator[Binding]:
    for rule in rules:
        size, local = rule.size, rule.local
        free = not (member.locked or (local is not None and is_driven(member, local)))
        if size is not None and local is not None and free and not size.constant:
            text = expression_text(reference, rule.axis, size, pieces)
            yield Binding(member.key, local, text)
        prop = position_property(member, rule.axis)
        if (nested or not rule.position.constant) and not is_driven(member, prop):
            text = expression_text(reference, rule.axis, rule.position, pieces, from_origin=True)
            yield Binding(member.key, prop, text)


def bindings_for(
    label: str,
    members: Sequence[Member],
    rules: Rules,
    *,
    keys: Collection[str] | None = None,
    nested: bool = False,
) -> tuple[tuple[Binding, ...], tuple[Notice, ...]]:
    """Liaisons des membres ``keys`` (tous par défaut) qui ont des règles (``follow_rules``), et
    avertissements ``UserFormula`` pour chaque propriété liée par l'atelier mais pilotée par
    l'utilisateur, qui n'en reçoit aucune. ``members`` : tous les membres, dont les pièces
    voisines dont une expression cite l'épaisseur.

    Les positions sont écrites relativement à ``<<Label>>.Origin`` ; ``core`` travaille en
    coordonnées relatives à cette ``Origin``. Aucune liaison qui ne dépendrait ni de la cote ni
    d'une épaisseur, sauf ``nested`` : l'ensemble est lui-même membre d'un autre, son ``Origin``
    peut bouger, toutes les positions de ses membres la suivent. Une pièce verrouillée ne reçoit
    aucune liaison de cote.
    """
    reference = label_reference(label)
    pieces = {member.key: piece_reference(member) for member in members}
    bindings: list[Binding] = []
    notices: list[Notice] = []
    for member in members:
        if keys is not None and member.key not in keys:
            continue
        for prop in sorted(member.driven):
            if bound_by_workshop(member, prop):
                notices.append(notice(NoticeKind.USER_FORMULA, member, property=prop))
        if member.key in rules:
            bindings.extend(_member_bindings(reference, member, rules[member.key], pieces, nested))
    return tuple(bindings), tuple(notices)
