# SPDX-License-Identifier: LGPL-2.1-or-later
"""Familles de profils d'arête : une stratégie par famille, dans un registre figé (ADR 0029).

Module privé. Ajouter une famille = une classe et une ligne dans :data:`FAMILIES` ; rien d'autre
ne change (spécification A6). Les valeurs de :class:`EdgeFamily` sont celles de la propriété
FreeCAD ``Family`` : en ajouter à la fin seulement.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import Enum
from types import MappingProxyType
from typing import Final, Protocol

import freecad.menuiserie.core.edges._sections as sections
from freecad.menuiserie.core._extrusion import Section

__all__ = [
    "BROKEN_EDGE_MM",
    "FAMILIES",
    "EdgeFamily",
    "FamilyStrategy",
    "SecondSize",
    "family_for",
]

BROKEN_EDGE_MM: Final = 1.0  # « arête cassée » : quart de rond préréglé (rayon 1 mm)


class EdgeFamily(str, Enum):
    """Famille de profil ; ``HALF_ROUND`` s'appelle « demi-rond » (``Bullnose``)."""

    CHAMFER = "Chamfer"  # chanfrein
    ROUND = "Round"  # quart de rond, et arête cassée
    COVE = "Cove"  # gorge
    BULLNOSE = "Bullnose"  # demi-rond : quart de rond sur les deux arêtes d'un chant
    BEAK = "Beak"  # bec-de-corbin
    OGEE = "Ogee"  # doucine


class SecondSize(Enum):
    """Rôle de la seconde cote ``B``."""

    SAME_IF_ZERO = "same_if_zero"  # 0 : égale à A
    IGNORED = "ignored"  # sans effet : égale à A
    REQUIRED = "required"  # cote propre, au moins la cote minimale


class FamilyStrategy(Protocol):
    """Calcul d'un profil : section enlevée et encombrement, cotes déjà résolues."""

    family: EdgeFamily
    second: SecondSize
    any_angle: bool  # calculée à tout angle de faces (ADR 0063) ; sinon à angle droit seulement

    def section(self, a: float, b: float) -> Section:
        """Section enlevée pour les cotes ``a`` et ``b``."""
        ...

    def extent(self, a: float, b: float) -> tuple[float, float]:
        """Encombrement ``(le long de la première face, le long de la seconde)`` en mm."""
        ...

    def angled_section(self, a: float, b: float, angle: float) -> Section:
        """Section enlevée sur une arête dont les faces forment ``angle`` radians
        (``ValueError`` si la famille exige un angle droit)."""
        ...

    def angled_extent(self, a: float, b: float, angle: float) -> tuple[float, float]:
        """Encombrement de :meth:`angled_section`."""
        ...


class _RightAngleOnly:
    """Mélange des familles calculées à angle droit seulement (placé avant la classe mère)."""

    any_angle = False

    def angled_section(self, a: float, b: float, angle: float) -> Section:
        raise ValueError(f"famille à angle droit seulement : {a}, {b}, {angle}")

    def angled_extent(self, a: float, b: float, angle: float) -> tuple[float, float]:
        raise ValueError(f"famille à angle droit seulement : {a}, {b}, {angle}")


class _Chamfer:
    family = EdgeFamily.CHAMFER
    second = SecondSize.SAME_IF_ZERO
    any_angle = True

    def section(self, a: float, b: float) -> Section:
        return sections.chamfer(a, b)

    def extent(self, a: float, b: float) -> tuple[float, float]:
        return (a, b)

    def angled_section(self, a: float, b: float, angle: float) -> Section:
        return sections.angled_chamfer(a, b, angle)

    def angled_extent(self, a: float, b: float, angle: float) -> tuple[float, float]:
        return (a, b)


class _Round(_Chamfer):
    family = EdgeFamily.ROUND

    def section(self, a: float, b: float) -> Section:
        return sections.round_corner(a, b)

    def angled_section(self, a: float, b: float, angle: float) -> Section:
        return sections.angled_round(a, angle)  # arc tangent : un seul rayon, B sans effet

    def angled_extent(self, a: float, b: float, angle: float) -> tuple[float, float]:
        tangent = sections.tangent_length(a, angle)
        return (tangent, tangent)


class _Cove(_Chamfer):
    family = EdgeFamily.COVE
    second = SecondSize.IGNORED

    def section(self, a: float, b: float) -> Section:
        return sections.cove(a)

    def angled_section(self, a: float, b: float, angle: float) -> Section:
        return sections.angled_cove(a, angle)

    def angled_extent(self, a: float, b: float, angle: float) -> tuple[float, float]:
        return (a, a)


class _Bullnose(_RightAngleOnly, _Cove):
    family = EdgeFamily.BULLNOSE

    def section(self, a: float, b: float) -> Section:
        return sections.round_corner(a, a)


class _Beak(_RightAngleOnly, _Chamfer):
    family = EdgeFamily.BEAK
    second = SecondSize.REQUIRED

    def section(self, a: float, b: float) -> Section:
        return sections.beak(a, b)

    def extent(self, a: float, b: float) -> tuple[float, float]:
        return (a, a + b)


class _Ogee(_RightAngleOnly, _Chamfer):
    family = EdgeFamily.OGEE
    second = SecondSize.REQUIRED

    def section(self, a: float, b: float) -> Section:
        return sections.ogee(a, b)


FAMILIES: Final[Mapping[EdgeFamily, FamilyStrategy]] = MappingProxyType(
    {
        strategy.family: strategy
        for strategy in (_Chamfer(), _Round(), _Cove(), _Bullnose(), _Beak(), _Ogee())
    }
)


def family_for(family: EdgeFamily | str) -> FamilyStrategy:
    """Stratégie d'une famille, désignée par l'énumération ou sa valeur (``ValueError`` sinon)."""
    return FAMILIES[EdgeFamily(family)]
