# SPDX-License-Identifier: LGPL-2.1-or-later
"""Faux tenons et biscuits : mortaises plates dans les deux pièces, pièce rapportée entre elles.

Un faux tenon (type Domino) et un biscuit (lamelle) ne se distinguent que par leurs tailles
du commerce : même plan d'usinage. Chaque logement est une boîte (la forme arrondie du commerce
est simplifiée) centrée dans l'épaisseur, répartie le long de la largeur du contact ; la pièce
rapportée la traverse de moitié dans chaque pièce (ADR 0033). Calculs dans le repère de
l'invitée (:mod:`._profile`).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import ClassVar, Final

from freecad.menuiserie.core.geometry import (
    CONTACT_TOLERANCE_MM,
    Box,
    JointError,
    PlacedBlock,
    moved_box,
)
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.joints._base import (
    JointKind,
    JointPlan,
    count_param,
    length_param,
    mm_text,
    offset_param,
    validate_params,
)
from freecad.menuiserie.core.joints._profile import THICKNESS_AXIS, ContactFrame, contact_frame
from freecad.menuiserie.core.joints.dowels import MAX_DOWEL_COUNT, positions

__all__ = ["BiscuitStrategy", "LooseTenonStrategy", "SlotParams", "SlotSize", "SlotValues"]

MIN_WALL_MM: Final = 2.0  # matière laissée de chaque côté de la mortaise, dans l'épaisseur
MIN_BOTTOM_MM: Final = 3.0  # matière laissée au fond de chaque logement
_EDGE_FACTOR: Final = 0.5  # distance au bord automatique : moitié de la longueur de la mortaise

TOO_THIN: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Pièces trop minces pour une mortaise de {thickness} mm : {contact_thickness} mm "
    "d'épaisseur au contact, il faut {wall} mm de matière de chaque côté.",
)
NO_SIZE_FITS: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Aucune taille du commerce ne tient dans ces pièces ({contact_thickness} mm d'épaisseur, "
    "{depth} mm de profondeur au plus) : saisissez une taille plus petite.",
)
TOO_DEEP: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Logement de {depth} mm trop profond pour une pièce de {extent} mm : il faut laisser au "
    "moins {bottom} mm de fond.",
)
DOES_NOT_FIT: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "{count} mortaises de {along} mm ne tiennent pas sur un contact de {width} mm "
    "(distance au bord {edge} mm).",
)


@dataclass(frozen=True)
class SlotSize:
    """Taille d'une pièce rapportée du commerce (mm) : épaisseur, longueur le long du joint,
    pénétration totale à travers le joint."""

    thickness: float
    along: float
    total_depth: float


@dataclass(frozen=True)
class SlotParams:
    """Paramètres des mortaises plates (mm) ; 0 = automatique."""

    thickness: float = length_param(0.0)
    along: float = length_param(0.0)
    total_depth: float = length_param(0.0)
    count: int = count_param(0)
    edge_distance: float = length_param(0.0)
    thickness_offset: float = offset_param(0.0)
    hole_clearance: float = length_param(1.0)

    def __post_init__(self) -> None:
        validate_params(self)


@dataclass(frozen=True)
class SlotValues:
    """Valeurs effectives des mortaises (mm), affichées par le panneau."""

    thickness: float
    along: float
    total_depth: float
    count: int
    edge_distance: float
    thickness_offset: float
    hole_clearance: float
    positions: tuple[float, ...]  # centres le long du contact, depuis son bord

    @property
    def half_depth(self) -> float:
        """Pénétration de la pièce rapportée dans chaque pièce."""
        return self.total_depth / 2


class _SlotStrategy:
    """Mortaises plates centrées sur le contact ; les sous-classes fournissent le commerce."""

    kind: ClassVar[JointKind]
    sizes: ClassVar[tuple[SlotSize, ...]]  # du plus petit au plus grand

    def resolve(self, host: PlacedBlock, guest: PlacedBlock, params: SlotParams) -> SlotValues:
        """Valeurs effectives : taille, nombre et positions."""
        frame = contact_frame(host, guest, end_only=False)
        return self._checked(frame, params)

    def plan(self, host: PlacedBlock, guest: PlacedBlock, params: SlotParams) -> JointPlan:
        """Mortaises dans les deux pièces ; pièce rapportée (repère de l'hôte)."""
        frame = contact_frame(host, guest, end_only=False)
        values = self._checked(frame, params)
        host_cuts, guest_cuts, inserts = [], [], []
        for position in values.positions:
            host_cuts.append(moved_box(_slot(frame, values, position, "host"), frame.to_host))
            guest_cuts.append(_slot(frame, values, position, "guest"))
            inserts.append(moved_box(_slot(frame, values, position, "insert"), frame.to_host))
        plan = JointPlan(
            host_cuts=tuple(host_cuts), guest_cuts=tuple(guest_cuts), inserts=tuple(inserts)
        )
        return frame.bridge.plan(plan)

    def _size(self, frame: ContactFrame, guest: PlacedBlock, params: SlotParams) -> SlotSize:
        """Taille saisie, complétée par la plus grande taille du commerce qui tient."""
        if params.thickness and params.along and params.total_depth:
            return SlotSize(params.thickness, params.along, params.total_depth)
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
        size = fitting[-1]
        return SlotSize(
            params.thickness or size.thickness,
            params.along or size.along,
            params.total_depth or size.total_depth,
        )

    def _checked(self, frame: ContactFrame, params: SlotParams) -> SlotValues:
        guest = frame.guest
        size = self._size(frame, guest, params)
        edge = params.edge_distance or size.along * _EDGE_FACTOR
        count = params.count or _auto_count(frame.contact_width, edge, size.along)
        values = SlotValues(
            size.thickness,
            size.along,
            size.total_depth,
            count,
            edge,
            params.thickness_offset,
            params.hole_clearance,
            positions(frame.contact_width, edge, count),
        )
        _check_section(frame, values)
        _check_depths(frame, guest, values)
        _check_spacing(frame, values)
        return values


class LooseTenonStrategy(_SlotStrategy):
    """Faux tenons : mortaises plates de 4 à 10 mm d'épaisseur (tailles du commerce)."""

    kind: ClassVar[JointKind] = JointKind.LOOSE_TENON
    sizes: ClassVar[tuple[SlotSize, ...]] = (
        SlotSize(4.0, 17.0, 20.0),
        SlotSize(5.0, 19.0, 30.0),
        SlotSize(6.0, 20.0, 40.0),
        SlotSize(8.0, 22.0, 50.0),
        SlotSize(10.0, 24.0, 50.0),
    )


class BiscuitStrategy(_SlotStrategy):
    """Biscuits : fentes de 4 mm (lamelles n° 0, 10 et 20)."""

    kind: ClassVar[JointKind] = JointKind.BISCUIT
    sizes: ClassVar[tuple[SlotSize, ...]] = (
        SlotSize(4.0, 47.0, 15.0),
        SlotSize(4.0, 53.0, 19.0),
        SlotSize(4.0, 56.0, 23.0),
    )


def _fits(frame: ContactFrame, size: SlotSize, shortest: float, clearance: float) -> bool:
    """Vrai si la taille tient dans l'épaisseur et dans la plus mince des deux pièces."""
    wall = size.thickness / 2 + MIN_WALL_MM
    return (
        frame.contact_thickness >= 2 * wall
        and shortest - (size.total_depth / 2 + clearance) >= MIN_BOTTOM_MM
        and frame.contact_width >= size.along + 2 * MIN_WALL_MM
    )


def _auto_count(width: float, edge: float, along: float) -> int:
    """Une mortaise sur un contact étroit, sinon une tous les 3 fois leur longueur environ."""
    span = width - 2 * edge
    if span <= along:
        return 1
    return min(MAX_DOWEL_COUNT, max(2, math.ceil(span / (3 * along)) + 1))


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


def _slot(frame: ContactFrame, values: SlotValues, position: float, role: str) -> Box:
    """Boîte de la mortaise de l'hôte, de l'invitée, ou de la pièce rapportée (repère de
    l'invitée)."""
    rectangle = frame.contact.rectangle
    along = rectangle.lo(frame.width_axis) + position
    thick = rectangle.center(THICKNESS_AXIS) + values.thickness_offset
    box = rectangle.with_range(frame.width_axis, along - values.along / 2, along + values.along / 2)
    box = box.with_range(THICKNESS_AXIS, thick - values.thickness / 2, thick + values.thickness / 2)
    reach = values.half_depth
    plane, sign = frame.guest_plane, frame.sign
    if role == "host":
        start = frame.host_near
        ends = (start, start + sign * (reach + values.hole_clearance))
    elif role == "guest":
        ends = (plane, plane - sign * (reach + values.hole_clearance))
    else:
        ends = (plane - sign * reach, plane + sign * reach)
    return box.with_range(frame.normal, min(ends), max(ends))
