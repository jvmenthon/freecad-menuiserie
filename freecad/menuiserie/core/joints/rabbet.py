# SPDX-License-Identifier: LGPL-2.1-or-later
"""Feuillure ou logement : la place occupée par l'invitée est enlevée de l'hôte."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from freecad.menuiserie.core.geometry import Box, PlacedBlock
from freecad.menuiserie.core.joints._base import (
    JointKind,
    JointPlan,
    flag_param,
    require_overlap,
    validate_params,
)

__all__ = ["RabbetParams", "RabbetStrategy", "RabbetValues"]


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
        return RabbetValues(cut)

    def plan(self, host: PlacedBlock, guest: PlacedBlock, params: RabbetParams) -> JointPlan:
        """Feuillure enlevée à l'hôte ; invitée inchangée."""
        return JointPlan(host_cuts=(self.resolve(host, guest, params).cut,))
