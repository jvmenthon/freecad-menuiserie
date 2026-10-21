# SPDX-License-Identifier: LGPL-2.1-or-later
"""Tourillons : chevilles rapportées, percées dans les deux pièces à travers leur contact.

Le contact se fait par le bout ou le chant de l'invitée (jamais par la face). Les tourillons
sont répartis le long de la largeur du contact, centrés dans son épaisseur ; chaque perçage a
un jeu de fond. Calculs dans le repère de l'invitée (:mod:`._profile`), puis perçages de
l'hôte et tourillons exprimés dans le repère de l'hôte.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import ClassVar, Final

from freecad.menuiserie.core.geometry import (
    CONTACT_TOLERANCE_MM,
    Cylinder,
    JointError,
    PlacedBlock,
    Vec3,
    moved,
)
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.joints._base import (
    MAX_COUNT,
    JointKind,
    JointPlan,
    count_param,
    length_param,
    mm_text,
    offset_param,
    validate_params,
)
from freecad.menuiserie.core.joints._profile import THICKNESS_AXIS, ContactFrame, contact_frame

__all__ = ["MAX_DOWEL_COUNT", "DowelParams", "DowelStrategy", "DowelValues"]

# Tourillons du commerce : diamètre → longueur (mm).
STANDARD_DOWELS: Final[Mapping[float, float]] = MappingProxyType(
    {6.0: 30.0, 8.0: 35.0, 10.0: 40.0, 12.0: 50.0}
)
MAX_DOWEL_COUNT: Final = MAX_COUNT  # nombre saisi de 0 (automatique) à 50
MAX_SPACING_MM: Final = 128.0  # entraxe maximal des tourillons automatiques
MIN_BOTTOM_MM: Final = 3.0  # matière laissée au fond de chaque perçage
_MARGIN: Final = 1e-9

TOO_THIN: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Pièces trop minces pour des tourillons : {thickness} mm d'épaisseur au contact, décalage "
    "de {offset} mm ({minimum} mm au moins sans décalage).",
)
TOO_WIDE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Tourillons de {diameter} mm trop gros pour l'épaisseur au contact ({thickness} mm, "
    "décalage compris).",
)
DEPTH_NOT_SHORTER: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "La profondeur dans la pièce qui reçoit ({depth} mm) doit être plus courte que les "
    "tourillons ({length} mm).",
)
HOLE_TOO_DEEP: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Perçage de {depth} mm trop profond pour une pièce de {extent} mm : il faut laisser au "
    "moins {bottom} mm de fond.",
)
DOES_NOT_FIT: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "{count} tourillons de {diameter} mm ne tiennent pas sur un contact de {width} mm "
    "(distance au bord {edge} mm).",
)


@dataclass(frozen=True)
class DowelParams:
    """Paramètres des tourillons (mm) ; 0 = automatique."""

    diameter: float = length_param(0.0)
    dowel_length: float = length_param(0.0)
    host_depth: float = length_param(0.0)
    count: int = count_param(0)
    edge_distance: float = length_param(0.0)
    thickness_offset: float = offset_param(0.0)
    hole_clearance: float = length_param(1.0)

    def __post_init__(self) -> None:
        validate_params(self)


@dataclass(frozen=True)
class DowelValues:
    """Valeurs effectives des tourillons (mm), affichées par le panneau."""

    diameter: float
    dowel_length: float
    host_depth: float
    count: int
    edge_distance: float
    thickness_offset: float
    hole_clearance: float
    positions: tuple[float, ...]  # le long du contact, depuis son bord

    @property
    def guest_depth(self) -> float:
        """Longueur du tourillon dans l'invitée."""
        return self.dowel_length - self.host_depth


