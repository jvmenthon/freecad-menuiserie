# SPDX-License-Identifier: LGPL-2.1-or-later
"""Stratégie de calcul (voir le paquet)."""

from __future__ import annotations

import math
from typing import ClassVar

from freecad.menuiserie.core.geometry import (
    CONTACT_TOLERANCE_MM,
    JointError,
    PlacedBlock,
    Prism,
    Vec3,
    moved,
)
from freecad.menuiserie.core.joints._base import (
    MIN_WALL_MM,
    JointKind,
    JointPlan,
    mm_text,
)
from freecad.menuiserie.core.joints._profile import ContactFrame, contact_frame
from freecad.menuiserie.core.joints._slot_shapes import half_stadium, rounded_rectangle
from freecad.menuiserie.core.joints.dowels import MAX_DOWEL_COUNT, positions
from freecad.menuiserie.core.joints.slots._params import (
    AUTO_EDGE_MM,
    AUTO_SIZE,
    AUTO_SPACING_MM,
    BISCUIT_SIZES,
    DOES_NOT_FIT,
    LOOSE_TENON_SIZES,
    MIN_BOTTOM_MM,
    NO_SIZE_FITS,
    TOO_DEEP,
    TOO_THIN,
    UNKNOWN_SIZE,
    SlotParams,
    SlotSize,
    SlotValues,
)


class _SlotStrategy:
    """Mortaises plates centrées sur le contact ; les sous-classes fournissent le commerce et la
    forme des logements."""

    kind: ClassVar[JointKind]
    sizes: ClassVar[tuple[SlotSize, ...]]  # du plus petit au plus grand
    custom_allowed: ClassVar[bool]

    def resolve(self, host: PlacedBlock, guest: PlacedBlock, params: SlotParams) -> SlotValues:
        """Valeurs effectives : taille, nombre et positions."""
        frame = contact_frame(host, guest, end_only=False, face_ok=True)
        return self._checked(frame, params)

    def plan(self, host: PlacedBlock, guest: PlacedBlock, params: SlotParams) -> JointPlan:
        """Mortaises dans les deux pièces ; pièce rapportée (repère de l'hôte)."""
        frame = contact_frame(host, guest, end_only=False, face_ok=True)
        values = self._checked(frame, params)
        host_cuts, guest_cuts, inserts = [], [], []
        for position in values.positions:
            host_cuts.append(moved(self._solid(frame, values, position, "host"), frame.to_host))
            guest_cuts.append(self._solid(frame, values, position, "guest"))
            inserts.append(moved(self._solid(frame, values, position, "insert"), frame.to_host))
        plan = JointPlan(
            host_cuts=tuple(host_cuts), guest_cuts=tuple(guest_cuts), inserts=tuple(inserts)
        )
        return frame.bridge.plan(plan)

    def _solid(self, frame: ContactFrame, values: SlotValues, position: float, role: str) -> Prism:
        raise NotImplementedError

    def _size(self, frame: ContactFrame, guest: PlacedBlock, params: SlotParams) -> SlotSize:
        """Taille de la liste choisie ; personnalisée (cotes saisies, complétées par la plus
        grande taille qui tient) si le type l'accepte et qu'elle est demandée ; sinon la plus
        grande taille du commerce qui tient."""
        if self.custom_allowed and params.custom_size:
            if params.thickness and params.along and params.total_depth:
                return SlotSize("", params.thickness, params.along, params.total_depth)
            size = self._largest_fitting(frame, guest, params)
            return SlotSize(
                "",
                params.thickness or size.thickness,
                params.along or size.along,
                params.total_depth or size.total_depth,
            )
        if params.size == AUTO_SIZE:
            return self._largest_fitting(frame, guest, params)
        for size in self.sizes:
            if size.id == params.size:
                return size
        text = {"size": params.size, "sizes": ", ".join(s.id for s in self.sizes)}
        raise JointError(UNKNOWN_SIZE, text)

    def _largest_fitting(
        self, frame: ContactFrame, guest: PlacedBlock, params: SlotParams
    ) -> SlotSize:
        shortest = min(frame.contact.host_depth, guest.local_box().size(frame.normal))
        slim = max(frame.contact_thickness / 3, self.sizes[0].thickness)  # au plus un tiers
        fitting = [
            s
            for s in self.sizes
            if s.thickness <= slim + CONTACT_TOLERANCE_MM
            and _fits(frame, s, shortest, params.hole_clearance)
        ]
        if not fitting:
            text = {
                "contact_thickness": mm_text(frame.contact_thickness),
                "depth": mm_text(shortest),
            }
            raise JointError(NO_SIZE_FITS, text)
        return fitting[-1]

    def _checked(self, frame: ContactFrame, params: SlotParams) -> SlotValues:
        guest = frame.guest
        size = self._size(frame, guest, params)
        edge = params.edge_distance or min(AUTO_EDGE_MM, frame.contact_width / 2)
        count = params.count or _auto_count(frame.contact_width, edge, size.along)
        custom = self.custom_allowed and params.custom_size
        values = SlotValues(
            size.thickness,
            size.along,
            size.total_depth,
            count,
            edge,
            params.thickness_offset,
            params.hole_clearance,
            positions(frame.contact_width, edge, count),
            size.id,
            custom,
            self.custom_allowed,
        )
        _check_section(frame, values)
        _check_depths(frame, guest, values)
        _check_spacing(frame, values)
        return values


