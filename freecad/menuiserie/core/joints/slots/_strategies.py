# SPDX-License-Identifier: LGPL-2.1-or-later
"""Stratégies concrètes pour les faux tenons et biscuits.

Ce module contient les implémentations concrètes des stratégies d'assemblage :
- LooseTenonStrategy : Faux tenons (type Domino)
- BiscuitStrategy : Biscuits (type Lamello)
"""

from __future__ import annotations

from typing import ClassVar

from freecad.menuiserie.core.geometry import Prism, Vec3
from freecad.menuiserie.core.joints._base import JointKind
from freecad.menuiserie.core.joints._slot_shapes import half_stadium, rounded_rectangle

from ._base import _SlotStrategy
from ._params import SlotParams, SlotValues, LOOSE_TENON_SIZES, BISCUIT_SIZES
from ._utils import _extent, _point


class LooseTenonStrategy(_SlotStrategy):
    """Faux tenons type Festool Domino : mortaise à bouts demi-ronds, dans la profondeur.

    Le faux tenon a une section en stade (bouts demi-ronds) extrudée dans la profondeur.
    La pièce rapportée traverse de moitié chaque pièce.

    Attributes:
        kind: JointKind.LOOSE_TENON
        sizes: LOOSE_TENON_SIZES (Festool Domino)
        custom_allowed: True (accept les tailles personnalisées)
    """

    kind: ClassVar[JointKind] = JointKind.LOOSE_TENON
    sizes: ClassVar[tuple] = LOOSE_TENON_SIZES
    custom_allowed: ClassVar[bool] = True

    def _solid(
        self, frame: "ContactFrame", values: SlotValues, position: float, role: str
    ) -> Prism:
        """Crée une mortaise ou un faux tenon.

        La section est un rectangle arrondi (stade) dans le plan (largeur, épaisseur),
        extrudé à travers le joint.

        Args:
            frame: Le cadre de contact
            values: Les valeurs calculées
            position: Position le long du contact
            role: Rôle ('host', 'guest' ou 'insert')

        Returns:
            Prism: Le solide créé
        """
        base, direction, length = _extent(frame, values, role)
        rectangle = frame.contact.rectangle

        # Centre de la mortaise/faux tenon
        center = (
            rectangle.lo(frame.width_axis) + position,
            rectangle.center(frame.thickness_axis) + values.thickness_offset,
        )

        # Contour de la section : rectangle arrondi
        outline = rounded_rectangle(values.along, values.thickness, values.thickness / 2)

        # Points de la section dans le repère de l'invitée
        points = tuple(
            _point(frame, center[0] + u, center[1] + v, base)
            for u, v in outline
        )

        # Extrusion selon la normale
        extrusion = Vec3(0.0, 0.0, 0.0).with_component(frame.normal, direction * length)

        return Prism(points, extrusion)


class BiscuitStrategy(_SlotStrategy):
    """Biscuits type Lamello : stade dans le plan du joint, de l'épaisseur de la fente.

    Le biscuit est un stade dans le plan du joint, de l'épaisseur de la fente.
    La pièce rapportée traverse de moitié chaque pièce.

    Attributes:
        kind: JointKind.BISCUIT
        sizes: BISCUIT_SIZES (lamelles Lamello)
        custom_allowed: False (pas de tailles personnalisées)
    """

    kind: ClassVar[JointKind] = JointKind.BISCUIT
    sizes: ClassVar[tuple] = BISCUIT_SIZES
    custom_allowed: ClassVar[bool] = False

    def _solid(
        self, frame: "ContactFrame", values: SlotValues, position: float, role: str
    ) -> Prism:
        """Crée une fente ou un biscuit.

        La section est un stade (la lamelle) ou un demi-stade (la fente d'une pièce)
        dans le plan (largeur, normale), extrudé sur l'épaisseur de la fente.

        Args:
            frame: Le cadre de contact
            values: Les valeurs calculées
            position: Position le long du contact
            role: Rôle ('host', 'guest' ou 'insert')

        Returns:
            Prism: Le solide créé
        """
        base, direction, length = _extent(frame, values, role)
        rectangle = frame.contact.rectangle

        along = rectangle.lo(frame.width_axis) + position
        thick = (
            rectangle.center(frame.thickness_axis)
            + values.thickness_offset
            - values.thickness / 2
        )

        if role == "insert":
            # Biscuit complet : stade dans le plan
            outline = rounded_rectangle(values.along, length, length / 2)
            centre = base + direction * length / 2
        else:
            # Fente : demi-stade
            outline = half_stadium(values.along, length)
            centre = base

        points = []
        for u, v in outline:
            normal = centre + (v if role == "insert" else direction * v)
            points.append(_point(frame, along + u, thick, normal))

        # Extrusion selon l'épaisseur
        extrusion = Vec3(0.0, 0.0, 0.0).with_component(frame.thickness_axis, values.thickness)

        return Prism(tuple(points), extrusion)
