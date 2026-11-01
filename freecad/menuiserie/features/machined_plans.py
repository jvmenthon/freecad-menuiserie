# SPDX-License-Identifier: LGPL-2.1-or-later
"""Plans d'usinage d'une pièce usinée : assemblages et profils d'arête (ADR 0006, ADR 0029).

Lecture seule : calcule, pour la brute d'une pièce usinée, les ajouts, enlèvements, parties
retirées et coupes de profil que :func:`~freecad.menuiserie.features.solids.machined_shape`
applique. Module privé de :mod:`freecad.menuiserie.features.machined_part`.
"""

from __future__ import annotations

from typing import Final

from freecad.menuiserie.core._extrusion import Extrusion
from freecad.menuiserie.core._polyhedron import PlanSolid
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.text import quoted_value
from freecad.menuiserie.features.edge_profile import edge_cuts, is_edge_profile
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.features.joints.base import is_joint, parts_mismatch, plan_for

__all__ = ["JointFailedError", "finishes_of", "machining_of"]

_NOT_A_JOINT: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "« {label} » n'est pas un assemblage de l'atelier Menuiserie."
)
_NOT_A_FINISH: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "« {label} » n'est pas une finition de l'atelier Menuiserie."
)
_FINISH_MISMATCH: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "La finition « {label} » ne correspond plus à la brute de sa pièce usinée : supprimez-la "
    "puis recréez-la.",
)


class JointFailedError(Exception):
    """Un assemblage de la pièce usinée est impossible : il le signale lui-même."""


def machining_of(
    obj: DocumentObject, blank: DocumentObject
) -> tuple[list[PlanSolid], list[PlanSolid], list[PlanSolid]]:
    """Ajouts, enlèvements et parties retirées de ``blank`` d'après les plans de chacun de ses
    assemblages ; ``ValueError`` traduite si un assemblage ne relie plus ``blank`` (pièce
    modifiée par un script), :class:`JointFailedError` si l'un d'eux est impossible."""
    additions: list[PlanSolid] = []
    cuts: list[PlanSolid] = []
    trims: list[PlanSolid] = []
    for joint in obj.Joints:
        if not is_joint(joint):
            raise ValueError(translated(_NOT_A_JOINT, {"label": quoted_value(joint.Label)}))
        if blank not in (joint.HostPart, joint.GuestPart):
            raise parts_mismatch(joint)
        try:
            plan = plan_for(joint)
        except ValueError:
            raise JointFailedError from None  # l'assemblage signale lui-même son erreur
        if joint.HostPart == blank:
            additions.extend(plan.host_additions)
            cuts.extend(plan.host_cuts)
        if joint.GuestPart == blank:
            additions.extend(plan.guest_additions)
            cuts.extend(plan.guest_cuts)
            trims.extend(plan.guest_trims)
    return additions, cuts, trims


def finishes_of(obj: DocumentObject, blank: DocumentObject) -> list[Extrusion]:
    """Coupes des profils d'arête de ``blank`` ; ``ValueError`` traduite si une finition n'est
    pas un profil de la brute, :class:`JointFailedError` si l'un d'eux est impossible (il
    signale lui-même son erreur)."""
    profiles: list[Extrusion] = []
    for finish in obj.Finishes:
        if not is_edge_profile(finish):
            raise ValueError(translated(_NOT_A_FINISH, {"label": quoted_value(finish.Label)}))
        if finish.Part != blank:
            raise ValueError(translated(_FINISH_MISMATCH, {"label": quoted_value(finish.Label)}))
        try:
            profiles.extend(edge_cuts(finish))
        except ValueError:
            raise JointFailedError from None
    return profiles
