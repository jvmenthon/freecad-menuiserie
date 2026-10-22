# SPDX-License-Identifier: LGPL-2.1-or-later
"""Feuillure ou logement : la place occupée par l'invitée est enlevée de l'hôte."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, Final

from freecad.menuiserie.core.geometry import CONTACT_TOLERANCE_MM, Box, JointError, PlacedBlock
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.joints._base import (
    JointKind,
    JointPlan,
    flag_param,
    require_overlap,
    validate_params,
)

__all__ = ["RabbetParams", "RabbetStrategy", "RabbetValues"]

CROSS_SECTION: Final = (1, 2)  # largeur et épaisseur de l'hôte
NO_MATERIAL_LEFT: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Feuillure : la pièce logée traverse toute la largeur ou toute l'épaisseur de l'autre ; "
    "elle doit n'en occuper qu'une partie (décalez-la ou réduisez ses cotes).",
)


@dataclass(frozen=True)
class RabbetParams:
    """Paramètres de la feuillure : filante (toute la longueur de l'hôte) par défaut."""

    through: bool = flag_param(True)

    def __post_init__(self) -> None:
        validate_params(self)


@dataclass(frozen=True)
class RabbetValues:
    """Valeurs effectives : enlèvement dans le repère de l'hôte."""

    cut: Box

    @property
    def length(self) -> float:
        """Longueur de la feuillure (axe X de l'hôte)."""
        return self.cut.size(0)


class RabbetStrategy:
    """Enlèvement = boîte commune aux deux pièces, prolongée si la feuillure est filante."""

    kind: ClassVar[JointKind] = JointKind.RABBET

    def resolve(self, host: PlacedBlock, guest: PlacedBlock, params: RabbetParams) -> RabbetValues:
        """Enlèvement effectif dans l'hôte."""
        cut = require_overlap(host, guest).common
        if params.through:
            cut = cut.with_range(0, 0.0, host.dimensions.length)
        crossed = [_spans(cut, host.local_box(), axis) for axis in CROSS_SECTION]
        if any(crossed) if params.through else all(crossed):
            raise JointError(NO_MATERIAL_LEFT, {})
        return RabbetValues(cut)

    def plan(self, host: PlacedBlock, guest: PlacedBlock, params: RabbetParams) -> JointPlan:
        """Feuillure enlevée à l'hôte ; invitée inchangée."""
        return JointPlan(host_cuts=(self.resolve(host, guest, params).cut,))


def _spans(cut: Box, host: Box, axis: int) -> bool:
    """Vrai si ``cut`` occupe toute l'étendue de ``host`` sur l'axe ``axis`` : une feuillure
    filante qui traverse ainsi la pièce la coupe en deux ou l'amincit sur toute une face, un
    logement qui traverse largeur et épaisseur la tronçonne (forme invalide, recette de jv)."""
    return (
        cut.lo(axis) <= host.lo(axis) + CONTACT_TOLERANCE_MM
        and cut.hi(axis) >= host.hi(axis) - CONTACT_TOLERANCE_MM
    )
