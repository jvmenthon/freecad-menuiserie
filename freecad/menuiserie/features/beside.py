# SPDX-License-Identifier: LGPL-2.1-or-later
"""Pièce créée à côté d'une pièce sélectionnée en entier (issue « pièce perpendiculaire »).

Une pièce choisie dans l'arbre, sans face ni point cliqué, ne désigne aucun élément : plutôt que de
tomber à l'origine du document, la nouvelle pièce se pose contre le côté +X de l'encombrement de la
pièce choisie. La cible est une face fictive (rectangle de l'encombrement) : l'accrochage, la
rotation et le panneau fonctionnent comme contre une vraie face. Aucune modification du document ;
aucun import de ``FreeCADGui``.
"""

from __future__ import annotations

from collections.abc import Sequence

from freecad.menuiserie.core.geometry import Vec3
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.snap import FaceTarget, Frame
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.features.picked import PickedElement
from freecad.menuiserie.features.snap_geometry import owner_shape
from freecad.menuiserie.features.snap_targets import TargetReading

__all__ = ["beside_reading"]

_SIDE: str = QT_TRANSLATE_NOOP("Menuiserie", "Côté de « {label} »")


def beside_reading(elements: Sequence[PickedElement]) -> TargetReading | None:
    """Lecture d'une cible contre le côté +X de la première pièce choisie en entier (objet sans
    sous-élément ni point cliqué) ; ``None`` s'il n'y en a pas ou si elle n'a pas de forme."""
    for element in elements:
        if element.is_subelement() or element.point is not None:
            continue
        shape = owner_shape(element)
        if shape is None:
            continue
        box = shape.BoundBox
        extent = (box.YMax - box.YMin, box.ZMax - box.ZMin)
        if min(extent) <= 0.0:
            continue
        frame = Frame(
            Vec3(box.XMax, box.YMin, box.ZMin), Vec3(0, 1, 0), Vec3(0, 0, 1), Vec3(1, 0, 0)
        )
        name = translated(_SIDE, {"label": str(element.owner().Label)})
        target = FaceTarget(name, frame, extent, planar=True)
        return TargetReading((target,), (element,), (), (shape,), shape)
    return None
