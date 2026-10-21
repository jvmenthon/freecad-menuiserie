# SPDX-License-Identifier: LGPL-2.1-or-later
"""Assemblage d'onglet du document : proxy ``MiterJoint``.

Contrat de persistance (ADR 0003) : chemin de ce module et nom de la classe figés. Les deux
pièces sont dessinées à leur longueur hors tout et se chevauchent au coin ; chacune perd le
prisme triangulaire de leur boîte commune situé du côté de l'autre (:mod:`core.joints.miter`).
Aucune propriété propre en J4 : un renfort (Q8) ajoutera une propriété et ``Version`` = 2.
"""

from __future__ import annotations

from typing import ClassVar

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.joints import JointKind
from freecad.menuiserie.core.joints.miter import MiterParams
from freecad.menuiserie.features.joints.base import JointFeature
from freecad.menuiserie.features.schema import PropertySpec

__all__ = ["MiterJoint"]


class MiterJoint(JointFeature):
    """Coupe d'onglet des deux pièces, du coin extérieur au coin intérieur."""

    KIND: ClassVar[JointKind] = JointKind.MITER
    TYPE: ClassVar[str] = "Menuiserie::Miter"
    OBJECT_NAME: ClassVar[str] = "Miter"
    LABEL: ClassVar[str] = QT_TRANSLATE_NOOP("Menuiserie", "Onglet")
    PARAMS: ClassVar[type[MiterParams]] = MiterParams
    PROPERTIES: ClassVar[tuple[PropertySpec, ...]] = ()
    SUMMARY: ClassVar[str] = QT_TRANSLATE_NOOP(
        "Menuiserie",
        "Angles de coupe : {host_angle}° pour la pièce hôte, {guest_angle}° pour la pièce "
        "invitée (depuis une coupe d'équerre).",
    )
