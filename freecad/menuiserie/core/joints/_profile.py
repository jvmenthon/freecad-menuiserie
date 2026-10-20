# SPDX-License-Identifier: LGPL-2.1-or-later
"""Profil commun du tenon et de la languette : section, longueur, logement et contrôles.

Tous les calculs se font dans le repère de l'invitée (la pièce qui porte le profil) ; le
logement est ensuite exprimé dans le repère de l'hôte. Module privé.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from freecad.menuiserie.core.geometry import (
    CONTACT_TOLERANCE_MM,
    Box,
    Contact,
    JointError,
    PlacedBlock,
    RigidTransform,
    moved_box,
    relative_transform,
)
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.joints._base import JointPlan, mm_text, require_contact

THICKNESS_AXIS: Final = 2  # épaisseur du profil : axe Z local de l'invitée
_MARGIN: Final = 1e-9

FACE_CONTACT: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Les pièces se touchent par une face : cet assemblage se fait par le bout ou le chant.",
)
EDGE_CONTACT: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Le tenon se fait au bout de la pièce, pas sur son chant."
)
TOO_SMALL: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Pièces trop petites pour cet assemblage : section ou longueur nulle."
)
OUTSIDE_CONTACT: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "La section ({width} x {thickness} mm, décalages compris) sort de la surface de contact "
    "({contact_width} x {contact_thickness} mm).",
)
TOO_DEEP: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Logement trop profond : {depth} mm (longueur et jeu de fond) pour une pièce de "
    "{host_depth} mm.",
)
NO_WALL: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Le logement ne laisse pas de paroi de matière de chaque côté de la pièce qui le reçoit.",
)


@dataclass(frozen=True)
class ProfileValues:
    """Valeurs effectives d'un tenon ou d'une languette (mm), affichées par le panneau."""

    thickness: float
    width: float
    length: float
    thickness_offset: float
    width_offset: float
    housing_depth: float  # profondeur de la mortaise ou de la rainure


@dataclass(frozen=True)
class ProfileRules:
    """Ce qui distingue le tenon de la languette dans le plan."""

    walled_width: bool  # le logement garde une paroi aux deux bouts (mortaise)
    extend_housing: bool  # logement prolongé sur toute l'étendue de l'hôte (rainure filante)


@dataclass(frozen=True)
class ContactFrame:
    """Contact vu de l'invitée : axe normal, plan de contact et axe de la largeur."""

    contact: Contact
    width_axis: int
    to_host: RigidTransform  # repère de l'invitée → repère de l'hôte
    host_box: Box  # boîte de l'hôte dans le repère de l'invitée

    @property
    def normal(self) -> int:
        """Axe local de l'invitée normal au contact."""
        return self.contact.guest_face.index

    @property
    def sign(self) -> int:
        """Sens, sur l'axe normal, de l'invitée vers l'hôte."""
        return self.contact.guest_face.sign

    @property
    def guest_plane(self) -> float:
        """Coordonnée de la face de contact de l'invitée."""
        return self.contact.rectangle.lo(self.normal)

    @property
    def host_near(self) -> float:
        """Coordonnée de la face de contact de l'hôte (à l'écart toléré près de l'invitée)."""
        box = self.host_box
        return box.lo(self.normal) if self.sign > 0 else box.hi(self.normal)

    @property
    def host_far(self) -> float:
        """Coordonnée de la face opposée de l'hôte."""
        box = self.host_box
        return box.hi(self.normal) if self.sign > 0 else box.lo(self.normal)

    @property
    def through_length(self) -> float:
        """Longueur d'un profil traversant : face de l'invitée → face opposée de l'hôte."""
        return abs(self.host_far - self.guest_plane)

    @property
    def contact_width(self) -> float:
        """Étendue du contact selon la largeur du profil."""
        return self.contact.rectangle.size(self.width_axis)

    @property
    def contact_thickness(self) -> float:
        """Étendue du contact selon l'épaisseur du profil."""
        return self.contact.rectangle.size(THICKNESS_AXIS)