class DowelStrategy:
    """Tourillons Ø ≤ ½ épaisseur, à 2 Ø du bord, entraxe de 128 mm au plus."""

    kind: ClassVar[JointKind] = JointKind.DOWELS

    def resolve(self, host: PlacedBlock, guest: PlacedBlock, params: DowelParams) -> DowelValues:
        """Valeurs effectives : cotes, nombre et positions des tourillons."""
        return _checked_values(contact_frame(host, guest, end_only=False), guest, params)

    def plan(self, host: PlacedBlock, guest: PlacedBlock, params: DowelParams) -> JointPlan:
        """Perçages dans les deux pièces ; tourillons rapportés (repère de l'hôte)."""
        frame = contact_frame(host, guest, end_only=False)
        values = _checked_values(frame, guest, params)
        dowels, host_holes, guest_holes = [], [], []
        for position in values.positions:
            center = _center(frame, values, position)
            dowels.append(_dowel(frame, values, center))
            host_holes.append(_host_hole(frame, values, center))
            guest_holes.append(_guest_hole(frame, values, center))
        return JointPlan(
            host_cuts=tuple(moved(hole, frame.to_host) for hole in host_holes),
            guest_cuts=tuple(guest_holes),
            inserts=tuple(moved(dowel, frame.to_host) for dowel in dowels),
        )


# --- Valeurs effectives ------------------------------------------------------------------


def _fits_thickness(diameter: float, thickness: float, offset: float) -> bool:
    """Vrai si le perçage reste dans l'épaisseur, décalage compris (comme ``_check_section``)."""
    return diameter / 2 < thickness / 2 - abs(offset) - CONTACT_TOLERANCE_MM


def auto_diameter(thickness: float, offset: float = 0.0) -> float:
    """Plus grand diamètre du commerce ne dépassant pas la moitié de ``thickness`` et dont le
    perçage, décalé de ``offset``, reste dans l'épaisseur."""
    fitting = [
        d
        for d in STANDARD_DOWELS
        if d <= thickness / 2 + _MARGIN and _fits_thickness(d, thickness, offset)
    ]
    if not fitting:
        text = {
            "thickness": mm_text(thickness),
            "offset": mm_text(offset),
            "minimum": mm_text(2 * min(STANDARD_DOWELS)),
        }
        raise JointError(TOO_THIN, text)
    return max(fitting)


def auto_length(diameter: float) -> float:
    """Longueur du tourillon du commerce de diamètre le plus proche par défaut."""
    smaller = [d for d in STANDARD_DOWELS if d <= diameter + _MARGIN]
    return STANDARD_DOWELS[max(smaller) if smaller else min(STANDARD_DOWELS)]


def auto_count(width: float, edge: float, diameter: float) -> int:
    """Au moins 2 tourillons, entraxe de 128 mm au plus, ``MAX_DOWEL_COUNT`` au plus (l'entraxe
    dépasse alors 128 mm sur un très long contact) ; jamais un entraxe refusé (au plus le
    diamètre, tolérance comprise) : 1 au milieu si la place manque."""
    span = width - 2 * edge
    if span <= diameter + CONTACT_TOLERANCE_MM:
        return 1
    count = min(MAX_DOWEL_COUNT, max(2, math.ceil(span / MAX_SPACING_MM - _MARGIN) + 1))
    while count > 1 and span / (count - 1) <= diameter + CONTACT_TOLERANCE_MM:
        count -= 1
    return count


def positions(width: float, edge: float, count: int) -> tuple[float, ...]:
    """Positions régulières de ``count`` tourillons de ``edge`` à ``width - edge`` (milieu
    pour un seul)."""
    if count == 1:
        return (width / 2,)
    step = (width - 2 * edge) / (count - 1)
    return tuple(edge + index * step for index in range(count))


def _values(frame: ContactFrame, params: DowelParams) -> DowelValues:
    width = frame.contact_width
    diameter = params.diameter or auto_diameter(frame.contact_thickness, params.thickness_offset)
    length = params.dowel_length or auto_length(diameter)
    edge = params.edge_distance or 2 * diameter
    count = params.count or auto_count(width, edge, diameter)
    return DowelValues(
        diameter=diameter,
        dowel_length=length,
        host_depth=params.host_depth or length / 2,
        count=count,
        edge_distance=edge,
        thickness_offset=params.thickness_offset,
        hole_clearance=params.hole_clearance,
        positions=positions(width, edge, count),
    )


