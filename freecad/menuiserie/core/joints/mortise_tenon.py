# SPDX-License-Identifier: LGPL-2.1-or-later
"""Tenon-mortaise : tenon ajouté au bout de l'invitée, mortaise enlevée dans l'hôte."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, Final

from freecad.menuiserie.core.geometry import PlacedBlock
from freecad.menuiserie.core.joints._base import (
    JointKind,
    JointPlan,
    flag_param,
    length_param,
    mm_round,
    offset_param,
    validate_params,
)
from freecad.menuiserie.core.joints._profile import (
    ContactFrame,
    ProfileRules,
    ProfileValues,
    build_profile,
    contact_frame,
)

__all__ = ["MortiseTenonParams", "MortiseTenonStrategy"]

_RULES: Final = ProfileRules(walled_width=True, extend_housing=False)


@dataclass(frozen=True)
class MortiseTenonParams:
    """Paramètres du tenon-mortaise (mm) ; 0 = automatique pour les cotes du tenon."""

    tenon_thickness: float = length_param(0.0)
    tenon_width: float = length_param(0.0)
    tenon_length: float = length_param(0.0)
    width_offset: float = offset_param(0.0)
    thickness_offset: float = offset_param(0.0)
    through: bool = flag_param(False)
    mortise_clearance: float = length_param(2.0)

    def __post_init__(self) -> None:
        validate_params(self)


class MortiseTenonStrategy:
    """Tenon au tiers de l'épaisseur, épaulements d'un sixième, longueur aux deux tiers."""

    kind: ClassVar[JointKind] = JointKind.MORTISE_TENON

    def resolve(
        self, host: PlacedBlock, guest: PlacedBlock, params: MortiseTenonParams
    ) -> ProfileValues:
        """Valeurs effectives du tenon et de la mortaise."""
        return _values(contact_frame(host, guest, end_only=True), params)

    def plan(self, host: PlacedBlock, guest: PlacedBlock, params: MortiseTenonParams) -> JointPlan:
        """Tenon ajouté à l'invitée, mortaise enlevée à l'hôte."""
        frame = contact_frame(host, guest, end_only=True)
        return build_profile(frame, _values(frame, params), _RULES)


def _values(frame: ContactFrame, params: MortiseTenonParams) -> ProfileValues:
    width = frame.contact_width
    depth = frame.contact.host_depth
    if params.through:
        length, housing = frame.through_length, depth
    else:
        length = params.tenon_length or mm_round(2 * depth / 3)
        housing = length + params.mortise_clearance
    return ProfileValues(
        thickness=params.tenon_thickness or mm_round(frame.contact_thickness / 3),
        width=params.tenon_width or width - 2 * mm_round(width / 6),
        length=length,
        thickness_offset=params.thickness_offset,
        width_offset=params.width_offset,
        housing_depth=housing,
    )
