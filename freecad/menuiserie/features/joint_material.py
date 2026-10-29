# SPDX-License-Identifier: LGPL-2.1-or-later
"""Contrôle de la matière réelle d'un assemblage sur une pièce en bois (E3, spec § 4.5).

L'atelier place chaque usinage sur la boîte d'encombrement de la pièce. Sur une face plane qui
coïncide avec cette boîte, c'est exact ; sur une face courbe ou dans un vide de la forme, la
matière à enlever manque. Pour chaque enlèvement (mortaise, rainure, logement, trou) on compare
le volume enlevé sur la boîte et sur la forme réelle ; pour chaque ajout (épaulement du tenon),
on compare la matière qui l'entoure d'un millimètre. S'il en manque plus de 5 % l'assemblage
avertit, sans refuser. Une seule série de booléennes par recalcul, au plus :data:`MAX_PROBES`
volumes par pièce (spec § 4.9).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

from freecad.menuiserie.core.geometry import Solid
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.joints import JointPlan
from freecad.menuiserie.core.shaped import (
    MAX_FACES,
    missing_material_ratio,
    missing_material_warning_due,
)
from freecad.menuiserie.core.text import quoted_value
from freecad.menuiserie.features.blank_shape import box_of
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.i18n import report_warning, translated
from freecad.menuiserie.features.shaped_part import base_shape_of, is_shaped_part
from freecad.menuiserie.features.snap_geometry import ERRORS
from freecad.menuiserie.features.solids import grown_shape, solid_shape

__all__ = ["MAX_PROBES", "check_joint_material", "worst_missing_ratio"]

MAX_PROBES: Final = 32  # volumes comparés par pièce : borne du temps de calcul
CONTACT_MARGIN_MM: Final = 1.0

_MISSING: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Assemblage « {joint} » : il manque {percent} % de la matière à usiner sur la pièce en "
    "bois « {part} » (face courbe ou vide de la forme). L'usinage est placé sur sa boîte "
    "d'encombrement : vérifiez le résultat.",
)


def worst_missing_ratio(
    part: DocumentObject, cuts: Sequence[Solid], additions: Sequence[Solid]
) -> float:
    """Plus grande part (0 à 1) de matière manquante sur la pièce en bois ``part`` parmi ses
    enlèvements ``cuts`` et ses ajouts ``additions`` (repère de la pièce), 0 si aucune n'atteint
    le seuil de 5 % ou si le noyau géométrique échoue (contrôle indicatif : un volume non fini ou
    négatif, ou une forme de plus de ``MAX_FACES`` faces, ne le fait jamais échouer)."""
    probes = [solid_shape(solid) for solid in cuts[:MAX_PROBES]]
    room = MAX_PROBES - len(probes)
    probes += [grown_shape(solid_shape(solid), CONTACT_MARGIN_MM) for solid in additions[:room]]
    if not probes:
        return 0.0
    box, shape = box_of(part), base_shape_of(part)
    if len(shape.Faces) > MAX_FACES:  # forme démesurée : pas de booléennes (§ 4.9)
        return 0.0
    worst = 0.0
    try:
        for probe in probes:
            on_box, on_shape = box.common(probe).Volume, shape.common(probe).Volume
            if missing_material_warning_due(on_box, on_shape):
                worst = max(worst, missing_material_ratio(on_box, on_shape))
    except ERRORS:  # noyau géométrique en échec, volume non fini ou négatif
        return 0.0
    return worst


def check_joint_material(joint: DocumentObject, plan: JointPlan) -> None:
    """Avertit, dans la vue rapport, pour chaque pièce en bois de ``joint`` à qui il manque de
    la matière sous son usinage (E3) ; ne refuse jamais l'assemblage."""
    sides = (
        (joint.HostPart, plan.host_cuts, plan.host_additions),
        (joint.GuestPart, plan.guest_cuts, plan.guest_additions),
    )
    for part, cuts, additions in sides:
        if not is_shaped_part(part):
            continue
        ratio = worst_missing_ratio(part, cuts, additions)
        if ratio > 0.0:
            params = {
                "joint": quoted_value(joint.Label),
                "part": quoted_value(part.Label),
                "percent": str(round(ratio * 100)),
            }
            report_warning(translated(_MISSING, params))