def _checked_values(frame: ContactFrame, guest: PlacedBlock, params: DowelParams) -> DowelValues:
    values = _values(frame, params)
    _check_section(frame, values)
    _check_depths(frame, guest, values)
    _check_spacing(frame, values)
    return values


# --- Contrôles ---------------------------------------------------------------------------


def _check_section(frame: ContactFrame, values: DowelValues) -> None:
    thickness = frame.contact_thickness
    if not _fits_thickness(values.diameter, thickness, values.thickness_offset):
        text = {"diameter": mm_text(values.diameter), "thickness": mm_text(thickness)}
        raise JointError(TOO_WIDE, text)


def _check_depths(frame: ContactFrame, guest: PlacedBlock, values: DowelValues) -> None:
    if values.host_depth >= values.dowel_length:
        text = {"depth": mm_text(values.host_depth), "length": mm_text(values.dowel_length)}
        raise JointError(DEPTH_NOT_SHORTER, text)
    guest_extent = guest.local_box().size(frame.normal)
    for depth, extent in (
        (values.host_depth, frame.contact.host_depth),
        (values.guest_depth, guest_extent),
    ):
        hole = depth + values.hole_clearance
        if extent - hole < MIN_BOTTOM_MM - _MARGIN:
            text = {
                "depth": mm_text(hole),
                "extent": mm_text(extent),
                "bottom": mm_text(MIN_BOTTOM_MM),
            }
            raise JointError(HOLE_TOO_DEEP, text)


def _check_spacing(frame: ContactFrame, values: DowelValues) -> None:
    width, radius = frame.contact_width, values.diameter / 2
    first, last = values.positions[0], values.positions[-1]
    inside = first - radius > CONTACT_TOLERANCE_MM and width - last - radius > CONTACT_TOLERANCE_MM
    gaps = [b - a for a, b in zip(values.positions, values.positions[1:], strict=False)]
    apart = all(gap > values.diameter + CONTACT_TOLERANCE_MM for gap in gaps)
    if not (inside and apart):
        text = {
            "count": str(values.count),
            "diameter": mm_text(values.diameter),
            "width": mm_text(width),
            "edge": mm_text(values.edge_distance),
        }
        raise JointError(DOES_NOT_FIT, text)


# --- Solides (repère de l'invitée) -------------------------------------------------------


def _center(frame: ContactFrame, values: DowelValues, position: float) -> Vec3:
    """Centre du tourillon sur le plan de contact de l'invitée."""
    rectangle = frame.contact.rectangle
    point = Vec3(0.0, 0.0, 0.0).with_component(frame.normal, frame.guest_plane)
    point = point.with_component(frame.width_axis, rectangle.lo(frame.width_axis) + position)
    thickness = rectangle.center(THICKNESS_AXIS) + values.thickness_offset
    return point.with_component(THICKNESS_AXIS, thickness)


def _dowel(frame: ContactFrame, values: DowelValues, center: Vec3) -> Cylinder:
    """Tourillon : de son bout dans l'invitée vers l'hôte."""
    start = frame.guest_plane - frame.sign * values.guest_depth
    base = center.with_component(frame.normal, start)
    return Cylinder(base, frame.towards_host, values.diameter / 2, values.dowel_length)


def _host_hole(frame: ContactFrame, values: DowelValues, center: Vec3) -> Cylinder:
    """Perçage de l'hôte : depuis sa face de contact, profondeur + jeu de fond."""
    base = center.with_component(frame.normal, frame.host_near)
    depth = values.host_depth + values.hole_clearance
    return Cylinder(base, frame.towards_host, values.diameter / 2, depth)


def _guest_hole(frame: ContactFrame, values: DowelValues, center: Vec3) -> Cylinder:
    """Perçage de l'invitée : depuis sa face de contact, profondeur + jeu de fond."""
    depth = values.guest_depth + values.hole_clearance
    return Cylinder(center, frame.towards_host.opposite(), values.diameter / 2, depth)
