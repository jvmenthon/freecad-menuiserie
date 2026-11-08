# SPDX-License-Identifier: LGPL-2.1-or-later
"""Énumérations, erreurs et paramètres validés de la répétition (ADR 0043)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Final, TypeVar

from freecad.menuiserie.core._validation import decimal_text, to_finite_float
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP, TemplatedError

MAX_COPIES: Final = 100

FIELDS: Final = {
    "mode": QT_TRANSLATE_NOOP("Menuiserie", "mode de répétition"),
    "spacing": QT_TRANSLATE_NOOP("Menuiserie", "mode de saisie"),
    "axis": QT_TRANSLATE_NOOP("Menuiserie", "axe"),
    "count": QT_TRANSLATE_NOOP("Menuiserie", "nombre de copies"),
    "step": QT_TRANSLATE_NOOP("Menuiserie", "pas"),
    "span": QT_TRANSLATE_NOOP("Menuiserie", "longueur"),
    "extent": QT_TRANSLATE_NOOP("Menuiserie", "cote de la pièce répétée"),
}
NOT_AVAILABLE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Répétition : le mode « {value} » n'est pas encore disponible."
)
UNKNOWN_VALUE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Répétition : {field} inconnu : « {value} »."
)
COUNT_RANGE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Répétition : {field} = {value} ; il faut un nombre entier de 1 à {max}."
)
POSITIVE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Répétition : {field} = {value} mm ; il faut un nombre fini supérieur à 0."
)

_E = TypeVar("_E", bound=Enum)


class RepeatError(TemplatedError):
    """Répétition refusée ; message traduisible (``params`` : champ, valeur, bornes)."""


class RepeatMode(str, Enum):
    """Genre de répétition (valeurs stables, écrites dans les documents)."""

    LINEAR = "Linear"
    CIRCULAR = "Circular"  # réservé
    PATH = "Path"  # réservé


class SpacingMode(str, Enum):
    """Manière de saisir la répétition (valeurs stables)."""

    COUNT_AND_STEP = "CountAndStep"
    COUNT_ON_SPAN = "CountOnSpan"
    STEP_ON_SPAN = "StepOnSpan"


class RepeatAxis(str, Enum):
    """Axe global de la répétition linéaire (valeurs stables)."""

    X = "X"
    Y = "Y"
    Z = "Z"


def shown(value: object) -> str:
    """Valeur écrite pour un message : nombre à la française, sinon son texte."""
    number = to_finite_float(value)
    return decimal_text(number) if number is not None else str(value)


def _enum(kind: type[_E], name: str, value: object) -> _E:
    try:
        return kind(value)
    except ValueError:
        raise RepeatError(UNKNOWN_VALUE, {"field": FIELDS[name], "value": shown(value)}) from None


def positive(name: str, value: object) -> float:
    """Nombre fini strictement positif, sinon :class:`RepeatError`."""
    number = to_finite_float(value)
    if number is None or number <= 0.0:
        raise RepeatError(POSITIVE, {"field": FIELDS[name], "value": shown(value)})
    return number


def _check_count(count: object) -> None:
    if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= MAX_COPIES:
        raise RepeatError(
            COUNT_RANGE,
            {"field": FIELDS["count"], "value": shown(count), "max": str(MAX_COPIES)},
        )


@dataclass(frozen=True)
class RepeatParams:
    """Paramètres d'une répétition linéaire (mm), validés à la construction.

    ``count`` : copies en plus de la source (entier de 1 à ``MAX_COPIES``), utilisé par
    ``CountAndStep`` et ``CountOnSpan`` ; ``step`` : pas entre copies, utilisé par
    ``CountAndStep`` et ``StepOnSpan`` ; ``span`` : longueur, utilisée par ``CountOnSpan`` et
    ``StepOnSpan``. Un champ que le mode de saisie n'utilise pas n'est pas contrôlé. Les modes
    ``Circular`` et ``Path`` sont refusés : pas encore disponibles.
    """

    mode: RepeatMode = RepeatMode.LINEAR
    spacing: SpacingMode = SpacingMode.COUNT_AND_STEP
    count: int = 1
    step: float = 100.0
    span: float = 0.0
    axis: RepeatAxis = RepeatAxis.X
    reverse: bool = False
    copy_joints: bool = True
    follow_resize: bool = False

    def __post_init__(self) -> None:
        mode = _enum(RepeatMode, "mode", self.mode)
        if mode is not RepeatMode.LINEAR:
            raise RepeatError(NOT_AVAILABLE, {"value": mode.value})
        spacing = _enum(SpacingMode, "spacing", self.spacing)
        object.__setattr__(self, "mode", mode)
        object.__setattr__(self, "spacing", spacing)
        object.__setattr__(self, "axis", _enum(RepeatAxis, "axis", self.axis))
        if spacing is not SpacingMode.STEP_ON_SPAN:
            _check_count(self.count)
        if spacing is not SpacingMode.COUNT_ON_SPAN:
            positive("step", self.step)
        if spacing is not SpacingMode.COUNT_AND_STEP:
            positive("span", self.span)