class LooseTenonStrategy(_SlotStrategy):
    """Faux tenons type Festool Domino : mortaise à bouts demi-ronds, dans la profondeur."""

    kind: ClassVar[JointKind] = JointKind.LOOSE_TENON
    sizes: ClassVar[tuple[SlotSize, ...]] = LOOSE_TENON_SIZES
    custom_allowed: ClassVar[bool] = True

    def _solid(self, frame: ContactFrame, values: SlotValues, position: float, role: str) -> Prism:
        """Section en stade dans le plan (largeur, épaisseur), extrudée à travers le joint."""
        base, direction, length = _extent(frame, values, role)
        rectangle = frame.contact.rectangle
        center = (
            rectangle.lo(frame.width_axis) + position,
            rectangle.center(frame.thickness_axis) + values.thickness_offset,
        )
        outline = rounded_rectangle(values.along, values.thickness, values.thickness / 2)
        points = tuple(_point(frame, center[0] + u, center[1] + v, base) for u, v in outline)
        return Prism(points, Vec3(0.0, 0.0, 0.0).with_component(frame.normal, direction * length))


class BiscuitStrategy(_SlotStrategy):
    """Biscuits type Lamello : stade dans le plan du joint, de l'épaisseur de la fente."""

    kind: ClassVar[JointKind] = JointKind.BISCUIT
    sizes: ClassVar[tuple[SlotSize, ...]] = BISCUIT_SIZES
    custom_allowed: ClassVar[bool] = False

    def _solid(self, frame: ContactFrame, values: SlotValues, position: float, role: str) -> Prism:
        """Stade (la lamelle) ou demi-stade (la fente d'une pièce, jeu de fond compris) dans le
        plan (largeur, normale), extrudé sur l'épaisseur de la fente."""
        base, direction, length = _extent(frame, values, role)
        rectangle = frame.contact.rectangle
        along = rectangle.lo(frame.width_axis) + position
        thick = (
            rectangle.center(frame.thickness_axis) + values.thickness_offset - values.thickness / 2
        )
        if role == "insert":
            outline = rounded_rectangle(values.along, length, length / 2)
            centre = base + direction * length / 2
        else:
            outline = half_stadium(values.along, length)
            centre = base
        points = []
        for u, v in outline:
            normal = centre + (v if role == "insert" else direction * v)
            points.append(_point(frame, along + u, thick, normal))
        extrusion = Vec3(0.0, 0.0, 0.0).with_component(frame.thickness_axis, values.thickness)
        return Prism(tuple(points), extrusion)


