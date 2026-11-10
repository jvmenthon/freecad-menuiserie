# SPDX-License-Identifier: LGPL-2.1-or-later
"""Énumérations, erreurs et paramètres validés de la répétition (ADR 0043)."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, replace
from enum import Enum
from typing import Final, TypeVar

from freecad.menuiserie.core._validation import decimal_text, to_finite_float
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP, TemplatedError

MAX_COPIES: Final = 100
Cell = tuple[int, int, int]  # (i, j, k) : rang de la copie sur X, Y et Z ; (0, 0, 0) : l'original

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
GRID_COUNT_RANGE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Répétition : {field} = {value} ; il faut un nombre entier de 1 (axe inactif) à {max} "
    "(original compris).",
)
AXIS_TWICE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Répétition : l'axe {axis} est donné deux fois ; une seule ligne par axe."
)
NO_AXIS: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Répétition : aucun axe n'est actif ; donnez un nombre supérieur à 1 sur au moins un axe.",
)
GRID_TOO_MANY: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Répétition : {counts} donneraient {count} copies en plus de l'original ; "
    "le maximum est {max}.",
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


def positive(name: str, value: object, axis: RepeatAxis | None = None) -> float:
    """Nombre fini strictement positif, sinon :class:`RepeatError` (``axis`` : ligne de grille)."""
    number = to_finite_float(value)
    if number is None or number <= 0.0:
        raise RepeatError(POSITIVE, {"field": field_name(name, axis), "value": shown(value)})
    return number


def _check_count(count: object) -> None:
    if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= MAX_COPIES:
        raise RepeatError(
            COUNT_RANGE,
            {"field": FIELDS["count"], "value": shown(count), "max": str(MAX_COPIES)},
        )


def field_name(name: str, axis: RepeatAxis | None) -> str:
    """Nom du champ pour un message, avec l'axe d'une ligne de grille."""
    return FIELDS[name] if axis is None else f"{FIELDS[name]} (axe {axis.value})"


def _check_cells(line: AxisRepeat) -> None:
    """Nombre d'éléments d'une ligne de grille : entier de 1 (inactif) à ``MAX_COPIES + 1``."""
    count = line.count
    if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= MAX_COPIES + 1:
        raise RepeatError(
            GRID_COUNT_RANGE,
            {
                "field": f"nombre sur l'axe {line.axis.value}",
                "value": shown(count),
                "max": str(MAX_COPIES + 1),
            },
        )


def counts_text(counts: Iterable[int]) -> str:
    """Nombres d'éléments par axe, ``4 x 3`` par exemple."""
    return " x ".join(str(count) for count in counts)


def checked_grid(grid: tuple[AxisRepeat, ...], spacing: SpacingMode) -> tuple[AxisRepeat, ...]:
    """Lignes actives de ``grid``, triées X, Y, Z et validées pour le mode de saisie ; une ligne de
    nombre 1 (modes avec nombre) est inactive et écartée. :class:`RepeatError` si un axe est
    répété, si aucun n'est actif, si un champ utilisé est hors bornes ou si le total dépasse
    ``MAX_COPIES``."""
    lines: list[AxisRepeat] = []
    for item in grid:
        line = replace(item, axis=_enum(RepeatAxis, "axis", item.axis))
        if line.axis in {other.axis for other in lines}:
            raise RepeatError(AXIS_TWICE, {"axis": line.axis.value})
        if spacing is not SpacingMode.STEP_ON_SPAN:
            _check_cells(line)
        lines.append(line)
    order = list(RepeatAxis)
    active = sorted(
        (ln for ln in lines if spacing is SpacingMode.STEP_ON_SPAN or ln.count > 1),
        key=lambda ln: order.index(ln.axis),
    )
    if not active:
        raise RepeatError(NO_AXIS, {})
    for line in active:
        if spacing is not SpacingMode.COUNT_ON_SPAN:
            positive("step", line.step, line.axis)
        if spacing is not SpacingMode.COUNT_AND_STEP:
            positive("span", line.span, line.axis)
    if spacing is not SpacingMode.STEP_ON_SPAN:
        _check_total(tuple(active))
    return tuple(active)


def _check_total(lines: tuple[AxisRepeat, ...]) -> None:
    total = 1
    for line in lines:
        total *= line.count
    if total - 1 > MAX_COPIES:
        counts = counts_text(line.count for line in lines)
        raise RepeatError(
            GRID_TOO_MANY, {"counts": counts, "count": str(total - 1), "max": str(MAX_COPIES)}
        )


