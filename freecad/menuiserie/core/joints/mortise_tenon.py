# SPDX-License-Identifier: LGPL-2.1-or-later
"""Tenon-mortaise : tenon ajouté au bout de l'invitée, mortaise enlevée dans l'hôte."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, Final

from freecad.menuiserie.core.geometry import PlacedBlock
from freecad.menuiserie.core.joints._base import (
    OBLIQUE_REFERENCES,
    JointKind,
    JointPlan,
    ObliqueReference,
    choice_param,
    flag_param,
    length_param,
    mm_round,
    offset_param,
    validate_params,
)
from freecad.menuiserie.core.joints._oblique import build_any
from freecad.menuiserie.core.joints._oblique_frame import Frame, profile_frame
from freecad.menuiserie.core.joints._profile import ProfileRules, ProfileValues

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

    oblique_reference: str = choice_param(ObliqueReference.TENON_PIECE.value, OBLIQUE_REFERENCES)

    def __post_init__(self) -> None:
        validate_params(self)


class MortiseTenonStrategy:
    """Tenon au tiers de l'épaisseur, épaulements d'un sixième, longueur aux deux tiers."""

    kind: ClassVar[JointKind] = JointKind.MORTISE_TENON

    def resolve(
        self, host: PlacedBlock, guest: PlacedBlock, params: MortiseTenonParams
    ) -> ProfileValues:
        """Valeurs effectives du tenon et de la mortaise."""
        return _values(
            profile_frame(host, guest, end_only=True, reference=params.oblique_reference), params
        )

    def plan(self, host: PlacedBlock, guest: PlacedBlock, params: MortiseTenonParams) -> JointPlan:
        """Tenon ajouté à l'invitée, mortaise enlevée à l'hôte."""
        frame = profile_frame(host, guest, end_only=True, reference=params.oblique_reference)
        return build_any(frame, _values(frame, params), _RULES)


def _values(frame: Frame, params: MortiseTenonParams) -> ProfileValues:
    width = frame.contact_width
    if params.through:
        length, housing = frame.through_length, frame.full_depth
    else:
        length = params.tenon_length or frame.auto_length(params.mortise_clearance)
        housing = length + params.mortise_clearance
    return ProfileValues(
        thickness=params.tenon_thickness or mm_round(frame.contact_thickness / 3),
        width=params.tenon_width or width - 2 * mm_round(width / 6),
        length=length,
        thickness_offset=params.thickness_offset,
        width_offset=params.width_offset,
        housing_depth=housing,
        **frame.oblique_values(),
    )
