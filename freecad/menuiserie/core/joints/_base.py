# SPDX-License-Identifier: LGPL-2.1-or-later
"""Socle des assemblages : types, plan d'usinage, protocole, arrondi et règles communes.

Module privé : la façade ``core.joints`` ré-exporte l'API publique.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, fields
from enum import Enum
from types import MappingProxyType
from typing import Any, ClassVar, Final, Protocol, TypeVar, runtime_checkable

from freecad.menuiserie.core._validation import MAX_DIMENSION_MM, bounded_float, decimal_text
from freecad.menuiserie.core.geometry import (
    Contact,
    JointError,
    Overlap,
    PlacedBlock,
    Solid,
    classify,
)
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.text import quoted_value

MAX_COUNT: Final = 50

SEPARATED: Final = QT_TRANSLATE_NOOP("Menuiserie", "Les pièces ne se touchent pas.")
OVERLAPPING: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Les pièces se chevauchent : cet assemblage demande deux pièces en contact."
)
NOT_OVERLAPPING: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Les pièces ne se chevauchent pas : la pièce logée doit occuper la place de la feuillure.",
)

_PARAM_KIND: Final = "joint_param"
_INVALID: Final = object()


class JointKind(str, Enum):
    """Type d'assemblage ; non enregistré dans les documents (le chemin du proxy l'est)."""

    MORTISE_TENON = "MortiseTenon"
    TONGUE_GROOVE = "TongueGroove"
    RABBET = "Rabbet"


@dataclass(frozen=True)
class JointPlan:
    """Plan d'usinage : ajouts et enlèvements dans le repère local de chaque pièce."""

    host_cuts: tuple[Solid, ...] = ()  # repère local de l'hôte
    host_additions: tuple[Solid, ...] = ()
    guest_cuts: tuple[Solid, ...] = ()  # repère local de l'invitée
    guest_additions: tuple[Solid, ...] = ()
    inserts: tuple[Solid, ...] = ()  # pièces rapportées (tourillons), repère de l'hôte


P = TypeVar("P", contravariant=True)
R = TypeVar("R", covariant=True)


@runtime_checkable
class JointStrategy(Protocol[P, R]):
    """Calcul d'un type d'assemblage : valeurs effectives et plan d'usinage."""

    kind: ClassVar[JointKind]

    def resolve(self, host: PlacedBlock, guest: PlacedBlock, params: P) -> R:
        """Valeurs effectives (automatiques résolues) utilisées par le plan."""

    def plan(self, host: PlacedBlock, guest: PlacedBlock, params: P) -> JointPlan:
        """Plan d'usinage ; lève :class:`JointError` si l'assemblage est impossible."""


def mm_round(value: float) -> float:
    """Arrondi au mm « demi vers le haut » (``floor(x + 0,5)``), au moins 1 mm."""
    return float(max(1, math.floor(value + 0.5)))


def mm_text(value: float) -> str:
    """Cote écrite à la française pour un message (« 7,5 »)."""
    return decimal_text(round(value, 6))


def require_contact(host: PlacedBlock, guest: PlacedBlock) -> Contact:
    """Contact des deux pièces, sinon :class:`JointError`."""
    relation = classify(host, guest)
    if isinstance(relation, Contact):
        return relation
    raise JointError(OVERLAPPING if isinstance(relation, Overlap) else SEPARATED, {})


def require_overlap(host: PlacedBlock, guest: PlacedBlock) -> Overlap:
    """Chevauchement des deux pièces, sinon :class:`JointError`."""
    relation = classify(host, guest)
    if isinstance(relation, Overlap):
        return relation
    raise JointError(NOT_OVERLAPPING, {})


# --- Paramètres : objets valeur validés à la construction ---------------------------------


class ParamKind(Enum):
    """Nature d'un paramètre d'assemblage, qui fixe ses bornes."""

    LENGTH = "length"
    OFFSET = "offset"
    FLAG = "flag"
    COUNT = "count"


def _length(value: object) -> object:
    number = bounded_float(value, 0.0, MAX_DIMENSION_MM)
    return _INVALID if number is None else number


def _offset(value: object) -> object:
    number = bounded_float(value, -MAX_DIMENSION_MM, MAX_DIMENSION_MM)
    return _INVALID if number is None else number


def _flag(value: object) -> object:
    return value if isinstance(value, bool) else _INVALID


def _count(value: object) -> object:
    valid = isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= MAX_COUNT
    return value if valid else _INVALID


_CHECKS: Final[Mapping[ParamKind, Callable[[object], object]]] = MappingProxyType(
    {
        ParamKind.LENGTH: _length,
        ParamKind.OFFSET: _offset,
        ParamKind.FLAG: _flag,
        ParamKind.COUNT: _count,
    }
)
_TEMPLATES: Final[Mapping[ParamKind, str]] = MappingProxyType(
    {
        ParamKind.LENGTH: QT_TRANSLATE_NOOP(
            "Menuiserie",
            "Paramètre d'assemblage invalide : {field} = {value} "
            "(longueur finie entre 0 et {max} mm attendue).",
        ),
        ParamKind.OFFSET: QT_TRANSLATE_NOOP(
            "Menuiserie",
            "Paramètre d'assemblage invalide : {field} = {value} "
            "(décalage fini entre -{max} et {max} mm attendu).",
        ),
        ParamKind.FLAG: QT_TRANSLATE_NOOP(
            "Menuiserie",
            "Paramètre d'assemblage invalide : {field} = {value} (vrai ou faux attendu).",
        ),
        ParamKind.COUNT: QT_TRANSLATE_NOOP(
            "Menuiserie",
            "Paramètre d'assemblage invalide : {field} = {value} "
            "(nombre entier entre 0 et {max} attendu).",
        ),
    }
)
_MAXIMA: Final = MappingProxyType(
    {
        ParamKind.LENGTH: MAX_DIMENSION_MM,
        ParamKind.OFFSET: MAX_DIMENSION_MM,
        ParamKind.COUNT: MAX_COUNT,
    }
)


def length_param(default: float) -> Any:
    """Champ « longueur » : fini, non booléen, 0 ≤ x ≤ 20 000 mm (0 = automatique)."""
    return field(default=default, metadata={_PARAM_KIND: ParamKind.LENGTH})


def offset_param(default: float) -> Any:
    """Champ « décalage » : fini, non booléen, |x| ≤ 20 000 mm."""
    return field(default=default, metadata={_PARAM_KIND: ParamKind.OFFSET})


def flag_param(default: bool) -> Any:
    """Champ booléen."""
    return field(default=default, metadata={_PARAM_KIND: ParamKind.FLAG})


def count_param(default: int) -> Any:
    """Champ « nombre » : entier, non booléen, 0 à 50 (0 = automatique)."""
    return field(default=default, metadata={_PARAM_KIND: ParamKind.COUNT})


def validate_params(params: object) -> None:
    """Contrôle et normalise chaque champ d'un objet de paramètres (``ValueError`` sinon)."""
    for item in fields(params):  # type: ignore[arg-type]
        kind: ParamKind = item.metadata[_PARAM_KIND]
        value = getattr(params, item.name)
        checked = _CHECKS[kind](value)
        if checked is _INVALID:
            values = {"field": item.name, "value": quoted_value(value)}
            if kind in _MAXIMA:
                values["max"] = decimal_text(_MAXIMA[kind])
            raise JointError(_TEMPLATES[kind], values)
        object.__setattr__(params, item.name, checked)