def _extent(frame: ContactFrame, values: SlotValues, role: str) -> tuple[float, float, float]:
    """Origine (coordonnée selon la normale), sens et longueur du logement de ``role`` : hôte et
    invitée s'enfoncent de la moitié de la pièce rapportée plus le jeu de fond, la pièce
    rapportée la traverse de part et d'autre du plan de contact."""
    reach, plane, sign = values.half_depth, frame.guest_plane, frame.sign
    if role == "host":
        return frame.host_near, sign, reach + values.hole_clearance
    if role == "guest":
        return plane, -sign, reach + values.hole_clearance
    return plane - sign * reach, sign, 2 * reach


def _point(frame: ContactFrame, across: float, level: float, normal: float) -> Vec3:
    """Point du repère de l'invitée : ``across`` selon la largeur du contact, ``level`` selon
    l'épaisseur, ``normal`` selon la normale du contact."""
    point = Vec3(0.0, 0.0, 0.0).with_component(frame.width_axis, across)
    return point.with_component(frame.thickness_axis, level).with_component(frame.normal, normal)


def _fits(frame: ContactFrame, size: SlotSize, shortest: float, clearance: float) -> bool:
    """Vrai si la taille tient dans l'épaisseur et dans la plus mince des deux pièces."""
    wall = size.thickness / 2 + MIN_WALL_MM
    return (
        frame.contact_thickness >= 2 * wall
        and shortest - (size.total_depth / 2 + clearance) >= MIN_BOTTOM_MM
        and frame.contact_width >= size.along + 2 * MIN_WALL_MM
    )


def _auto_count(width: float, edge: float, along: float) -> int:
    """Une mortaise sur un contact étroit, sinon assez pour qu'elles soient espacées de 150 mm au
    plus entre centres (le premier et le dernier à ``edge`` des bords)."""
    span = width - 2 * edge
    if span <= along:
        return 1
    return min(MAX_DOWEL_COUNT, max(2, math.ceil(span / AUTO_SPACING_MM) + 1))


def _check_section(frame: ContactFrame, values: SlotValues) -> None:
    room = frame.contact_thickness / 2 - values.thickness / 2 - abs(values.thickness_offset)
    if room < MIN_WALL_MM - CONTACT_TOLERANCE_MM:
        text = {
            "thickness": mm_text(values.thickness),
            "contact_thickness": mm_text(frame.contact_thickness),
            "wall": mm_text(MIN_WALL_MM),
        }
        raise JointError(TOO_THIN, text)


def _check_depths(frame: ContactFrame, guest: PlacedBlock, values: SlotValues) -> None:
    hole = values.half_depth + values.hole_clearance
    extents = (frame.contact.host_depth, guest.local_box().size(frame.normal))
    for extent in extents:
        if extent - hole < MIN_BOTTOM_MM - CONTACT_TOLERANCE_MM:
            text = {
                "depth": mm_text(hole),
                "extent": mm_text(extent),
                "bottom": mm_text(MIN_BOTTOM_MM),
            }
            raise JointError(TOO_DEEP, text)


def _check_spacing(frame: ContactFrame, values: SlotValues) -> None:
    half, width = values.along / 2, frame.contact_width
    first, last = values.positions[0], values.positions[-1]
    inside = first - half > -CONTACT_TOLERANCE_MM and width - last - half > -CONTACT_TOLERANCE_MM
    gaps = [b - a for a, b in zip(values.positions, values.positions[1:], strict=False)]
    apart = all(gap > values.along + CONTACT_TOLERANCE_MM for gap in gaps)
    if not (inside and apart):
        text = {
            "count": str(values.count),
            "along": mm_text(values.along),
            "width": mm_text(width),
            "edge": mm_text(values.edge_distance),
        }
        raise JointError(DOES_NOT_FIT, text)
