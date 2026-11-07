# SPDX-License-Identifier: LGPL-2.1-or-later
"""Jeu qui manque à une coulisse de tiroir : mesure et correction (ADR 0033).

Une coulisse se pose même si le côté du tiroir touche celui du caisson ; il manque alors du jeu
(l'épaisseur de la coulisse moins l'écart). :func:`slide_shortfall` le mesure ;
:func:`make_room_for_slide` l'obtient en écartant le côté du tiroir (« réduire le tiroir ») ou
celui du caisson (« élargir le meuble ») le long de l'épaisseur, par ``features/part_drag`` (membre
d'ensemble relié ensuite). Aucun import de ``FreeCADGui`` ; la transaction est celle de l'appelant.
"""

from __future__ import annotations

from typing import Final

import FreeCAD as App

from freecad.menuiserie.core.geometry import CONTACT_TOLERANCE_MM, Vec3
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.joints import JointKind
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.features.joints.base import is_joint, resolved_for
from freecad.menuiserie.features.part_drag import begin_drag, end_drag, move_part

__all__ = ["CABINET", "DRAWER", "make_room_for_slide", "slide_shortfall"]

DRAWER: Final = "drawer"
CABINET: Final = "cabinet"

_NOT_A_SLIDE: Final = QT_TRANSLATE_NOOP("Menuiserie", "« {label} » n'est pas une coulisse.")
_UNKNOWN_SIDE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Le côté à déplacer est « drawer » (tiroir) ou « cabinet » (meuble)."
)


def _slide_values(joint: DocumentObject) -> object:
    if not is_joint(joint) or joint.Proxy.KIND is not JointKind.DRAWER_SLIDE:
        raise ValueError(translated(_NOT_A_SLIDE, {"label": str(getattr(joint, "Label", joint))}))
    return resolved_for(joint)


def slide_shortfall(joint: DocumentObject) -> float:
    """Jeu qui manque (mm) entre les côtés de la coulisse ``joint``, 0 s'il est suffisant."""
    shortfall: float = _slide_values(joint).shortfall  # type: ignore[attr-defined]
    return 0.0 if shortfall <= CONTACT_TOLERANCE_MM else shortfall


def make_room_for_slide(joint: DocumentObject, move: str) -> list[str]:
    """Écarte les côtés de ``joint`` du jeu qui manque : ``move`` vaut ``"drawer"`` (le côté du
    tiroir s'éloigne) ou ``"cabinet"`` (le côté du caisson s'éloigne), selon l'épaisseur. Renvoie
    les avertissements de ``end_drag`` ; ``ValueError`` traduite si le côté est bloqué (formule,
    verrou) ou si ``move`` est inconnu."""
    if move not in (DRAWER, CABINET):
        raise ValueError(translated(_UNKNOWN_SIDE))
    values = _slide_values(joint)
    missing = slide_shortfall(joint)
    if not missing:
        return []
    direction = values.direction.unit()  # type: ignore[attr-defined]
    away = App.Vector(direction.x, direction.y, direction.z) * missing
    world = joint.HostPart.Placement.Rotation.multVec(away)
    part, sign = (joint.GuestPart, 1.0) if move == DRAWER else (joint.HostPart, -1.0)
    local = part.Placement.Rotation.inverted().multVec(world * sign)
    memento = begin_drag(part)
    move_part(memento, Vec3(local.x, local.y, local.z))
    return end_drag(memento)
