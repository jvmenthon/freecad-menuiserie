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

AXES: Final = (0, 1, 2)
NO_MATERIAL_LEFT: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Feuillure : la pièce logée traverse l'autre de part en part et la couperait en deux (ou "
    "l'enlèverait entièrement) ; décalez-la ou réduisez ses cotes.",
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
        if _splits(cut, host.local_box()):
            raise JointError(NO_MATERIAL_LEFT, {})
        return RabbetValues(cut)

    def plan(self, host: PlacedBlock, guest: PlacedBlock, params: RabbetParams) -> JointPlan:
        """Feuillure enlevée à l'hôte ; invitée inchangée."""
        return JointPlan(host_cuts=(self.resolve(host, guest, params).cut,))


def _splits(cut: Box, host: Box) -> bool:
    """Vrai si enlever ``cut`` coupe ``host`` en deux ou l'enlève entièrement (forme invalide,
    recette de jv) : ``cut`` occupe toute l'étendue de ``host`` sur deux axes et, sur le
    troisième, ne touche aucune de ses faces (ou l'occupe aussi en entier). Une feuillure qui
    amincit ou rétrécit la pièce sur toute sa longueur reste permise."""
    spans = [_spans(cut, host, axis) for axis in AXES]
    if sum(spans) < len(AXES) - 1:
        return False
    if all(spans):
        return True
    free = spans.index(False)
    return (
        cut.lo(free) > host.lo(free) + CONTACT_TOLERANCE_MM
        and cut.hi(free) < host.hi(free) - CONTACT_TOLERANCE_MM
    )


def _spans(cut: Box, host: Box, axis: int) -> bool:
    """Vrai si ``cut`` occupe toute l'étendue de ``host`` sur l'axe ``axis``."""
    return (
        cut.lo(axis) <= host.lo(axis) + CONTACT_TOLERANCE_MM
        and cut.hi(axis) >= host.hi(axis) - CONTACT_TOLERANCE_MM
    )
