# SPDX-License-Identifier: LGPL-2.1-or-later
"""Usinages d'une pièce usinée d'après les plans de ses assemblages (ADR 0006).

Ajouts, enlèvements et parties retirées de la brute, lus sur chaque assemblage ; un assemblage
impossible lève :class:`JointFailedError` (il signale lui-même son erreur, ADR 0026), ou est
ignoré pour un aperçu (``holding_only``). Aucun import de ``FreeCADGui``.
"""

from __future__ import annotations

from typing import Final

from freecad.menuiserie.core._polyhedron import PlanSolid
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.text import quoted_value
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.features.joints.base import is_joint, parts_mismatch, plan_for

__all__ = ["JointFailedError", "Machining", "machining_of"]

Machining = tuple[list[PlanSolid], list[PlanSolid], list[PlanSolid]]  # ajouts, coupes, retraits

_NOT_A_JOINT: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "« {label} » n'est pas un assemblage de l'atelier Menuiserie."
)


class JointFailedError(Exception):
    """Un assemblage de la pièce usinée est impossible : il le signale lui-même."""


def machining_of(
    obj: DocumentObject, blank: DocumentObject, *, holding_only: bool = False
) -> Machining:
    """Ajouts, enlèvements et parties retirées de ``blank`` d'après les plans de chacun de ses
    assemblages ; ``ValueError`` traduite si un assemblage ne relie plus ``blank`` (pièce
    modifiée par un script), :class:`JointFailedError` si l'un d'eux est impossible (ignoré
    si ``holding_only``)."""
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
            if holding_only:  # aperçu : l'assemblage est repris au relâchement
                continue
            raise JointFailedError from None  # l'assemblage signale lui-même son erreur
        if joint.HostPart == blank:
            additions.extend(plan.host_additions)
            cuts.extend(plan.host_cuts)
        if joint.GuestPart == blank:
            additions.extend(plan.guest_additions)
            cuts.extend(plan.guest_cuts)
            trims.extend(plan.guest_trims)
    return additions, cuts, trims