@dataclass(frozen=True)
class AxisRepeat:
    """Ligne d'une répétition en grille : réglage d'un axe (mm).

    ``count`` : nombre d'éléments sur l'axe, **original compris** (1 : axe inactif) ; ``step`` :
    pas ; ``span`` : longueur, source comprise ; ``reverse`` : sens négatif de l'axe. Les champs
    que le mode de saisie commun n'utilise pas sont ignorés. Les valeurs sont contrôlées par
    :class:`RepeatParams`.
    """

    axis: RepeatAxis
    count: int = 2
    step: float = 100.0
    span: float = 0.0
    reverse: bool = False


@dataclass(frozen=True)
class RepeatParams:
    """Paramètres d'une répétition linéaire ou en grille (mm), validés à la construction.

    **Grille** (``grid``, ADR 0045) : une ligne :class:`AxisRepeat` par axe actif ; le mode de
    saisie ``spacing`` est commun, chaque axe a ses valeurs et son sens. Le total des copies est
    le produit des nombres moins un, au plus ``MAX_COPIES``. Les champs ``axis``, ``count``,
    ``step``, ``span`` et ``reverse`` reflètent alors la première ligne (``count`` en copies).

    **Un seul axe** (``grid`` vide) : cas particulier historique, une seule ligne.

    ``count`` : copies en plus de la source (entier de 1 à ``MAX_COPIES``), utilisé par
    ``CountAndStep`` et ``CountOnSpan`` ; ``step`` : pas entre copies, utilisé par
    ``CountAndStep`` et ``StepOnSpan`` ; ``span`` : longueur, utilisée par ``CountOnSpan`` et
    ``StepOnSpan``. Un champ que le mode de saisie n'utilise pas n'est pas contrôlé. Les modes
    ``Circular`` et ``Path`` sont refusés : pas encore disponibles.

    ``deduct_thickness`` (modes « sur une longueur », saisie ou butée) : vrai (défaut, comportement
    historique), la cote des sources sur l'axe est déduite de la longueur et la dernière copie
    s'arrête **à fleur** de la fin de la longueur ; faux, elle ne l'est pas et la dernière copie
    **commence** à la fin de la longueur.

    ``end_gap`` (modes « sur une longueur », demande de jv) : faux (défaut), ``n`` éléments
    partagent la longueur en ``n - 1`` intervalles ; vrai, en ``n`` intervalles égaux : la
    dernière pièce ne touche pas la fin, l'écart est celui des autres (``deduct_thickness`` ne
    sert plus).
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
    deduct_thickness: bool = True
    end_gap: bool = False
    grid: tuple[AxisRepeat, ...] = ()

    def __post_init__(self) -> None:
        mode = _enum(RepeatMode, "mode", self.mode)
        if mode is not RepeatMode.LINEAR:
            raise RepeatError(NOT_AVAILABLE, {"value": mode.value})
        spacing = _enum(SpacingMode, "spacing", self.spacing)
        object.__setattr__(self, "mode", mode)
        object.__setattr__(self, "spacing", spacing)
        if self.grid:
            self._set_grid(checked_grid(tuple(self.grid), spacing))
            return
        object.__setattr__(self, "axis", _enum(RepeatAxis, "axis", self.axis))
        if spacing is not SpacingMode.STEP_ON_SPAN:
            _check_count(self.count)
        if spacing is not SpacingMode.COUNT_ON_SPAN:
            positive("step", self.step)
        if spacing is not SpacingMode.COUNT_AND_STEP:
            positive("span", self.span)

    def _set_grid(self, lines: tuple[AxisRepeat, ...]) -> None:
        first = lines[0]
        for name, value in (
            ("grid", lines),
            ("axis", first.axis),
            ("count", first.count - 1),
            ("step", first.step),
            ("span", first.span),
            ("reverse", first.reverse),
        ):
            object.__setattr__(self, name, value)

    @property
    def lines(self) -> tuple[AxisRepeat, ...]:
        """Lignes actives (une par axe, X, Y, Z) : la grille, ou la ligne unique des champs
        historiques (``count`` copies, soit ``count + 1`` éléments)."""
        if self.grid:
            return self.grid
        return (AxisRepeat(self.axis, self.count + 1, self.step, self.span, self.reverse),)
