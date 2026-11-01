# SPDX-License-Identifier: LGPL-2.1-or-later
"""Rainure-languette : languette ajoutée au chant ou au bout de l'invitée, rainure dans l'hôte."""

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

__all__ = ["DEFAULT_TONGUE_LENGTH_MM", "TongueGrooveParams", "TongueGrooveStrategy"]

DEFAULT_TONGUE_LENGTH_MM: Final = 10.0


@dataclass(frozen=True)
class TongueGrooveParams:
    """Paramètres de la rainure-languette (mm) ; 0 = automatique."""

    tongue_thickness: float = length_param(0.0)
    tongue_length: float = length_param(DEFAULT_TONGUE_LENGTH_MM)
    thickness_offset: float = offset_param(0.0)
    groove_clearance: float = length_param(1.0)
    through_groove: bool = flag_param(True)

    oblique_reference: str = choice_param(ObliqueReference.TENON_PIECE.value, OBLIQUE_REFERENCES)

    def __post_init__(self) -> None:
        validate_params(self)


class TongueGrooveStrategy:
    """Languette au tiers de l'épaisseur sur toute la longueur du contact, rainure filante."""

    kind: ClassVar[JointKind] = JointKind.TONGUE_GROOVE

    def resolve(
        self, host: PlacedBlock, guest: PlacedBlock, params: TongueGrooveParams
    ) -> ProfileValues:
        """Valeurs effectives de la languette et de la rainure."""
        return _values(
            profile_frame(host, guest, end_only=False, reference=params.oblique_reference), params
        )

    def plan(self, host: PlacedBlock, guest: PlacedBlock, params: TongueGrooveParams) -> JointPlan:
        """Languette ajoutée à l'invitée, rainure enlevée à l'hôte."""
        frame = profile_frame(host, guest, end_only=False, reference=params.oblique_reference)
        rules = ProfileRules(walled_width=False, extend_housing=params.through_groove)
        return build_any(frame, _values(frame, params), rules)


def _values(frame: Frame, params: TongueGrooveParams) -> ProfileValues:
    length = params.tongue_length or DEFAULT_TONGUE_LENGTH_MM
    return ProfileValues(
        thickness=params.tongue_thickness or mm_round(frame.contact_thickness / 3),
        width=frame.contact_width,
        length=length,
        thickness_offset=params.thickness_offset,
        width_offset=0.0,
        housing_depth=length + params.groove_clearance,
    )
