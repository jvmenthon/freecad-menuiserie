# SPDX-License-Identifier: LGPL-2.1-or-later
"""Feuillure ou logement : la place occupée par l'invitée est enlevée de l'hôte."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, Final

from freecad.menuiserie.core.contact import Contact
from freecad.menuiserie.core.geometry import CONTACT_TOLERANCE_MM, Box, JointError, PlacedBlock
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.joints._base import (
    JointKind,
    JointPlan,
    flag_param,
    length_param,
    mm_round,
    mm_text,
    require_overlap,
    validate_params,
)
from freecad.menuiserie.core.joints._bridge import Bridge, bridged

__all__ = ["RabbetParams", "RabbetStrategy", "RabbetValues"]

AXES: Final = (0, 1, 2)
NO_MATERIAL_LEFT: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Feuillure : la pièce logée traverse l'autre de part en part et la couperait en deux (ou "
    "l'enlèverait entièrement) ; décalez-la ou réduisez ses cotes.",
)
TOO_DEEP: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Feuillure : profondeur de {depth} mm dans une pièce de {available} mm ; elle doit être "
    "moins profonde.",
)


@dataclass(frozen=True)
class RabbetParams:
    """Paramètres de la feuillure : filante (toute la longueur de l'hôte) par défaut ;
    ``depth`` (mm) ne sert qu'aux pièces posées au contact, 0 = moitié de l'hôte traversé."""

    through: bool = flag_param(True)
    depth: float = length_param(0.0)

    def __post_init__(self) -> None:
        validate_params(self)


@dataclass(frozen=True)
class RabbetValues:
    """Valeurs effectives : enlèvement dans le repère de l'hôte, prolongement de la pièce
    logée posée au contact (0 si elle occupe déjà la place de la feuillure)."""

    cut: Box
    depth: float = 0.0

    @property
    def length(self) -> float:
        """Longueur de la feuillure (axe X de l'hôte)."""
        return self.cut.size(0)


class RabbetStrategy:
    """Enlèvement = boîte commune aux deux pièces, prolongée si la feuillure est filante."""

    kind: ClassVar[JointKind] = JointKind.RABBET

    def resolve(self, host: PlacedBlock, guest: PlacedBlock, params: RabbetParams) -> RabbetValues:
        """Enlèvement effectif dans l'hôte."""
        return self._resolve(host, _bridge(host, guest, params), params)

    def plan(self, host: PlacedBlock, guest: PlacedBlock, params: RabbetParams) -> JointPlan:
        """Feuillure enlevée à l'hôte ; invitée inchangée, ou prolongée dans la feuillure si
        elle est posée au contact."""
        bridge = _bridge(host, guest, params)
        cut = self._resolve(host, bridge, params).cut
        return bridge.plan(JointPlan(host_cuts=(cut,)))

    @staticmethod
    def _resolve(host: PlacedBlock, bridge: Bridge, params: RabbetParams) -> RabbetValues:
        cut = require_overlap(host, bridge.guest).common
        if params.through:
            cut = cut.with_range(0, 0.0, host.dimensions.length)
        if _splits(cut, host.local_box()):
            raise JointError(NO_MATERIAL_LEFT, {})
        return RabbetValues(cut, bridge.extension)


def _bridge(host: PlacedBlock, guest: PlacedBlock, params: RabbetParams) -> Bridge:
    """Pièce logée prolongée de ``depth`` (moitié de l'hôte traversé par défaut) quand elle
    est posée au contact ; ``JointError`` si la feuillure traverserait l'hôte."""

    def extension(contact: Contact) -> float:
        depth = params.depth or mm_round(contact.host_depth / 2)
        if depth >= contact.host_depth:
            values = {"depth": mm_text(depth), "available": mm_text(contact.host_depth)}
            raise JointError(TOO_DEEP, values)
        return depth

    return bridged(host, guest, extension)


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
