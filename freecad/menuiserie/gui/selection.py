# SPDX-License-Identifier: LGPL-2.1-or-later
"""Sélection de l'interface lue avant de lancer « Pièce de bois » (J6d, ADR 0011).

La sélection est lue une fois : aucun observateur ni filtre n'est installé, et rien n'est
modifié (la sélection reste visible comme repère de l'accrochage). Les chemins sont ceux de
``getSelectionEx("", 0)`` (sans résolution) : le premier objet du chemin est la racine, les
liens (``App::Link``) et les Std Part traversés restent dans le chemin. Les éléments d'un même
objet sont groupés par FreeCAD, dans l'ordre où ils ont été sélectionnés.
"""

from __future__ import annotations

from typing import Final

import FreeCADGui as Gui

from freecad.menuiserie.core.geometry import Vec3
from freecad.menuiserie.features.picked import PickedElement

__all__ = ["picked_elements", "view_direction"]

NO_RESOLVE: Final = 0  # ResolveMode.NoResolve : chemins complets, sans suivre les liens
FROM_ABOVE: Final = Vec3(0.0, 0.0, 1.0)
ORIGIN: Final = Vec3(0.0, 0.0, 0.0)  # point que FreeCAD donne à une sélection faite par script


def picked_elements() -> list[PickedElement]:
    """Éléments sélectionnés (objets entiers compris, ignorés plus tard avec un message), avec
    leur point cliqué global quand FreeCAD le donne (un point par élément ; l'origine exacte, que
    FreeCAD attribue aux sélections par script, vaut « pas de point »)."""
    elements: list[PickedElement] = []
    for selected in Gui.Selection.getSelectionEx("", NO_RESOLVE):
        names = list(selected.SubElementNames) or [""]
        points = list(selected.PickedPoints)
        for index, name in enumerate(names):
            point = None
            if len(points) == len(names):
                click = Vec3(float(points[index].x), float(points[index].y), float(points[index].z))
                point = None if click == ORIGIN else click
            elements.append(PickedElement(selected.Object, name, point))
    return elements


def view_direction() -> Vec3:
    """Direction de la scène vers l'observateur dans la vue 3D active (+Z sans vue 3D : page
    TechDraw, aucun document)."""
    try:
        looking = Gui.ActiveDocument.ActiveView.getViewDirection()
    except (AttributeError, RuntimeError):
        return FROM_ABOVE
    return Vec3(-float(looking.x), -float(looking.y), -float(looking.z))
