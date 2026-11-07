# SPDX-License-Identifier: LGPL-2.1-or-later
"""Stratégie d'assemblage pour les coulisses de tiroir.

Ce module contient la classe SlideStrategy qui implémente la logique
principale des coulisses de tiroir à billes.
"""

from __future__ import annotations

from typing import ClassVar

from freecad.menuiserie.core.geometry import (
    Axis,
    Cylinder,
    JointError,
    PlacedBlock,
    moved,
)
from freecad.menuiserie.core.joints._base import JointKind, JointPlan

from ._params import SlideParams, SlideValues
from ._layout import _frame, _values
from ._drilling import _holes, _along, _depth, _body


class SlideStrategy:
    """Coulisse à billes posée face à face avec un jeu.

    Contrairement aux assemblages de chant ou de bout, les deux pièces sont séparées
    par un jeu (la coulisse l'occupe) : le côté du caisson (host) et celui du tiroir
    (guest) se font face.

    Attributes:
        kind: JointKind.DRAWER_SLIDE
    """

    kind: ClassVar[JointKind] = JointKind.DRAWER_SLIDE

    def resolve(self, host: PlacedBlock, guest: PlacedBlock, params: SlideParams) -> SlideValues:
        """Calcule les valeurs effectives : longueur, jeu et position des trous.

        Args:
            host: Le côté du caisson
            guest: Le côté du tiroir
            params: Les paramètres de la coulisse

        Returns:
            SlideValues: Les valeurs calculées (longueur, jeu, positions des trous, etc.)
        """
        return _values(_frame(host, guest), params)

    def plan(self, host: PlacedBlock, guest: PlacedBlock, params: SlideParams) -> JointPlan:
        """Génère le plan d'usinage : avant-trous des deux côtés et coulisse rapportée.

        Args:
            host: Le côté du caisson
            guest: Le côté du tiroir
            params: Les paramètres de la coulisse

        Returns:
            JointPlan: Le plan contenant les avant-trous (host_cuts, guest_cuts) et
            la coulisse (inserts), exprimé dans le repère de l'hôte.
        """
        frame = _frame(host, guest)
        values = _values(frame, params)

        host_cuts, guest_cuts = [], []
        host_depth = _depth(host.local_box().size(frame.normal), params.hole_depth)

        for hole in values.hole_positions:
            center = _along(frame, params, hole)

            # Trou dans l'hôte (côté du caisson)
            host_cuts.append(
                Cylinder(
                    center.with_component(frame.normal, frame.host_plane),
                    Axis.of(frame.normal, -frame.sign),
                    params.hole_diameter / 2,
                    host_depth,
                )
            )

            # Avant-trou dans l'invité (côté du tiroir) - vis de fixation
            from freecad.menuiserie.core.joints.slides._params import (
                GUEST_PILOT_MM,
                GUEST_PILOT_DEPTH_MM,
            )

            pilot = Cylinder(
                center.with_component(frame.normal, frame.guest_plane),
                Axis.of(frame.normal, frame.sign),
                GUEST_PILOT_MM / 2,
                _depth(frame.guest_extent, GUEST_PILOT_DEPTH_MM),
            )
            guest_cuts.append(moved(pilot, frame.to_guest))

        return JointPlan(
            host_cuts=tuple(host_cuts),
            guest_cuts=tuple(guest_cuts),
            inserts=(_body(frame, params, values),),
        )
