# SPDX-License-Identifier: LGPL-2.1-or-later
"""Calcul du layout pour le perçage LR32.

Ce module contient les fonctions de calcul des positions des trous et taquets,
ainsi que la gestion du perçage miroir sur le montant opposé.
"""

from __future__ import annotations

from dataclasses import replace

from freecad.menuiserie.core.geometry import PlacedBlock

from freecad.menuiserie.core.joints._shelf_layout import (
    Layout,
    Neighbor,
    choose_face,
    free_window,
    heights_of,
    moved_box,
    relative_transform,
    upright,
)

from ._params import ShelfPinsParams, ShelfPinsValues


# Tolérances numériques
_EPSILON: float = 1e-9
_TOLERANCE_MM: float = 1e-6


def opposite_values(
    host: PlacedBlock, guest: PlacedBlock, params: ShelfPinsParams
) -> ShelfPinsValues | None:
    """Valeurs effectives du perçage du montant opposé ``guest``.

    Args:
        host: Le côté principal
        guest: Le montant opposé
        params: Les paramètres du perçage

    Returns:
        ShelfPinsValues: Les valeurs pour le montant opposé, ou None s'il n'est pas percé.
    """
    opposite = _opposite(host, guest, params, _checked(host, params)[0])
    return None if opposite is None else opposite[0]


def _opposite(
    host: PlacedBlock, guest: PlacedBlock, params: ShelfPinsParams, values: ShelfPinsValues
) -> tuple[ShelfPinsValues, Layout] | None:
    """Calcule le perçage en miroir du montant opposé.

    Le montant opposé est percé avec :
    - La face tournée vers ``host``
    - Les rangs **aux mêmes hauteurs** que ceux de ``host`` (ramenées au bas de ``guest``)
      pour que la tablette repose de niveau
    - Les rangs sont gardés seulement dans la zone libre de ``guest`` (ses propres assemblages)
    - Les taquets sont placés dans les mêmes rangs

    Args:
        host: Le côté principal
        guest: Le montant opposé
        params: Les paramètres du perçage
        values: Les valeurs déjà calculées pour host

    Returns:
        tuple[ShelfPinsValues, Layout]: Les valeurs et le layout pour le montant opposé,
        ou None si pas de perçage opposé.
    """
    from freecad.menuiserie.core.geometry import Vec3

    if guest == host or not params.both_sides:
        return None

    vertical, down = upright(host)
    box = host.local_box()
    bottom = box.hi(vertical) if down > 0 else box.lo(vertical)
    transform = relative_transform(host, guest)
    sign = 1.0 if values.face == "plus" else -1.0
    toward = transform.rotate(Vec3(0.0, 0.0, 1.0)).z * -sign

    low, _high = heights_of(moved_box(guest.local_box(), transform), bottom, down, vertical)

    mirrored = replace(
        params,
        face="plus" if toward > 0 else "minus",
        zone_height=max(params.zone_height - low, 0.0) if params.zone_height else 0.0,
        neighbors=params.guest_neighbors,
        guest_neighbors=(),
    )

    own, own_layout = _checked(guest, mirrored)

    # Filtrer les rangs pour garder seulement ceux dans la zone libre de guest
    lowest = own.zone[0] + own.end_margin - _TOLERANCE_MM  # zone libre de guest, marges
    highest = own.zone[1] - own.end_margin + _TOLERANCE_MM

    kept = [
        (row, height - low)
        for row, height in enumerate(values.heights)
        if lowest <= height - low <= highest
    ]

    heights = tuple(height for _row, height in kept)
    pins = tuple(index for index, (row, _h) in enumerate(kept) if row in values.pin_rows)

    if not heights:
        return own, own_layout

    aligned = replace(
        own,
        rows=len(heights),
        heights=heights,
        pin_rows=pins,
        pin_row=pins[0] + 1 if pins else 0,
    )

    return aligned, Layout(own_layout.face_sign, heights, pins)


