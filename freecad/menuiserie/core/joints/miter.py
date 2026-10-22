# SPDX-License-Identifier: LGPL-2.1-or-later
"""Onglet : deux pièces d'angle dessinées à leur longueur hors tout, qui se chevauchent au coin
dans leur boîte commune ``C`` ; chacune perd le prisme triangulaire de ``C`` situé du côté de
l'autre.

Notations (repère de l'hôte) : ``s`` = axe de l'arête du coin, selon lequel les deux pièces
couvrent exactement ``C`` (à fleur) ; ``u`` = axe selon lequel l'hôte se prolonge hors de
``C``, ``v`` = celui de l'invitée. Le plan de coupe contient ``s``, le coin extérieur (où les
deux bouts se rejoignent) et le coin intérieur de ``C`` : 45° pour deux largeurs égales, sinon
atan(w_invitée / w_hôte) et son complément ; les deux faces coupées coïncident toujours. Cadre
(``s`` = épaisseur) et coin de caisson (``s`` = profondeur) sont le même calcul. Enlèvement
seulement (ADR 0006) : les brutes gardent leur longueur hors tout. Posées au contact (bout de
l'invitée contre la face de l'hôte), l'invitée est prolongée jusqu'au coin extérieur (ADR 0014).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import ClassVar, Final

from freecad.menuiserie.core.contact import Overlap, classify
from freecad.menuiserie.core.geometry import (
    CONTACT_TOLERANCE_MM,
    CUT_OVERRUN_MM,
    Box,
    JointError,
    PlacedBlock,
    Prism,
    RigidTransform,
    Solid,
    Vec3,
    moved,
    moved_box,
    relative_transform,
)
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.joints._base import JointKind, JointPlan
from freecad.menuiserie.core.joints._bridge import Bridge, bridged

__all__ = ["MiterParams", "MiterStrategy", "MiterValues"]

ANGLE_DECIMALS: Final = 2  # angles de coupe rendus en degrés, au centième
_BOTH_SIDES: Final = 2  # pièce qui dépasse la boîte commune des deux côtés d'un axe

NOT_OVERLAPPING: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Onglet : dessinez les deux pièces à leur longueur hors tout ; elles doivent se chevaucher "
    "au coin, ou se toucher bout contre face.",
)
NOT_SAME_CORNER: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Onglet : les deux pièces doivent s'arrêter au même coin."
)
NOT_FLUSH: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Onglet : les deux pièces doivent avoir la même étendue le long de l'arête du coin et y "
    "être à fleur.",
)


@dataclass(frozen=True)
class MiterParams:
    """Paramètres de l'onglet : aucun en J4 (un renfort futur, Q8, ajoutera un champ)."""


@dataclass(frozen=True)
class MiterValues:
    """Valeurs effectives : angles de coupe (degrés, mesurés depuis une coupe d'équerre de la
    pièce, au centième) et enlèvements dans le repère de chaque pièce."""

    host_angle: float  # atan(w_invitée / w_hôte)
    guest_angle: float  # son complément
    host_cut: Solid  # prisme, repère de l'hôte
    guest_cut: Solid  # prisme, repère de l'invitée


class MiterStrategy:
    """Coupe d'onglet par le coin extérieur et le coin intérieur de la boîte commune : chaque
    pièce perd le triangle situé du côté de l'autre, rien n'est ajouté."""

    kind: ClassVar[JointKind] = JointKind.MITER

    def resolve(self, host: PlacedBlock, guest: PlacedBlock, params: MiterParams) -> MiterValues:
        """Angles de coupe et prismes enlevés aux deux pièces."""
        del params  # aucun paramètre en J4
        bridge = _bridge(host, guest)
        corner = _corner(host, bridge.guest)
        angle = math.degrees(math.atan2(corner.guest_width, corner.host_width))
        return MiterValues(
            host_angle=round(angle, ANGLE_DECIMALS),
            guest_angle=round(90.0 - angle, ANGLE_DECIMALS),
            host_cut=_cut(corner, host_side=True),
            guest_cut=bridge.back(moved(_cut(corner, host_side=False), corner.to_host.inverse())),
        )

    def plan(self, host: PlacedBlock, guest: PlacedBlock, params: MiterParams) -> JointPlan:
        """Un prisme triangulaire enlevé à chaque pièce ; l'invitée posée au contact est
        prolongée jusqu'au coin."""
        values = self.resolve(host, guest, params)
        return JointPlan(
            host_cuts=(values.host_cut,),
            guest_cuts=(values.guest_cut,),
            guest_additions=_bridge(host, guest).additions,
        )


def _bridge(host: PlacedBlock, guest: PlacedBlock) -> Bridge:
    """Invitée posée au contact prolongée jusqu'au coin extérieur."""
    return bridged(host, guest, lambda contact: contact.host_depth)


