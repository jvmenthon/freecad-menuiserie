# SPDX-License-Identifier: LGPL-2.1-or-later
"""Assemblages par superposition posés au contact (ADR 0014, demande de jv).

Feuillure, mi-bois et onglet se calculent sur deux pièces qui se superposent. Posées au
contact (l'accrochage J6 crée des pièces qui se touchent), l'invitée est prolongée par la face
qui touche l'hôte jusque dans l'hôte : le calcul par superposition s'applique à cette invitée
prolongée, et la pièce usinée de l'invitée reçoit la partie ajoutée. Module privé.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace

from freecad.menuiserie.core.contact import Contact, classify
from freecad.menuiserie.core.geometry import (
    Box,
    PlacedBlock,
    RigidTransform,
    Solid,
    Vec3,
    moved,
)
from freecad.menuiserie.core.joints._base import JointPlan
from freecad.menuiserie.core.part_model import Dimensions

__all__ = ["Bridge", "bridged", "cut_plan", "through_host"]

_IDENTITY = RigidTransform.identity()
_SIZES = ("length", "width", "thickness")


@dataclass(frozen=True)
class Bridge:
    """Invitée vue par le calcul par superposition : elle-même si les pièces se superposent,
    prolongée jusque dans l'hôte si elles se touchent. ``to_guest`` ramène le repère de
    l'invitée prolongée à celui de l'invitée ; ``addition`` est la partie ajoutée (repère de
    l'invitée), ``extension`` sa longueur (0 sans contact)."""

    guest: PlacedBlock
    to_guest: RigidTransform = _IDENTITY
    addition: Box | None = None
    extension: float = 0.0

    @property
    def additions(self) -> tuple[Box, ...]:
        """Partie ajoutée à l'invitée (aucune sans contact)."""
        return () if self.addition is None else (self.addition,)

    def back(self, solid: Solid) -> Solid:
        """``solid`` du repère de l'invitée prolongée vers celui de l'invitée."""
        return moved(solid, self.to_guest)

    def plan(self, plan: JointPlan) -> JointPlan:
        """Plan calculé sur l'invitée prolongée, ramené à l'invitée : ses enlèvements changent
        de repère et la partie ajoutée s'ajoute à ses ajouts (enlevés ensuite)."""
        if self.addition is None:
            return plan
        return replace(
            plan,
            guest_cuts=tuple(self.back(solid) for solid in plan.guest_cuts),
            guest_additions=(
                *(self.back(solid) for solid in plan.guest_additions),
                *self.additions,
            ),
        )


def bridged(host: PlacedBlock, guest: PlacedBlock, extension: Callable[[Contact], float]) -> Bridge:
    """Invitée prolongée de ``extension(contact)`` mm par sa face au contact de l'hôte ; elle
    reste telle quelle si les pièces ne se touchent pas par une face (superposition, pièces
    écartées : le calcul par superposition donne alors son message)."""
    relation = classify(host, guest)
    if not isinstance(relation, Contact):
        return Bridge(guest)
    length = extension(relation)
    face = relation.guest_face
    sizes = [getattr(guest.dimensions, name) for name in _SIZES]
    ranges = [(0.0, size) for size in sizes]
    if face.sign > 0:
        ranges[face.index] = (sizes[face.index], sizes[face.index] + length)
        to_guest = _IDENTITY
    else:
        ranges[face.index] = (-length, 0.0)
        shift = Vec3.of([-length if index == face.index else 0.0 for index in range(3)])
        to_guest = RigidTransform(_IDENTITY.rotation, shift)
    sizes[face.index] += length
    prolonged = PlacedBlock(Dimensions(*sizes), guest.placement.compose(to_guest))
    return Bridge(prolonged, to_guest, Box.from_ranges(ranges), length)


def through_host(host: PlacedBlock, guest: PlacedBlock) -> Bridge:
    """Invitée posée au contact prolongée à travers toute l'étendue de l'hôte (mi-bois, onglet)."""
    return bridged(host, guest, lambda contact: contact.host_depth)


def cut_plan(host_cut: Solid, guest_cut: Solid, bridge: Bridge) -> JointPlan:
    """Plan d'un enlèvement dans chaque pièce (repère de chacune), plus la partie ajoutée à
    l'invitée posée au contact."""
    return JointPlan(
        host_cuts=(host_cut,), guest_cuts=(guest_cut,), guest_additions=bridge.additions
    )