def contact_frame(host: PlacedBlock, guest: PlacedBlock, *, end_only: bool) -> ContactFrame:
    """Contact par le bout (``±X``) ou, si permis, par le chant (``±Y``) de l'invitée."""
    contact = require_contact(host, guest)
    normal = contact.guest_face.index
    if normal == THICKNESS_AXIS:
        raise JointError(FACE_CONTACT, {})
    if end_only and normal != 0:
        raise JointError(EDGE_CONTACT, {})
    to_host = relative_transform(host, guest)
    host_box = moved_box(host.local_box(), to_host.inverse())
    return ContactFrame(contact, 1 - normal, to_host, host_box)


def _centered(center: float, size: float) -> tuple[float, float]:
    return (center - size / 2, center + size / 2)


def _along_normal(frame: ContactFrame, section: Box, start: float, end: float) -> Box:
    low, high = sorted((start, end))
    return section.with_range(frame.normal, low, high)


def _profile(frame: ContactFrame, section: Box, length: float) -> Box:
    """Section prolongée de ``length`` depuis la face de l'invitée, vers l'hôte."""
    start = frame.guest_plane
    return _along_normal(frame, section, start, start + frame.sign * length)


def _housing(frame: ContactFrame, section: Box, depth: float) -> Box:
    """Logement de ``depth`` depuis la face de l'hôte ; débouchant s'il atteint la profondeur."""
    start = frame.host_near
    if depth >= frame.contact.host_depth - _MARGIN:
        return _along_normal(frame, section, start, frame.host_far)
    return _along_normal(frame, section, start, start + frame.sign * depth)


def _section(frame: ContactFrame, values: ProfileValues) -> Box:
    rectangle = frame.contact.rectangle
    width_center = rectangle.center(frame.width_axis) + values.width_offset
    thickness_center = rectangle.center(THICKNESS_AXIS) + values.thickness_offset
    section = rectangle.with_range(frame.width_axis, *_centered(width_center, values.width))
    section = section.with_range(THICKNESS_AXIS, *_centered(thickness_center, values.thickness))
    for axis in (frame.width_axis, THICKNESS_AXIS):
        if section.lo(axis) < rectangle.lo(axis) - _MARGIN:
            raise _outside(frame, values)
        if section.hi(axis) > rectangle.hi(axis) + _MARGIN:
            raise _outside(frame, values)
    return section


def _outside(frame: ContactFrame, values: ProfileValues) -> JointError:
    params = {
        "width": mm_text(values.width),
        "thickness": mm_text(values.thickness),
        "contact_width": mm_text(frame.contact_width),
        "contact_thickness": mm_text(frame.contact_thickness),
    }
    return JointError(OUTSIDE_CONTACT, params)


def _check_walls(housing: Box, host_box: Box, axes: tuple[int, ...]) -> None:
    for axis in axes:
        low_wall = housing.lo(axis) - host_box.lo(axis)
        high_wall = host_box.hi(axis) - housing.hi(axis)
        if min(low_wall, high_wall) <= CONTACT_TOLERANCE_MM:
            raise JointError(NO_WALL, {})


def build_profile(frame: ContactFrame, values: ProfileValues, rules: ProfileRules) -> JointPlan:
    """Plan d'un profil : ajout dans l'invitée, logement dans l'hôte, contrôles de matière.

    Le logement part de la face de l'hôte (pas de peau quand les pièces sont écartées de moins
    que la tolérance de contact) ; s'il atteint la profondeur de l'hôte, il débouche.
    """
    if min(values.width, values.thickness, values.length) <= 0:
        raise JointError(TOO_SMALL, {})
    host_depth = frame.contact.host_depth
    if values.housing_depth > host_depth + _MARGIN:
        depth = {"depth": mm_text(values.housing_depth), "host_depth": mm_text(host_depth)}
        raise JointError(TOO_DEEP, depth)
    section = _section(frame, values)
    host_box = frame.host_box
    housing = _housing(frame, section, values.housing_depth)
    if rules.extend_housing:
        axis = frame.width_axis
        housing = housing.with_range(axis, host_box.lo(axis), host_box.hi(axis))
    walled = (frame.width_axis, THICKNESS_AXIS) if rules.walled_width else (THICKNESS_AXIS,)
    _check_walls(housing, host_box, walled)
    return JointPlan(
        host_cuts=(moved_box(housing, frame.to_host),),
        guest_additions=(_profile(frame, section, values.length),),
    )
