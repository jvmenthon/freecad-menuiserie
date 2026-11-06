# SPDX-License-Identifier: LGPL-2.1-or-later
"""Familles de quincaillerie : cotes fonctionnelles attendues par famille générique (ADR 0033).

Une famille décrit seulement les noms et les bornes des cotes (mm) d'une référence du catalogue ;
le modèle 3D générique et les logements à usiner en sont déduits plus tard. Une famille inconnue
(catalogue plus récent) est acceptée telle quelle : la référence reste dans la liste de débit.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP

__all__ = ["FAMILIES", "Family", "ParamSpec", "family_of"]

MAX_PARAM_MM: Final = 2_000.0
MIN_PARAM_MM: Final = 0.1


@dataclass(frozen=True)
class ParamSpec:
    """Cote d'une famille : nom, borne basse et haute en mm."""

    name: str
    minimum: float = MIN_PARAM_MM
    maximum: float = MAX_PARAM_MM


@dataclass(frozen=True)
class Family:
    """Famille générique : identifiant stable, libellé (traduisible) et cotes obligatoires."""

    key: str
    label: str
    params: tuple[ParamSpec, ...]

    @property
    def names(self) -> frozenset[str]:
        """Noms des cotes de la famille."""
        return frozenset(spec.name for spec in self.params)


_FAMILY_LIST: Final = (
    Family(
        "dowel",
        QT_TRANSLATE_NOOP("Menuiserie", "Tourillon"),
        (ParamSpec("diameter", 2.0, 30.0), ParamSpec("length", 10.0, 200.0)),
    ),
    Family(
        "loose-tenon",
        QT_TRANSLATE_NOOP("Menuiserie", "Faux tenon"),
        (
            ParamSpec("thickness", 2.0, 30.0),
            ParamSpec("width", 10.0, 100.0),
            ParamSpec("length", 20.0, 300.0),
        ),
    ),
    Family(
        "biscuit",
        QT_TRANSLATE_NOOP("Menuiserie", "Biscuit"),
        (
            ParamSpec("thickness", 2.0, 10.0),
            ParamSpec("width", 10.0, 80.0),
            ParamSpec("length", 20.0, 120.0),
        ),
    ),
    Family(
        "wood-screw",
        QT_TRANSLATE_NOOP("Menuiserie", "Vis à bois"),
        (ParamSpec("diameter", 2.0, 12.0), ParamSpec("length", 10.0, 300.0)),
    ),
    Family(
        "hinge-cup-35",
        QT_TRANSLATE_NOOP("Menuiserie", "Charnière à cuvette Ø35"),
        (ParamSpec("cup_diameter", 10.0, 60.0), ParamSpec("cup_depth", 3.0, 30.0)),
    ),
    Family(
        "drawer-slide-ball",
        QT_TRANSLATE_NOOP("Menuiserie", "Coulisse à billes"),
        (ParamSpec("length", 100.0, 1_200.0), ParamSpec("thickness", 5.0, 30.0)),
    ),
)

FAMILIES: Final[Mapping[str, Family]] = MappingProxyType({f.key: f for f in _FAMILY_LIST})


def family_of(key: str) -> Family | None:
    """Famille ``key``, ou ``None`` si elle est inconnue de cette version."""
    return FAMILIES.get(key)
