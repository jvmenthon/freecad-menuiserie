# SPDX-License-Identifier: LGPL-2.1-or-later
"""Stratégie de calcul (voir le paquet)."""

from __future__ import annotations

from dataclasses import replace
from typing import ClassVar, Final

from freecad.menuiserie.core.geometry import (
    Axis,
    Box,
    Cylinder,
    JointError,
    PlacedBlock,
    RigidTransform,
    Vec3,
    moved_axis,
    moved_box,
    relative_transform,
)
from freecad.menuiserie.core.joints._base import (
    MIN_WALL_MM,
    JointKind,
    JointPlan,
    mm_text,
)
from freecad.menuiserie.core.joints._shelf_layout import (
    Layout,
    choose_face,
    free_window,
    heights_of,
    pin_rows,
    side_boxes,
    touching_boxes,
    upright,
)
from freecad.menuiserie.core.joints.shelf_pins._params import (
    AUTO_DEPTH_MM,
    AUTO_DIAMETER_MM,
    AUTO_EDGE_MM,
    AUTO_MARGIN_MM,
    EPSILON,
    HOLE_TOO_DEEP,
    MIN_BOTTOM_MM,
    NO_SUCH_ROW,
    PITCH_TOO_SMALL,
    TOLERANCE_MM,
    TOO_SHORT,
    ShelfPinsParams,
    ShelfPinsValues,
)


class ShelfPinsStrategy:
    """Perçage LR32 : deux colonnes de trous dans un côté, taquets rapportés."""

    kind: ClassVar[JointKind] = JointKind.SHELF_PINS

    def resolve(
        self, host: PlacedBlock, guest: PlacedBlock, params: ShelfPinsParams
    ) -> ShelfPinsValues:
        """Valeurs effectives du côté ``host`` (distances, rangs, taquets), avec le nombre de
        trous et de taquets du montant opposé ``guest`` s'il est percé aussi."""
        values = _checked(host, params)[0]
        opposite = _opposite(host, guest, params, values)
        if opposite is None:
            return values
        other = opposite[0]
        return replace(values, opposite_pins=other.count, opposite_holes=other.hole_count)

    def plan(self, host: PlacedBlock, guest: PlacedBlock, params: ShelfPinsParams) -> JointPlan:
        """Trous percés dans la face intérieure ; taquets plantés dans les rangs choisis ; de
        même en miroir dans le montant opposé ``guest`` (s'il est distinct de ``host``)."""
        values, layout = _checked(host, params)
        holes, pins = _drilling(host, values, layout)
        opposite = _opposite(host, guest, params, values)
        if opposite is None:
            return JointPlan(host_cuts=holes, inserts=pins)
        guest_holes, guest_pins = _drilling(guest, *opposite)
        transform = relative_transform(host, guest)
        moved = tuple(_moved(solid, transform) for solid in guest_pins)
        return JointPlan(host_cuts=holes, guest_cuts=guest_holes, inserts=(*pins, *moved))


def opposite_values(
    host: PlacedBlock, guest: PlacedBlock, params: ShelfPinsParams
) -> ShelfPinsValues | None:
    """Valeurs effectives du perçage du montant opposé ``guest`` (``None`` s'il n'est pas
    percé)."""
    opposite = _opposite(host, guest, params, _checked(host, params)[0])
    return None if opposite is None else opposite[0]


def _opposite(
    host: PlacedBlock, guest: PlacedBlock, params: ShelfPinsParams, values: ShelfPinsValues
) -> tuple[ShelfPinsValues, Layout] | None:
    """Perçage en miroir du montant opposé : face tournée vers ``host``, rangs **aux mêmes
    hauteurs** que ceux de ``host`` (ramenées au bas de ``guest``) pour que la tablette repose de
    niveau, gardés seulement dans la zone libre de ``guest`` (ses propres assemblages) ; taquets
    dans les mêmes rangs."""
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
    lowest = own.zone[0] + own.end_margin - TOLERANCE_MM  # zone libre de ``guest``, marges
    highest = own.zone[1] - own.end_margin + TOLERANCE_MM
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
        own, rows=len(heights), heights=heights, pin_rows=pins, pin_row=pins[0] + 1 if pins else 0
    )
    return aligned, Layout(own_layout.face_sign, heights, pins)


