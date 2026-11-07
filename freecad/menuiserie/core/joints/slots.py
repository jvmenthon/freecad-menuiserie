# SPDX-License-Identifier: LGPL-2.1-or-later
"""Faux tenons et biscuits : mortaises plates dans les deux pièces, pièce rapportée entre elles.

Un faux tenon (type Domino) et un biscuit (lamelle) partagent le même plan d'usinage : logements
répartis le long de la largeur du contact, la pièce rapportée traversant de moitié chaque pièce
(ADR 0033). Leurs formes sont celles du commerce : le faux tenon a une section en stade (bouts
demi-ronds, comme les Domino de Festool) extrudée dans la profondeur ; le biscuit est un stade
dans le plan du joint (comme les lamelles de Lamello), de l'épaisseur de la fente. La taille se
choisit dans la liste du commerce (Festool, Lamello) ; seul le faux tenon accepte une taille
personnalisée. Calculs dans le repère de l'invitée (:mod:`._profile`).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import ClassVar, Final

from freecad.menuiserie.core.geometry import (
    CONTACT_TOLERANCE_MM,
    JointError,
    PlacedBlock,
    Prism,
    Vec3,
    moved,
)
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.joints._base import (
    JointKind,
    JointPlan,
    choice_param,
    count_param,
    flag_param,
    length_param,
    mm_text,
    offset_param,
    validate_params,
)
from freecad.menuiserie.core.joints._profile import THICKNESS_AXIS, ContactFrame, contact_frame
from freecad.menuiserie.core.joints._slot_shapes import half_stadium, rounded_rectangle
from freecad.menuiserie.core.joints.dowels import MAX_DOWEL_COUNT, positions

__all__ = [
    "AUTO_SIZE",
    "BISCUIT_SIZES",
    "LOOSE_TENON_SIZES",
    "BiscuitStrategy",
    "LooseTenonStrategy",
    "SlotParams",
    "SlotSize",
    "SlotValues",
    "half_stadium",
    "rounded_rectangle",
]

MIN_WALL_MM: Final = 2.0  # matière laissée de chaque côté de la mortaise, dans l'épaisseur
MIN_BOTTOM_MM: Final = 3.0  # matière laissée au fond de chaque logement
_EDGE_FACTOR: Final = 0.5  # distance au bord automatique : moitié de la longueur de la mortaise
AUTO_SIZE: Final = "auto"  # taille : la plus grande du commerce qui tient dans les pièces

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
UNKNOWN_SIZE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Taille « {size} » inconnue pour cet assemblage (tailles : {sizes})."
)
DOES_NOT_FIT: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "{count} mortaises de {along} mm ne tiennent pas sur un contact de {width} mm "
    "(distance au bord {edge} mm).",
)


@dataclass(frozen=True)
class SlotSize:
    """Taille d'une pièce rapportée du commerce (mm) : identifiant dans la liste, épaisseur,
    longueur le long du joint, pénétration totale à travers le joint."""

    id: str
    thickness: float
    along: float
    total_depth: float


LOOSE_TENON_SIZES: Final = (  # Festool Domino, du plus petit au plus grand
    SlotSize("4x20", 4.0, 16.6, 20.0),
    SlotSize("5x30", 5.0, 19.0, 30.0),
    SlotSize("6x40", 6.0, 20.0, 40.0),
    SlotSize("8x40", 8.0, 22.0, 40.0),
    SlotSize("8x50", 8.0, 22.0, 50.0),
    SlotSize("10x50", 10.0, 24.0, 50.0),
)
BISCUIT_SIZES: Final = (  # lamelles Lamello n° 0, 10 et 20 (fente de 4 mm)
    SlotSize("0", 4.0, 47.0, 15.0),
    SlotSize("10", 4.0, 53.0, 19.0),
    SlotSize("20", 4.0, 56.0, 23.0),
)
_SIZE_IDS: Final = (
    AUTO_SIZE,
    *(size.id for size in LOOSE_TENON_SIZES),
    *(size.id for size in BISCUIT_SIZES),
)


@dataclass(frozen=True)
class SlotParams:
    """Paramètres des mortaises plates (mm) ; 0 = automatique.

    ``size`` : taille de la liste du commerce (``auto`` : la plus grande qui tient). Les cotes
    ``thickness``, ``along`` et ``total_depth`` ne valent que pour le faux tenon à taille
    personnalisée (``custom_size``)."""

    size: str = choice_param(AUTO_SIZE, _SIZE_IDS)
    custom_size: bool = flag_param(False)
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
    size: str = AUTO_SIZE  # taille choisie dans la liste du commerce (vide : personnalisée)
    custom_size: bool = False  # taille personnalisée en vigueur
    custom_allowed: bool = False  # le type d'assemblage accepte une taille personnalisée

    @property
    def half_depth(self) -> float:
        """Pénétration de la pièce rapportée dans chaque pièce."""
        return self.total_depth / 2


class _SlotStrategy:
    """Mortaises plates centrées sur le contact ; les sous-classes fournissent le commerce et la
    forme des logements."""

    kind: ClassVar[JointKind]
    sizes: ClassVar[tuple[SlotSize, ...]]  # du plus petit au plus grand
    custom_allowed: ClassVar[bool]

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
        edge = params.edge_distance or size.along * _EDGE_FACTOR
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
            rectangle.center(THICKNESS_AXIS) + values.thickness_offset,
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
        thick = rectangle.center(THICKNESS_AXIS) + values.thickness_offset - values.thickness / 2
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
        extrusion = Vec3(0.0, 0.0, 0.0).with_component(THICKNESS_AXIS, values.thickness)
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
    return point.with_component(THICKNESS_AXIS, level).with_component(frame.normal, normal)


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
