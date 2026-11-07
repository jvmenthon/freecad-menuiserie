# SPDX-License-Identifier: LGPL-2.1-or-later
"""Stratégie d'assemblage pour le perçage LR32 et taquets de tablette.

Ce module contient la classe ShelfPinsStrategy qui implémente la logique
principale du perçage LR32.
"""

from __future__ import annotations

from typing import ClassVar

from freecad.menuiserie.core.geometry import PlacedBlock
from freecad.menuiserie.core.joints._base import JointKind, JointPlan

from ._params import ShelfPinsParams, ShelfPinsValues
from ._layout import _checked, _opposite
from ._drilling import _drilling


class ShelfPinsStrategy:
    """Perçage LR32 : deux colonnes de trous dans un côté, taquets rapportés.

    Cette stratégie gère la création de trous de perçage LR32 (5mm de diamètre,
    pas de 32mm) et l'insertion de taquets de tablette dans un côté de caisson.

    Le perçage ne relie pas deux pièces : la pièce guest est la même que host
    (le côté de caisson debout). Optionnellement, le montant opposé peut être
    percé en miroir.
    """

    kind: ClassVar[JointKind] = JointKind.SHELF_PINS

    def resolve(
        self, host: PlacedBlock, guest: PlacedBlock, params: ShelfPinsParams
    ) -> ShelfPinsValues:
        """Calcule les valeurs effectives du perçage pour le côté ``host``.

        Args:
            host: Le côté principal à percer (côté de caisson debout)
            guest: Le montant opposé (peut être le même que host)
            params: Les paramètres du perçage

        Returns:
            ShelfPinsValues: Les valeurs calculées (rangs, hauteurs, taquets, etc.)
            avec le nombre de trous et taquets du montant opposé si percé.
        """
        values = _checked(host, params)[0]
        opposite = _opposite(host, guest, params, values)
        if opposite is None:
            return values
        other = opposite[0]
        return values.__class__(
            hole_diameter=values.hole_diameter,
            hole_depth=values.hole_depth,
            pitch=values.pitch,
            edge_distance=values.edge_distance,
            end_margin=values.end_margin,
            rows=values.rows,
            pin_row=values.pin_row,
            pin_projection=values.pin_projection,
            with_pins=values.with_pins,
            pin_rows=values.pin_rows,
            heights=values.heights,
            face=values.face,
            zone_height=values.zone_height,
            zone=values.zone,
            opposite_pins=other.count,
            opposite_holes=other.hole_count,
        )

    def plan(self, host: PlacedBlock, guest: PlacedBlock, params: ShelfPinsParams) -> JointPlan:
        """Génère le plan de perçage avec trous et taquets.

        Args:
            host: Le côté principal à percer
            guest: Le montant opposé
            params: Les paramètres du perçage

        Returns:
            JointPlan: Le plan contenant les trous (host_cuts), les trous du montant
            opposé (guest_cuts), et les taquets (inserts).
        """
        from freecad.menuiserie.core.geometry import relative_transform
        from freecad.menuiserie.core.joints._shelf_layout import moved_axis

        def _moved_cylinder(pin, transform):
            """Applique une transformation à un cylindre (taquet du montant opposé)."""
            from freecad.menuiserie.core.geometry import Cylinder
            axis = moved_axis(transform, pin.axis)
            return Cylinder(transform.apply(pin.base), axis, pin.radius, pin.height)

        values, layout = _checked(host, params)
        holes, pins = _drilling(host, values, layout)
        opposite = _opposite(host, guest, params, values)
        if opposite is None:
            return JointPlan(host_cuts=holes, inserts=pins)
        guest_holes, guest_pins = _drilling(guest, *opposite)
        transform = relative_transform(host, guest)
        moved = tuple(_moved_cylinder(solid, transform) for solid in guest_pins)
        return JointPlan(host_cuts=holes, guest_cuts=guest_holes, inserts=(*pins, *moved))
