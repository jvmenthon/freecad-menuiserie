# SPDX-License-Identifier: LGPL-2.1-or-later
"""« Suivre le redimensionnement » (``FollowResize``, ADR 0043, spécification § 3.4).

Décochée, le pas de la répétition est fixe. Cochée, la répétition passe en « nombre sur une
longueur » et sa longueur ``Span`` est une expression sur la cote de l'ensemble des sources le long
de l'axe : ``Span = <ensemble>.<cote> - retraits``, où les retraits au début et à la fin sont ceux
d'**aujourd'hui** (figés en constante au moment de l'écriture). Le pas devient
``Step = (Span - cote des sources) / Count``. Agrandir l'ensemble redistribue donc les copies sur
la nouvelle cote ; leur nombre ne change pas.

En grille (ADR 0045), le suivi s'applique **axe par axe** : chaque ligne (``Span``/``Step``,
``Span2``/``Step2``, ``Span3``/``Step3``) suit la cote de l'ensemble sur son propre axe.

Les sources doivent être membres d'un même ensemble : la cote suivie est la sienne (``Width`` pour
l'axe X, ``Depth`` pour Y, ``Height`` pour Z). Les expressions sont écrites par l'API, dans la
transaction en cours, jamais pendant un recalcul.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import replace
from typing import Final

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.repeat import (
    AxisRepeat,
    RepeatAxis,
    RepeatParams,
    Resolved,
    ResolvedAxis,
    ResolvedGrid,
    SpacingMode,
)
from freecad.menuiserie.core.text import quoted_value
from freecad.menuiserie.features.freecad_types import DocumentObject, has_expression
from freecad.menuiserie.features.furniture import furniture_of
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.features.repeat_props import LINE_COUNT, line_name

__all__ = [
    "bind_follow",
    "bind_follow_grid",
    "follow_furniture",
    "follow_grid_params",
    "follow_params",
    "unbind_follow",
]

_NO_FURNITURE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Répétition : « {label} » n'est membre d'aucun ensemble ; « Suivre le redimensionnement » "
    "demande que les pièces répétées soient dans un ensemble dont elles suivent la cote.",
)
_SEVERAL_FURNITURES: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Répétition : « {first} » (ensemble « {first_furniture} ») et « {second} » (ensemble "
    "« {second_furniture} ») ne sont pas dans le même ensemble ; « Suivre le redimensionnement » "
    "suit la cote d'un seul ensemble.",
)
_SIZE_OF_AXIS: Final = {RepeatAxis.X: "Width", RepeatAxis.Y: "Depth", RepeatAxis.Z: "Height"}
_DECIMALS: Final = 6


def follow_furniture(sources: Sequence[DocumentObject]) -> DocumentObject:
    """Ensemble dont la répétition suit la cote : celui des ``sources``, qui doivent toutes y être
    membres. ``ValueError`` traduite si l'une n'est dans aucun ensemble ou si deux sources sont
    dans des ensembles différents."""
    found: list[tuple[DocumentObject, DocumentObject]] = []
    for source in sources:
        furniture = furniture_of(source)
        if furniture is None:
            raise ValueError(translated(_NO_FURNITURE, {"label": quoted_value(source.Label)}))
        found.append((source, furniture))
    first, furniture = found[0]
    for source, other in found[1:]:
        if other != furniture:
            params = {
                "first": quoted_value(first.Label),
                "first_furniture": quoted_value(furniture.Label),
                "second": quoted_value(source.Label),
                "second_furniture": quoted_value(other.Label),
            }
            raise ValueError(translated(_SEVERAL_FURNITURES, params))
    return furniture


def follow_grid_params(
    params: RepeatParams,
    grid: ResolvedGrid,
    extents: Mapping[RepeatAxis, float],
    *,
    gap: bool = False,
) -> RepeatParams:
    """Réglage écrit dans la répétition qui suit le redimensionnement : « nombre sur une
    longueur », avec, pour chaque axe, la longueur que donnent le nombre et le pas effectifs
    (``extents`` : cote des sources sur chaque axe ; ``gap`` : un intervalle de plus, avant la
    fin)."""
    lines = tuple(
        AxisRepeat(
            line.axis,
            line.cells,
            line.step,
            extents[line.axis] + (line.count + gap) * line.step,
            line.reverse,
        )
        for line in grid.axes
    )
    return replace(params, spacing=SpacingMode.COUNT_ON_SPAN, grid=lines)


def follow_params(params: RepeatParams, resolved: Resolved, extent: float) -> RepeatParams:
    """:func:`follow_grid_params` pour une répétition sur un seul axe : nombre et pas effectifs
    ``resolved``, cote des sources ``extent`` sur l'axe."""
    line = params.lines[0]
    axis = ResolvedAxis(line.axis, resolved.count + 1, resolved.step, line.reverse)
    return follow_grid_params(params, ResolvedGrid((axis,)), {line.axis: extent})


def _mm(value: float) -> str:
    """Longueur écrite pour une expression, ``6`` décimales au plus."""
    text = f"{abs(value):.{_DECIMALS}f}".rstrip("0").rstrip(".")
    return f"{text or '0'} mm"


def unbind_follow(repeat: DocumentObject) -> None:
    """Retire les expressions de ``Span`` et ``Step`` de chaque ligne (le pas redevient fixe, à sa
    valeur)."""
    for line in range(LINE_COUNT):
        for field in ("Span", "Step"):
            name = line_name(field, line)
            if has_expression(repeat, name):
                repeat.setExpression(name, None)


def bind_follow_line(
    repeat: DocumentObject,
    furniture: DocumentObject,
    line: int,
    axis: ResolvedAxis,
    extent: float,
    *,
    gap: bool = False,
) -> None:
    """Écrit ``Span`` et ``Step`` de la ligne ``line`` (``Span2`` et ``Step2`` pour la deuxième…) en
    expressions : retraits actuels figés, nombre de copies en constante (il ne change que par
    l'API, qui réécrit alors ces expressions)."""
    size = _SIZE_OF_AXIS[axis.axis]
    span_name, step_name = line_name("Span", line), line_name("Step", line)
    divisions = axis.count + 1 if gap else axis.count  # ``gap`` : intervalle avant la fin
    span = extent + divisions * axis.step
    margins = float(getattr(furniture, size).Value) - span
    sign = "-" if margins >= 0 else "+"
    repeat.setExpression(span_name, f"{furniture.Name}.{size} {sign} {_mm(margins)}")
    repeat.setExpression(step_name, f"({span_name} - {_mm(extent)}) / {divisions}")


def bind_follow_grid(
    repeat: DocumentObject,
    furniture: DocumentObject,
    grid: ResolvedGrid,
    extents: Mapping[RepeatAxis, float],
    *,
    gap: bool = False,
) -> None:
    """Chaque ligne de la grille suit la cote de ``furniture`` sur son axe
    (:func:`bind_follow_line`)."""
    for line, axis in enumerate(grid.axes):
        bind_follow_line(repeat, furniture, line, axis, extents[axis.axis], gap=gap)


def bind_follow(
    repeat: DocumentObject,
    furniture: DocumentObject,
    axis: RepeatAxis,
    extent: float,
    resolved: Resolved,
) -> None:
    """:func:`bind_follow_grid` pour une répétition sur un seul axe."""
    line = ResolvedAxis(axis, resolved.count + 1, resolved.step)
    bind_follow_line(repeat, furniture, 0, line, extent)
