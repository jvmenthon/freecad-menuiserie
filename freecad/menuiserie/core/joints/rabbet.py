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
    """Paramètres de la feuillure : filante (d'un bout à l'autre de l'hôte, dans le sens où la
    pièce logée l'occupe, ADR 0027) par défaut ; ``depth`` (mm) ne sert qu'aux pièces posées
    au contact, 0 = moitié de l'épaisseur de l'hôte (épaisseur de la pièce logée contre un
    chant ou un bout)."""

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
        """Longueur de la feuillure : la plus grande de ses étendues sur les axes X et Y de
        l'hôte (axe où elle file)."""
        return self.cut.size(_run_axis(self.cut))


class RabbetStrategy:
    """Enlèvement = boîte commune aux deux pièces, prolongée d'un bout à l'autre de l'hôte, dans
    le sens où la pièce logée l'occupe, si la feuillure est filante (ADR 0027)."""

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
            axis = _run_axis(cut)
            cut = cut.with_range(axis, host.local_box().lo(axis), host.local_box().hi(axis))
        if _splits(cut, host.local_box()):
            raise JointError(NO_MATERIAL_LEFT, {})
        return RabbetValues(cut, bridge.extension)


def _run_axis(cut: Box) -> int:
    """Axe de l'hôte où file la feuillure : X ou Y, celui où la pièce logée occupe le plus de
    longueur dans l'hôte (X à égalité). Un logement d'étagère en travers d'une joue file
    ainsi sur sa largeur, un fond le long de la joue (ADR 0027)."""
    return 0 if cut.size(0) >= cut.size(1) else 1


def _bridge(host: PlacedBlock, guest: PlacedBlock, params: RabbetParams) -> Bridge:
    """Pièce logée prolongée de ``depth`` quand elle est posée au contact ; ``JointError`` si
    la feuillure traverserait l'hôte. Par défaut : moitié de l'épaisseur de l'hôte contre sa
    face, épaisseur de la pièce logée contre un chant ou un bout (ADR 0027)."""

    def extension(contact: Contact) -> float:
        default = contact.host_depth / 2 if contact.host_face.index == 2 else guest_thickness
        depth = params.depth or mm_round(default)
        if depth >= contact.host_depth:
            values = {"depth": mm_text(depth), "available": mm_text(contact.host_depth)}
            raise JointError(TOO_DEEP, values)
        return depth

    guest_thickness = guest.dimensions.thickness
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
