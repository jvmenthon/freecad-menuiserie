# SPDX-License-Identifier: LGPL-2.1-or-later
"""« Suivre le redimensionnement » (``FollowResize``, ADR 0043, spécification § 3.4).

Décochée, le pas de la répétition est fixe. Cochée, la répétition passe en « nombre sur une
longueur » et sa longueur ``Span`` est une expression sur la cote de l'ensemble des sources le long
de l'axe : ``Span = <ensemble>.<cote> - retraits``, où les retraits au début et à la fin sont ceux
d'**aujourd'hui** (figés en constante au moment de l'écriture). Le pas devient
``Step = (Span - cote des sources) / Count``. Agrandir l'ensemble redistribue donc les copies sur
la nouvelle cote ; leur nombre ne change pas.

Les sources doivent être membres d'un même ensemble : la cote suivie est la sienne (``Width`` pour
l'axe X, ``Depth`` pour Y, ``Height`` pour Z). Les expressions sont écrites par l'API, dans la
transaction en cours, jamais pendant un recalcul.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from typing import Final

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.repeat import RepeatAxis, RepeatParams, Resolved, SpacingMode
from freecad.menuiserie.core.text import quoted_value
from freecad.menuiserie.features.freecad_types import DocumentObject, has_expression
from freecad.menuiserie.features.furniture import furniture_of
from freecad.menuiserie.features.i18n import translated

__all__ = ["bind_follow", "follow_furniture", "follow_params", "unbind_follow"]

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


def follow_params(params: RepeatParams, resolved: Resolved, extent: float) -> RepeatParams:
    """Réglage écrit dans la répétition qui suit le redimensionnement : « nombre sur une
    longueur », avec la longueur que donnent le nombre et le pas effectifs (``extent`` : cote des
    sources sur l'axe)."""
    span = extent + resolved.count * resolved.step
    return replace(
        params,
        spacing=SpacingMode.COUNT_ON_SPAN,
        count=resolved.count,
        step=resolved.step,
        span=span,
    )


def _mm(value: float) -> str:
    """Longueur écrite pour une expression, ``6`` décimales au plus."""
    text = f"{abs(value):.{_DECIMALS}f}".rstrip("0").rstrip(".")
    return f"{text or '0'} mm"


def unbind_follow(repeat: DocumentObject) -> None:
    """Retire les expressions de ``Span`` et ``Step`` (le pas redevient fixe, à sa valeur)."""
    for name in ("Span", "Step"):
        if has_expression(repeat, name):
            repeat.setExpression(name, None)


def bind_follow(
    repeat: DocumentObject,
    furniture: DocumentObject,
    axis: RepeatAxis,
    extent: float,
    resolved: Resolved,
) -> None:
    """Écrit ``Span`` et ``Step`` en expressions : retraits actuels figés, nombre ``Count`` en
    constante (il ne change que par l'API, qui réécrit alors ces expressions)."""
    size = _SIZE_OF_AXIS[axis]
    span = extent + resolved.count * resolved.step
    margins = float(getattr(furniture, size).Value) - span
    sign = "-" if margins >= 0 else "+"
    repeat.setExpression("Span", f"{furniture.Name}.{size} {sign} {_mm(margins)}")
    repeat.setExpression("Step", f"(Span - {_mm(extent)}) / {resolved.count}")
