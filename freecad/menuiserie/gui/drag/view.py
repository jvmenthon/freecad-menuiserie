# SPDX-License-Identifier: LGPL-2.1-or-later
"""La vue 3D vue par le glissement : rayon de la souris, projection en pixels, tolérance en mm.

Adaptateur mince sur la vue de FreeCAD (``Gui.activeView()``) ; les pixels sont ceux de FreeCAD
(origine en bas à gauche, voir ``double_click.view_point``). Rien n'est gardé au-delà de la vie de
la session.
"""

from __future__ import annotations

import math
from typing import Any

import FreeCAD as App

from freecad.menuiserie.core.geometry import Vec3
from freecad.menuiserie.core.magnet import Ray, mm_per_pixel
from freecad.menuiserie.features.snap_geometry import to_vec3
from freecad.menuiserie.gui.drag.geometry import mouse_ray

__all__ = ["ViewPort"]

Point = tuple[float, float]
PROBE_MM = 100.0  # segment de référence de la mesure de l'échelle


class ViewPort:
    """Vue 3D de FreeCAD : ``view`` doit offrir ``getPoint``, ``getPointOnScreen``,
    ``getViewDirection``, ``getCameraType``, ``getCameraNode`` et ``getSceneGraph``."""

    def __init__(self, view: Any) -> None:
        self.view = view

    def _camera(self) -> Vec3 | None:
        """Position de la caméra en perspective, ``None`` en caméra orthogonale."""
        if "persp" not in str(self.view.getCameraType()).lower():
            return None
        x, y, z = self.view.getCameraNode().position.getValue().getValue()
        return Vec3(float(x), float(y), float(z))

    def ray(self, point: Point) -> Ray:
        """Rayon de la souris au pixel ``point``."""
        focal = to_vec3(self.view.getPoint(int(point[0]), int(point[1])))
        return mouse_ray(focal, to_vec3(self.view.getViewDirection()), self._camera())

    def project(self, position: Vec3) -> Point:
        """Pixel où ``position`` (mm, global) s'affiche."""
        x, y = self.view.getPointOnScreen(App.Vector(position.x, position.y, position.z))
        return float(x), float(y)

    def mm(self, at: Vec3, pixels: float) -> float:
        """Longueur en mm de ``pixels`` pixels à la profondeur du point ``at`` (jamais nulle) :
        mesurée sur la projection d'un segment de 100 mm parallèle à l'écran, donc exacte pour
        la caméra orthogonale comme en perspective."""
        view = to_vec3(self.view.getViewDirection())
        side = Vec3(view.y, -view.x, 0.0)  # perpendiculaire à la vue et au haut du document
        if math.hypot(side.x, side.y) < 1e-6:
            side = Vec3(1.0, 0.0, 0.0)
        norm = math.hypot(side.x, side.y)
        end = Vec3(at.x + PROBE_MM * side.x / norm, at.y + PROBE_MM * side.y / norm, at.z)
        (x0, y0), (x1, y1) = self.project(at), self.project(end)
        on_screen = math.hypot(x1 - x0, y1 - y0)
        return mm_per_pixel(at, end, pixels / on_screen) if on_screen > 0 else PROBE_MM

    def scene_graph(self) -> Any:
        """Racine Coin de la vue."""
        return self.view.getSceneGraph()
