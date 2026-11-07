# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fonctions de perçage pour LR32 et taquets de tablette.

Ce module contient les fonctions de création des trous et taquets,
ainsi que la gestion des appuis d'aimantation.
"""

from __future__ import annotations

from typing import Final

from freecad.menuiserie.core.geometry import (
    Axis,
    Box,
    Cylinder,
    PlacedBlock,
    RigidTransform,
    Vec3,
)

from freecad.menuiserie.core.joints._shelf_layout import Layout, upright

from ._params import ShelfPinsValues


# Épaisseur des appuis d'aimantation (seule leur face haute compte)
REST_SLAB_MM: Final = 0.01


def _drilling(
    side: PlacedBlock, values: ShelfPinsValues, layout: Layout
) -> tuple[tuple[Cylinder, ...], tuple[Cylinder, ...]]:
    """Génère les trous et taquets d'un côté dans son repère.

    Args:
        side: Le côté à percer
        values: Les valeurs effectives du perçage
        layout: Le layout (hauteurs, rangs de taquets, signe de la face)

    Returns:
        tuple[tuple[Cylinder, ...], tuple[Cylinder, ...]]:
            - Premier tuple : les trous (host_cuts)
            - Deuxième tuple : les taquets (inserts)
    """
    vertical, down = upright(side)
    box = side.local_box()
    face = Axis.of(2, layout.face_sign)
    plane = box.lo(2) if face.sign < 0 else box.hi(2)
    horizontal = 1 - vertical
    bottom = box.hi(vertical) if down > 0 else box.lo(vertical)

    # Position des colonnes (distance depuis les bords horizontaux)
    columns = (
        box.lo(horizontal) + values.edge_distance,
        box.hi(horizontal) - values.edge_distance,
    )

    holes: list[Cylinder] = []
    pins: list[Cylinder] = []
    radius = values.hole_diameter / 2
    depth = values.hole_depth

    for row, height in enumerate(layout.heights):
        level = bottom - down * height
        for column in columns:
            base = _point(vertical, level, horizontal, column, plane)
            # Trou dans le côté
            holes.append(Cylinder(base, face.opposite(), radius, values.hole_depth))
            # Taquet rond : tige dans le trou et saillie d'un tenant
            if row in layout.pin_rows:
                inner = _point(vertical, level, horizontal, column, plane - face.sign * depth)
                pins.append(
                    Cylinder(inner, face, radius, depth + values.pin_projection)
                )

    return tuple(holes), tuple(pins)


def _moved(pin: Cylinder, transform: RigidTransform) -> Cylinder:
    """Applique une transformation à un taquet du montant opposé.

    Args:
        pin: Le taquet (cylindre) à transformer
        transform: La transformation à appliquer

    Returns:
        Cylinder: Le taquet transformé
    """
    from freecad.menuiserie.core.geometry import moved_axis

    axis = moved_axis(transform, pin.axis)
    return Cylinder(transform.apply(pin.base), axis, pin.radius, pin.height)


def _point(vertical: int, level: float, horizontal: int, column: float, z: float) -> Vec3:
    """Crée un point 3D dans le repère d'un côté.

    Args:
        vertical: Axe vertical (0, 1 ou 2)
        level: Niveau sur l'axe vertical
        horizontal: Axe horizontal (0, 1 ou 2)
        column: Position sur l'axe horizontal
        z: Position sur l'axe Z (profondeur)

    Returns:
        Vec3: Le point créé
    """
    point = Vec3(0.0, 0.0, z).with_component(vertical, level)
    return point.with_component(horizontal, column)


def pin_rests(host: PlacedBlock, values: ShelfPinsValues) -> tuple[Box, ...]:
    """Calcule les appuis possibles d'une tablette pour l'aimantation.

    Pour chaque rang de trous et dans chaque colonne, crée une plaque mince
    sous le dessus qu'aurait un taquet (repère du côté). Leur face haute guide
    l'aimantation du dessous de la tablette sur n'importe quel rang.

    Args:
        host: Le côté contenant les trous
        values: Les valeurs effectives du perçage

    Returns:
        tuple[Box, ...]: Les boîtes de collision pour l'aimantation
    """
    vertical, down = upright(host)
    box = host.local_box()
    horizontal = 1 - vertical
    bottom = box.hi(vertical) if down > 0 else box.lo(vertical)
    plane = box.hi(2) if values.face == "plus" else box.lo(2)
    out = plane + (1.0 if values.face == "plus" else -1.0) * values.pin_projection
    radius = values.hole_diameter / 2

    rests = []
    for height in values.heights:
        top = bottom - down * (height + radius)
        under = bottom - down * (height + radius - REST_SLAB_MM)
        for column in (
            box.lo(horizontal) + values.edge_distance,
            box.hi(horizontal) - values.edge_distance,
        ):
            ranges = [(0.0, 0.0)] * 3
            ranges[vertical] = (min(top, under), max(top, under))
            ranges[horizontal] = (column - radius, column + radius)
            ranges[2] = (min(plane, out), max(plane, out))
            rests.append(Box.from_ranges(ranges))

    return tuple(rests)
