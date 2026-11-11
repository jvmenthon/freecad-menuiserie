# SPDX-License-Identifier: LGPL-2.1-or-later
"""Taille, déplacement et orientation d'un ensemble à la souris : règles pures (EN-a, ADR 0038).

La boîte de l'ensemble (``Origin`` à ``Origin`` + cotes) est exprimée dans le repère de son Std
Part (``frame``, repère local vers global). Ce module ne dessine rien et ne lit aucun document :

- :func:`furniture_layout` (A1) : six poignées de face, trois flèches de déplacement au centre et
  trois anneaux de rotation, en coordonnées globales ; il réutilise ``core/magnet`` (flèches,
  poignées) et ``core/rotation`` (anneaux) sans les dupliquer ;
- :func:`resized_box` (A2) : la boîte après le déplacement d'une face, la face opposée fixe.

Aucun import de FreeCAD, de Qt ni de pivy.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final

from freecad.menuiserie.core.geometry import Box, Vec3
from freecad.menuiserie.core.magnet import (
    Arrow,
    Handle,
    ResizeResult,
    arrows,
    resize,
)
from freecad.menuiserie.core.rotation import Ring, ring_of
from freecad.menuiserie.core.snap import Frame

MIN_FURNITURE_MM: Final = 0.1  # cote minimale d'un ensemble tiré à la souris (A2)


@dataclass(frozen=True)
class FaceHandle:
    """Poignée d'une face de la boîte : ``handle`` (axe et sens), ``point`` (milieu de la face) et
    ``normal`` (normale sortante, unitaire), en coordonnées globales."""

    handle: Handle
    point: Vec3
    normal: Vec3

    @property
    def key(self) -> str:
        """Clé stable de la poignée (``-X``, ``+X``, ``-Y``…), pour la saisie à l'écran."""
        return ("+" if self.handle.at_end else "-") + "XYZ"[self.handle.axis]


@dataclass(frozen=True)
class FurnitureLayout:
    """Ce que la vue 3D dessine autour d'un ensemble sélectionné : six poignées, trois flèches
    (X, Y, Z) et trois anneaux (X, Y, Z). Vide pour une boîte sans volume (R3)."""

    handles: tuple[FaceHandle, ...] = ()
    arrows: tuple[Arrow, ...] = ()
    rings: tuple[Ring, ...] = ()

    @property
    def is_empty(self) -> bool:
        """Vrai s'il n'y a rien à dessiner."""
        return not (self.handles or self.arrows or self.rings)


def _has_volume(box: Box) -> bool:
    return all(box.size(i) > 0.0 for i in range(3))


def furniture_layout(box: Box, frame: Frame, size_mm: float) -> FurnitureLayout:
    """Poignées, flèches et anneaux de la boîte ``box`` (repère de ``frame``), les flèches
    mesurant ``size_mm`` (A1). Boîte sans volume : mise en page vide (R3). ``ValueError`` si
    ``size_mm`` n'est pas un réel strictement positif."""
    if not math.isfinite(size_mm) or size_mm <= 0:
        raise ValueError("furniture_layout.size_mm : longueur strictement positive attendue")
    if not _has_volume(box):
        return FurnitureLayout()
    to_global = frame.to_transform()
    axes = (frame.x, frame.y, frame.z)
    middle = Vec3(box.center(0), box.center(1), box.center(2))
    handles = []
    for axis in range(3):
        for at_end in (False, True):
            local = middle.with_component(axis, box.hi(axis) if at_end else box.lo(axis))
            normal = axes[axis].scaled(1.0 if at_end else -1.0)
            handles.append(FaceHandle(Handle(axis, at_end), to_global.apply(local), normal))
    rings = tuple(ring_of(box, to_global, axis) for axis in range(3))
    return FurnitureLayout(tuple(handles), tuple(arrows(frame, box, size_mm)), rings)


def resized_by(box: Box, handle: Handle, result: ResizeResult) -> Box:
    """Boîte après ``result`` (:func:`~freecad.menuiserie.core.magnet.resize`, éventuellement
    aimanté) : la face de ``handle`` a bougé, la face opposée est restée en place."""
    axis = handle.axis
    low = box.lo(axis) + result.origin_shift.component(axis)
    return box.with_range(axis, low, low + result.size)


def resized_box(box: Box, face: Handle, delta: float) -> Box:
    """Boîte dont la face ``face`` est tirée de ``delta`` mm vers l'extérieur (négatif : vers
    l'intérieur) ; la face opposée ne bouge pas et la cote reste au moins 0,1 mm (A2).
    ``ValueError`` si ``delta`` n'est pas fini."""
    return resized_by(box, face, resize(box, face, delta, (), 0.0, MIN_FURNITURE_MM))