@dataclass(frozen=True)
class _Corner:
    """Coin vu de l'hôte : boîte commune, axes ``s``, ``u``, ``v`` et sens dans lesquels
    l'hôte (selon ``u``) et l'invitée (selon ``v``) se prolongent hors de ``C``."""

    common: Box
    edge: int  # s
    host_axis: int  # u
    host_sign: int
    guest_axis: int  # v
    guest_sign: int
    to_host: RigidTransform

    @property
    def host_width(self) -> float:
        """Largeur de l'hôte dans le plan du coin : étendue de ``C`` selon ``v``."""
        return self.common.size(self.guest_axis)

    @property
    def guest_width(self) -> float:
        """Largeur de l'invitée dans le plan du coin : étendue de ``C`` selon ``u``."""
        return self.common.size(self.host_axis)


def _run(box: Box, common: Box, axis: int) -> int:
    """Sens dans lequel ``box`` dépasse ``common`` selon ``axis`` : 0 (à fleur des deux côtés),
    +1, -1, ou :data:`_BOTH_SIDES`."""
    low = box.lo(axis) < common.lo(axis) - CONTACT_TOLERANCE_MM
    high = box.hi(axis) > common.hi(axis) + CONTACT_TOLERANCE_MM
    if low and high:
        return _BOTH_SIDES
    return 1 if high else -1 if low else 0


def _corner(host: PlacedBlock, guest: PlacedBlock) -> _Corner:
    """Coin d'onglet des deux pièces ; :class:`JointError` sinon (``NOT_SQUARE`` si elles ne
    sont pas d'équerre)."""
    relation = classify(host, guest)
    if not isinstance(relation, Overlap):
        raise JointError(NOT_OVERLAPPING, {})
    to_host = relative_transform(host, guest)
    common = relation.common
    guest_box = moved_box(guest.local_box(), to_host)
    host_runs = [_run(host.local_box(), common, axis) for axis in range(3)]
    guest_runs = [_run(guest_box, common, axis) for axis in range(3)]
    flush = [axis for axis in range(3) if not host_runs[axis] and not guest_runs[axis]]
    if not flush:  # avant les dépassements : une pièce plus épaisse et centrée dépasse des deux
        raise JointError(NOT_FLUSH, {})
    if _BOTH_SIDES in host_runs + guest_runs:
        raise JointError(NOT_SAME_CORNER, {})
    host_axes = [axis for axis in range(3) if host_runs[axis] and not guest_runs[axis]]
    guest_axes = [axis for axis in range(3) if guest_runs[axis] and not host_runs[axis]]
    if len(flush) != 1 or len(host_axes) != 1 or len(guest_axes) != 1:
        raise JointError(NOT_SAME_CORNER, {})
    (u,), (v,) = host_axes, guest_axes
    return _Corner(common, flush[0], u, host_runs[u], v, guest_runs[v], to_host)


def _cut(corner: _Corner, *, host_side: bool) -> Prism:
    """Prisme enlevé à l'hôte (``host_side``) ou à l'invitée, repère de l'hôte.

    Triangle du plan (``u``, ``v``) entre le coin extérieur, le coin intérieur et le coin de
    ``C`` situé du côté de l'autre pièce, extrudé selon ``s``. Il est agrandi de
    :data:`~.geometry.CUT_OVERRUN_MM` au moins hors de la matière, l'hypoténuse restant sur le
    plan de coupe : le volume enlevé dans la pièce ne change pas."""
    common, edge = corner.common, corner.edge
    u, v = corner.host_axis, corner.guest_axis
    outer_u = common.lo(u) if corner.host_sign > 0 else common.hi(u)
    outer_v = common.lo(v) if corner.guest_sign > 0 else common.hi(v)
    margin = CUT_OVERRUN_MM / min(corner.host_width, corner.guest_width)

    def point(a: float, b: float) -> Vec3:
        """Point aux fractions ``a`` de ``C`` selon ``u`` et ``b`` selon ``v``, comptées depuis
        le coin extérieur."""
        position = Vec3(0.0, 0.0, 0.0).with_component(edge, common.lo(edge) - CUT_OVERRUN_MM)
        position = position.with_component(u, outer_u + corner.host_sign * a * corner.guest_width)
        return position.with_component(v, outer_v + corner.guest_sign * b * corner.host_width)

    start, stop = -margin, 1.0 + margin
    apex = point(start, stop) if host_side else point(stop, start)
    extrusion = Vec3(0.0, 0.0, 0.0).with_component(edge, common.size(edge) + 2 * CUT_OVERRUN_MM)
    return Prism((point(start, start), point(stop, stop), apex), extrusion)
