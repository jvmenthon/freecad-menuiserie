# SPDX-License-Identifier: LGPL-2.1-or-later
"""Invitée prolongée ou raccourcie pour se ramener au cas que l'assemblage sait calculer.

Feuillure, mi-bois et onglet se calculent sur deux pièces qui se superposent. Posées au
contact (l'accrochage J6 crée des pièces qui se touchent), l'invitée est prolongée par la face
qui touche l'hôte jusque dans l'hôte, et sa pièce usinée reçoit la partie ajoutée (ADR 0014).

Tenon, languette, tourillons et queue d'aronde se calculent sur deux pièces au contact. Quand
elles se chevauchent (pièces dessinées hors tout), l'invitée est raccourcie de la partie qui
entre dans l'hôte, et sa pièce usinée perd cette partie avant de recevoir ses ajouts (ADR 0016).
Module privé.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass, replace

from freecad.menuiserie.core.contact import Contact, Overlap, classify
from freecad.menuiserie.core.geometry import (
    CONTACT_TOLERANCE_MM,
    Axis,
    Box,
    PlacedBlock,
    RigidTransform,
    Solid,
    Vec3,
    moved,
    moved_box,
    relative_transform,
)
from freecad.menuiserie.core.joints._base import JointPlan
from freecad.menuiserie.core.part_model import Dimensions

__all__ = ["Bridge", "bridged", "cut_plan", "through_host", "trimmed"]

_IDENTITY = RigidTransform.identity()
_SIZES = ("length", "width", "thickness")


@dataclass(frozen=True)
class Bridge:
    """Invitée vue par le calcul de l'assemblage : elle-même, prolongée jusque dans l'hôte
    (``addition``) ou raccourcie hors de l'hôte (``trim``). ``to_guest`` ramène le repère de
    cette invitée à celui de l'invitée ; ``addition`` et ``trim`` sont dans le repère de
    l'invitée, ``extension`` est la longueur ajoutée (0 sans contact)."""

    guest: PlacedBlock
    to_guest: RigidTransform = _IDENTITY
    addition: Box | None = None
    extension: float = 0.0
    trim: Box | None = None

    @property
    def additions(self) -> tuple[Box, ...]:
        """Partie ajoutée à l'invitée (aucune sans contact)."""
        return () if self.addition is None else (self.addition,)

    @property
    def trims(self) -> tuple[Box, ...]:
        """Partie retirée à l'invitée (aucune sans chevauchement)."""
        return () if self.trim is None else (self.trim,)

    def back(self, solid: Solid) -> Solid:
        """``solid`` du repère de l'invitée prolongée ou raccourcie vers celui de l'invitée."""
        return moved(solid, self.to_guest)

    def plan(self, plan: JointPlan) -> JointPlan:
        """Plan calculé sur l'invitée prolongée ou raccourcie, ramené à l'invitée : ses
        enlèvements, ajouts et parties retirées changent de repère ; la partie ajoutée s'ajoute
        à ses ajouts, la partie retirée à ses parties retirées."""
        if self.addition is None and self.trim is None:
            return plan
        return replace(
            plan,
            guest_cuts=tuple(self.back(solid) for solid in plan.guest_cuts),
            guest_additions=(
                *(self.back(solid) for solid in plan.guest_additions),
                *self.additions,
            ),
            guest_trims=(*(self.back(solid) for solid in plan.guest_trims), *self.trims),
        )


def _resized(guest: PlacedBlock, face: Axis, length: float) -> tuple[Bridge, Box]:
    """Invitée allongée (``length`` > 0) ou raccourcie (``length`` < 0) par sa face ``face``,
    et la partie ajoutée ou retirée (repère de l'invitée)."""
    sizes = [getattr(guest.dimensions, name) for name in _SIZES]
    ranges = [(0.0, size) for size in sizes]
    if face.sign > 0:
        ends = (sizes[face.index], sizes[face.index] + length)
        to_guest = _IDENTITY
    else:
        ends = (-length, 0.0)
        shift = Vec3.of([-length if index == face.index else 0.0 for index in range(3)])
        to_guest = RigidTransform(_IDENTITY.rotation, shift)
    ranges[face.index] = (min(ends), max(ends))
    sizes[face.index] += length
    block = PlacedBlock(Dimensions(*sizes), guest.placement.compose(to_guest))
    return Bridge(block, to_guest), Box.from_ranges(ranges)


def bridged(host: PlacedBlock, guest: PlacedBlock, extension: Callable[[Contact], float]) -> Bridge:
    """Invitée prolongée de ``extension(contact)`` mm par sa face au contact de l'hôte ; elle
    reste telle quelle si les pièces ne se touchent pas par une face (superposition, pièces
    écartées : le calcul par superposition donne alors son message)."""
    relation = classify(host, guest)
    if not isinstance(relation, Contact):
        return Bridge(guest)
    length = extension(relation)
    bridge, addition = _resized(guest, relation.guest_face, length)
    return replace(bridge, addition=addition, extension=length)


def through_host(host: PlacedBlock, guest: PlacedBlock) -> Bridge:
    """Invitée posée au contact prolongée à travers toute l'étendue de l'hôte (mi-bois, onglet)."""
    return bridged(host, guest, lambda contact: contact.host_depth)


def _entry_faces(common: Box, guest: PlacedBlock) -> Iterator[Axis]:
    """Faces de l'invitée par où elle entre dans l'hôte : la partie commune (repère de
    l'invitée) touche cette face sans traverser l'invitée jusqu'à la face opposée."""
    box = guest.local_box()
    for axis in range(3):
        if common.size(axis) >= box.size(axis) - CONTACT_TOLERANCE_MM:
            continue
        if common.hi(axis) >= box.hi(axis) - CONTACT_TOLERANCE_MM:
            yield Axis.of(axis, 1)
        elif common.lo(axis) <= box.lo(axis) + CONTACT_TOLERANCE_MM:
            yield Axis.of(axis, -1)


def trimmed(host: PlacedBlock, guest: PlacedBlock) -> Bridge:
    """Invitée raccourcie de la partie qui chevauche l'hôte, par la face où elle y entre en
    perdant le moins de matière (bout d'une traverse dessinée hors tout). Elle reste telle
    quelle si les pièces ne se chevauchent pas, ou si aucune face ne la ramène au contact :
    le calcul au contact donne alors son message."""
    relation = classify(host, guest)
    if not isinstance(relation, Overlap):
        return Bridge(guest)
    common = moved_box(relation.common, relative_transform(host, guest).inverse())
    box = guest.local_box()
    faces = sorted(
        _entry_faces(common, guest),
        key=lambda face: (common.size(face.index) / box.size(face.index), face.index),
    )
    if not faces:
        return Bridge(guest)
    face = faces[0]
    bridge, trim = _resized(guest, face, -common.size(face.index))
    return replace(bridge, trim=trim)


def cut_plan(host_cut: Solid, guest_cut: Solid, bridge: Bridge) -> JointPlan:
    """Plan d'un enlèvement dans chaque pièce (repère de chacune), plus la partie ajoutée à
    l'invitée posée au contact."""
    return JointPlan(
        host_cuts=(host_cut,), guest_cuts=(guest_cut,), guest_additions=bridge.additions
    )
