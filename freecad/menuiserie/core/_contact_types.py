# SPDX-License-Identifier: LGPL-2.1-or-later
"""Résultats de la position relative de deux pièces (valeurs figées). Module privé ; l'API est
dans :mod:`.contact`."""

from __future__ import annotations

from dataclasses import dataclass

from freecad.menuiserie.core._polyhedron import Plane, Polyhedron
from freecad.menuiserie.core.geometry import Axis, Box, RigidTransform

__all__ = ["Contact", "ObliqueContact", "Overlap", "Separated"]


@dataclass(frozen=True)
class Contact:
    """Deux pièces qui se touchent par une face (chevauchement nul à la tolérance près)."""

    guest_face: Axis
    host_face: Axis
    rectangle: Box  # aplati, repère de l'invitée
    host_depth: float  # étendue de l'hôte dans l'axe normal au contact


@dataclass(frozen=True)
class Overlap:
    """Deux pièces qui se chevauchent sur les trois axes."""

    common: Box  # repère de l'hôte


@dataclass(frozen=True)
class Separated:
    """Pièces écartées, ou qui ne se touchent que par une arête ou un coin."""


@dataclass(frozen=True)
class ObliqueContact:
    """Le bout (ou le chant) d'une invitée rencontre une face de l'hôte sans être d'équerre.

    Tout est exprimé dans le repère de l'invitée, sauf ``transform`` (invitée → hôte, rotation
    exacte). ``shoulder`` est le plan de la face de l'hôte (normale sortante de l'hôte) : c'est
    le plan d'épaulement ; ``opposite`` celui de la face opposée. ``removed`` est la partie de
    l'invitée qui entre dans l'hôte (coin retiré), ``added`` le prolongement de l'invitée jusqu'au
    plan (coin ajouté) ; ``None`` quand il n'y en a pas.
    """

    guest_face: Axis
    host_face: Axis
    angle: float  # degrés, écart entre la normale de la face de l'invitée et celle de l'hôte
    shoulder: Plane
    opposite: Plane
    removed: Polyhedron | None
    added: Polyhedron | None
    transform: RigidTransform
    host_depth: float  # étendue de l'hôte perpendiculairement au plan d'épaulement