def _drilling(
    side: PlacedBlock, values: ShelfPinsValues, layout: Layout
) -> tuple[tuple[Cylinder, ...], tuple[Cylinder, ...]]:
    """Trous et taquets d'un côté, dans son repère."""
    vertical, down = upright(side)
    box = side.local_box()
    face = Axis.of(2, layout.face_sign)
    plane = box.lo(2) if face.sign < 0 else box.hi(2)
    horizontal = 1 - vertical
    bottom = box.hi(vertical) if down > 0 else box.lo(vertical)
    columns = (box.lo(horizontal) + values.edge_distance, box.hi(horizontal) - values.edge_distance)
    holes: list[Cylinder] = []
    pins: list[Cylinder] = []
    radius, depth = values.hole_diameter / 2, values.hole_depth
    for row, height in enumerate(layout.heights):
        level = bottom - down * height
        for column in columns:
            base = _point(vertical, level, horizontal, column, plane)
            holes.append(Cylinder(base, face.opposite(), radius, values.hole_depth))
            if row in layout.pin_rows:  # taquet rond : tige dans le trou et saillie d'un tenant
                inner = _point(vertical, level, horizontal, column, plane - face.sign * depth)
                pins.append(Cylinder(inner, face, radius, depth + values.pin_projection))
    return tuple(holes), tuple(pins)


def _moved(pin: Cylinder, transform: RigidTransform) -> Cylinder:
    """Taquet du montant opposé exprimé dans le repère de l'hôte."""
    axis = moved_axis(transform, pin.axis)
    return Cylinder(transform.apply(pin.base), axis, pin.radius, pin.height)


REST_SLAB_MM: Final = 0.01  # épaisseur des appuis d'aimantation (seule leur face haute compte)


def pin_rests(host: PlacedBlock, values: ShelfPinsValues) -> tuple[Box, ...]:
    """Appuis possibles d'une tablette : à chaque rang de trous et dans chaque colonne, une
    plaque mince sous le dessus qu'aurait un taquet (repère du côté). Leur face haute guide
    l'aimantation du dessous de la tablette sur n'importe quel rang."""
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


def _point(vertical: int, level: float, horizontal: int, column: float, z: float) -> Vec3:
    point = Vec3(0.0, 0.0, z).with_component(vertical, level)
    return point.with_component(horizontal, column)


def _checked(host: PlacedBlock, params: ShelfPinsParams) -> tuple[ShelfPinsValues, Layout]:
    box = host.local_box()
    vertical, down = upright(host)
    bottom = box.hi(vertical) if down > 0 else box.lo(vertical)
    diameter = params.hole_diameter or AUTO_DIAMETER_MM
    depth = params.hole_depth or AUTO_DEPTH_MM
    thickness, total = box.size(2), box.size(vertical)
    if depth > thickness - MIN_BOTTOM_MM:
        text = {
            "depth": mm_text(depth),
            "thickness": mm_text(thickness),
            "bottom": mm_text(MIN_BOTTOM_MM),
        }
        raise JointError(HOLE_TOO_DEEP, text)
    edge = params.edge_distance or AUTO_EDGE_MM
    margin = params.end_margin or AUTO_MARGIN_MM
    if params.pitch < diameter + MIN_WALL_MM:
        text = {
            "pitch": mm_text(params.pitch),
            "diameter": mm_text(diameter),
            "minimum": mm_text(diameter + MIN_WALL_MM),
        }
        raise JointError(PITCH_TOO_SMALL, text)
    boxes = side_boxes(host, params.neighbors, vertical)
    sign = choose_face(params.face, host, boxes)
    touching = touching_boxes(boxes, host, sign)
    fixed = [heights_of(other, bottom, down, vertical) for other, fixed in touching if fixed]
    shelves = [heights_of(other, bottom, down, vertical) for other, fixed in touching if not fixed]
    window = free_window(fixed, total, params.zone_height)
    first = window[0] + margin
    span = window[1] - margin - first
    rows = params.rows or (int(span // params.pitch + EPSILON) + 1 if span >= 0 else 0)
    wide = box.size(1 - vertical) - 2 * edge - diameter
    if rows < 1 or span < (rows - 1) * params.pitch - 1e-6 or wide < 0:
        text = {
            "rows": str(max(rows, 1)),
            "pitch": mm_text(params.pitch),
            "margin": mm_text(margin),
            "edge": mm_text(edge),
        }
        raise JointError(TOO_SHORT, text)
    heights = tuple(first + index * params.pitch for index in range(rows))
    if not params.with_pins:
        chosen: tuple[int, ...] = ()
    elif params.pin_row:
        if params.pin_row > rows:
            raise JointError(NO_SUCH_ROW, {"row": str(params.pin_row), "rows": str(rows)})
        chosen = (params.pin_row - 1,)
    else:
        chosen = pin_rows(heights, shelves, diameter / 2)
    values = ShelfPinsValues(
        diameter,
        depth,
        params.pitch,
        edge,
        margin,
        rows,
        chosen[0] + 1 if chosen else 0,
        params.pin_projection,
        params.with_pins,
        chosen,
        heights,
        "plus" if sign > 0 else "minus",
        (window[0] + window[1]) / 2,
        window,
    )
    return values, Layout(sign, heights, chosen)
