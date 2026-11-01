# SPDX-License-Identifier: LGPL-2.1-or-later
"""Contrôles d'un profil d'arête : assemblages que sa zone touche (issue #5, B3, ADR 0029).

Un profil retire de la matière avant les ajouts et les enlèvements des assemblages : il ne casse
jamais un assemblage, mais il peut en couper un bord. Le contrôle est indicatif (jamais un refus)
et ne bloque jamais : un noyau géométrique en échec n'avertit de rien.
"""

from __future__ import annotations

from typing import Final

import Part

from freecad.menuiserie.core._polyhedron import PlanSolid
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.text import quoted_value
from freecad.menuiserie.features.edge_profile import edge_cuts
from freecad.menuiserie.features.extrusion_shape import extrusion_shape
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.features.joints.base import plan_for
from freecad.menuiserie.features.machined_part import machined_part_of
from freecad.menuiserie.features.solids import solid_shape

__all__ = ["profile_warnings", "touched_joints"]

MAX_SOLIDS: Final = 40  # solides d'assemblage essayés au plus par profil
_MIN_VOLUME_MM3: Final = 0.01  # volume commun sous lequel les solides ne font que se frôler
_TOUCHES: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Le profil « {profile} » touche l'assemblage « {joint} »."
)
_ERRORS: Final = (ValueError, Part.OCCError)


def _solids_on(joint: DocumentObject, blank: DocumentObject) -> list[PlanSolid]:
    """Ajouts et enlèvements de l'assemblage ``joint`` sur la pièce ``blank``."""
    plan = plan_for(joint)
    solids: list[PlanSolid] = []
    if joint.HostPart == blank:
        solids += [*plan.host_additions, *plan.host_cuts]
    if joint.GuestPart == blank:
        solids += [*plan.guest_additions, *plan.guest_cuts]
    return solids[:MAX_SOLIDS]


def touched_joints(profile: DocumentObject) -> list[DocumentObject]:
    """Assemblages dont un ajout ou un enlèvement coupe la zone enlevée par ``profile`` ; vide
    si le contrôle est impossible (profil ou assemblage en erreur, noyau géométrique en échec)."""
    blank = profile.Part
    machined = None if blank is None else machined_part_of(blank)
    if machined is None:
        return []
    try:
        zones = [extrusion_shape(cut) for cut in edge_cuts(profile)]
    except _ERRORS:
        return []
    touched = []
    for joint in machined.Joints:
        try:
            shapes = [solid_shape(solid) for solid in _solids_on(joint, blank)]
            if any(z.common(s).Volume > _MIN_VOLUME_MM3 for z in zones for s in shapes):
                touched.append(joint)
        except _ERRORS:
            continue
    return touched


def profile_warnings(profile: DocumentObject) -> tuple[str, ...]:
    """Avertissements traduits « Le profil touche l'assemblage X » pour ``profile``."""
    return tuple(
        translated(
            _TOUCHES,
            {"profile": quoted_value(profile.Label), "joint": quoted_value(joint.Label)},
        )
        for joint in touched_joints(profile)
    )