def _checked(host: PlacedBlock, params: ShelfPinsParams) -> tuple[ShelfPinsValues, Layout]:
    """Calcule et valide le layout du perçage pour une pièce.

    Cette fonction :
    1. Calcule les valeurs par défaut si nécessaire
    2. Valide que les paramètres sont cohérents
    3. Calcule la zone libre entre les pièces voisines
    4. Détermine le nombre de rangs de trous
    5. Calcule les hauteurs de chaque rang
    6. Détermine quels rangs recevront des taquets

    Args:
        host: La pièce à percer
        params: Les paramètres du perçage

    Returns:
        tuple[ShelfPinsValues, Layout]: Les valeurs et le layout calculés.

    Raises:
        JointError: Si les paramètres sont invalides ou la pièce trop petite.
    """
    from freecad.menuiserie.core.geometry import Box
    from freecad.menuiserie.core.joints._base import mm_text
    from freecad.menuiserie.core.joints._shelf_layout import (
        side_boxes,
        touching_boxes,
    )
    from freecad.menuiserie.core.joints import JointError
    from ._params import (
        AUTO_DIAMETER_MM,
        AUTO_DEPTH_MM,
        AUTO_EDGE_MM,
        AUTO_MARGIN_MM,
        MIN_BOTTOM_MM,
        MIN_WALL_MM,
        HOLE_TOO_DEEP,
        TOO_SHORT,
        PITCH_TOO_SMALL,
        NO_SUCH_ROW,
        pin_rows,
    )

    box = host.local_box()
    vertical, down = upright(host)
    bottom = box.hi(vertical) if down > 0 else box.lo(vertical)

    # Valeurs par défaut
    diameter = params.hole_diameter or AUTO_DIAMETER_MM
    depth = params.hole_depth or AUTO_DEPTH_MM
    thickness = box.size(2)
    total = box.size(vertical)

    # Validation : profondeur du trou
    if depth > thickness - MIN_BOTTOM_MM:
        text = {
            "depth": mm_text(depth),
            "thickness": mm_text(thickness),
            "bottom": mm_text(MIN_BOTTOM_MM),
        }
        raise JointError(HOLE_TOO_DEEP, text)

    edge = params.edge_distance or AUTO_EDGE_MM
    margin = params.end_margin or AUTO_MARGIN_MM

    # Validation : pas trop petit
    if params.pitch < diameter + MIN_WALL_MM:
        text = {
            "pitch": mm_text(params.pitch),
            "diameter": mm_text(diameter),
            "minimum": mm_text(diameter + MIN_WALL_MM),
        }
        raise JointError(PITCH_TOO_SMALL, text)

    # Calcul de la zone libre entre les pièces voisines
    boxes = side_boxes(host, params.neighbors, vertical)
    sign = choose_face(params.face, host, boxes)
    touching = touching_boxes(boxes, host, sign)
    fixed = [heights_of(other, bottom, down, vertical) for other, fixed in touching if fixed]
    shelves = [heights_of(other, bottom, down, vertical) for other, fixed in touching if not fixed]
    window = free_window(fixed, total, params.zone_height)

    # Calcul du nombre de rangs
    first = window[0] + margin
    span = window[1] - margin - first
    rows = params.rows or (int(span // params.pitch + _EPSILON) + 1 if span >= 0 else 0)

    # Validation : pièce assez grande
    wide = box.size(1 - vertical) - 2 * edge - diameter
    if rows < 1 or span < (rows - 1) * params.pitch - 1e-6 or wide < 0:
        text = {
            "rows": str(max(rows, 1)),
            "pitch": mm_text(params.pitch),
            "margin": mm_text(margin),
            "edge": mm_text(edge),
        }
        raise JointError(TOO_SHORT, text)

    # Calcul des hauteurs de chaque rang
    heights = tuple(first + index * params.pitch for index in range(rows))

    # Détermination des rangs avec taquets
    if not params.with_pins:
        chosen: tuple[int, ...] = ()
    elif params.pin_row:
        if params.pin_row > rows:
            raise JointError(NO_SUCH_ROW, {"row": str(params.pin_row), "rows": str(rows)})
        chosen = (params.pin_row - 1,)
    else:
        chosen = pin_rows(heights, shelves, diameter / 2)

    values = ShelfPinsValues(
        hole_diameter=diameter,
        hole_depth=depth,
        pitch=params.pitch,
        edge_distance=edge,
        end_margin=margin,
        rows=rows,
        pin_row=chosen[0] + 1 if chosen else 0,
        pin_projection=params.pin_projection,
        with_pins=params.with_pins,
        pin_rows=chosen,
        heights=heights,
        face="plus" if sign > 0 else "minus",
        zone_height=(window[0] + window[1]) / 2,
        zone=window,
    )

    return values, Layout(sign, heights, chosen)
