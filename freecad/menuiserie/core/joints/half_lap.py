# SPDX-License-Identifier: LGPL-2.1-or-later
"""Mi-bois : deux pièces de même épaisseur, à fleur, qui se chevauchent ; chacune est entaillée
sur une partie de l'épaisseur dans leur boîte commune (croix, T ou angle)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, Final

from freecad.menuiserie.core.contact import Overlap, classify
from freecad.menuiserie.core.geometry import (
    CONTACT_TOLERANCE_MM,
    Axis,
    Box,
    JointError,
    PlacedBlock,
    RigidTransform,
    moved_axis,
    moved_box,
    relative_transform,
)
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.joints._base import (
    JointKind,
    JointPlan,
    flag_param,
    length_param,
    mm_round,
    mm_text,
    validate_params,
)

__all__ = ["HalfLapParams", "HalfLapStrategy", "HalfLapValues"]

THICKNESS_AXIS: Final = 2  # épaisseur : axe Z local de chaque pièce

NOT_CROSSING: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Mi-bois : dessinez les deux pièces qui se croisent ; elles doivent se chevaucher.",
)
NOT_FLUSH: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Mi-bois : les deux pièces doivent avoir la même épaisseur et être à fleur."
)
TOO_DEEP: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Mi-bois : entaille de {depth} mm pour des pièces de {thickness} mm ; elle doit être moins "
    "profonde que l'épaisseur.",
)


@dataclass(frozen=True)
class HalfLapParams:
    """Paramètres du mi-bois (mm) ; ``depth`` = 0 : moitié de l'épaisseur."""

    depth: float = length_param(0.0)
    flip_side: bool = flag_param(False)

    def __post_init__(self) -> None:
        validate_params(self)


@dataclass(frozen=True)
class HalfLapValues:
    """Valeurs effectives : profondeurs des deux entailles et enlèvements dans le repère de
    chaque pièce."""

    depth: float  # entaille de l'hôte
    guest_depth: float  # entaille de l'invitée : le reste de l'épaisseur
    host_cut: Box  # repère de l'hôte
    guest_cut: Box  # repère de l'invitée


class HalfLapStrategy:
    """L'hôte perd le haut (+Z local) de la boîte commune sur ``depth``, l'invitée le bas sur
    le reste de l'épaisseur ; ``flip_side`` inverse haut et bas."""

    kind: ClassVar[JointKind] = JointKind.HALF_LAP

    def resolve(
        self, host: PlacedBlock, guest: PlacedBlock, params: HalfLapParams
    ) -> HalfLapValues:
        """Profondeurs effectives et entailles des deux pièces."""
        lap = _lap(host, guest)
        thickness = host.dimensions.thickness
        depth = params.depth or mm_round(thickness / 2)
        if depth >= thickness:
            values = {"depth": mm_text(depth), "thickness": mm_text(thickness)}
            raise JointError(TOO_DEEP, values)
        level = depth if params.flip_side else thickness - depth
        host_range = (0.0, level) if params.flip_side else (level, thickness)
        # Bornes de l'invitée elle-même (à fleur à la tolérance près) : jamais de peau.
        guest_low, guest_high = lap.guest_box.lo(THICKNESS_AXIS), lap.guest_box.hi(THICKNESS_AXIS)
        guest_range = (level, guest_high) if params.flip_side else (guest_low, level)
        guest_cut = lap.common.with_range(THICKNESS_AXIS, *guest_range)
        return HalfLapValues(
            depth=depth,
            guest_depth=thickness - depth,
            host_cut=lap.common.with_range(THICKNESS_AXIS, *host_range),
            guest_cut=moved_box(guest_cut, lap.to_host.inverse()),
        )

    def plan(self, host: PlacedBlock, guest: PlacedBlock, params: HalfLapParams) -> JointPlan:
        """Une entaille dans chaque pièce, rien d'ajouté."""
        values = self.resolve(host, guest, params)
        return JointPlan(host_cuts=(values.host_cut,), guest_cuts=(values.guest_cut,))


@dataclass(frozen=True)
class _Lap:
    """Chevauchement vu de l'hôte : boîte commune, boîte de l'invitée, passage invitée → hôte."""

    common: Box
    guest_box: Box
    to_host: RigidTransform


def _lap(host: PlacedBlock, guest: PlacedBlock) -> _Lap:
    """Chevauchement de deux pièces d'épaisseurs parallèles et égales, à fleur ;
    :class:`JointError` sinon (``NOT_SQUARE`` si elles ne sont pas d'équerre)."""
    relation = classify(host, guest)
    if not isinstance(relation, Overlap):
        raise JointError(NOT_CROSSING, {})
    to_host = relative_transform(host, guest)
    guest_box = moved_box(guest.local_box(), to_host)
    parallel = moved_axis(to_host, Axis.Z_POS).index == THICKNESS_AXIS
    flush = (
        abs(guest_box.lo(THICKNESS_AXIS)) <= CONTACT_TOLERANCE_MM
        and abs(guest_box.hi(THICKNESS_AXIS) - host.dimensions.thickness) <= CONTACT_TOLERANCE_MM
    )
    if not (parallel and flush):
        raise JointError(NOT_FLUSH, {})
    return _Lap(relation.common, guest_box, to_host)
