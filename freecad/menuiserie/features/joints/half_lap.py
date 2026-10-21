# SPDX-License-Identifier: LGPL-2.1-or-later
"""Assemblage à mi-bois du document : proxy ``HalfLapJoint``.

Contrat de persistance (ADR 0003) : chemin de ce module, nom de la classe et noms des propriétés
figés. Les deux pièces se chevauchent à leur place : chacune est entaillée dans leur boîte
commune. La profondeur vaut 0 pour « automatique » (moitié de l'épaisseur, :mod:`core.joints`).
"""

from __future__ import annotations

from typing import ClassVar, Final

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.joints import JointKind
from freecad.menuiserie.core.joints.half_lap import HalfLapParams
from freecad.menuiserie.features.joints.base import JointFeature
from freecad.menuiserie.features.schema import LENGTH, PropertySpec

__all__ = ["HalfLapJoint"]

_DEFAULTS: Final = HalfLapParams()


class HalfLapJoint(JointFeature):
    """Entaille de la pièce hôte par-dessus, de la pièce invitée par-dessous (ou l'inverse)."""

    KIND: ClassVar[JointKind] = JointKind.HALF_LAP
    TYPE: ClassVar[str] = "Menuiserie::HalfLap"
    OBJECT_NAME: ClassVar[str] = "HalfLap"
    LABEL: ClassVar[str] = QT_TRANSLATE_NOOP("Menuiserie", "Mi-bois")
    PARAMS: ClassVar[type[HalfLapParams]] = HalfLapParams
    PROPERTIES: ClassVar[tuple[PropertySpec, ...]] = (
        PropertySpec(
            "Depth",
            LENGTH,
            "Mi-bois",
            QT_TRANSLATE_NOOP(
                "App::Property",
                "Profondeur de l'entaille de la pièce hôte ; 0 = moitié de l'épaisseur.",
            ),
            default=_DEFAULTS.depth,
            label=QT_TRANSLATE_NOOP("Menuiserie", "Profondeur de l'entaille"),
            resolved="depth",
        ),
        PropertySpec(
            "FlipSide",
            "App::PropertyBool",
            "Mi-bois",
            QT_TRANSLATE_NOOP("App::Property", "Entaille de l'hôte par-dessous."),
            default=_DEFAULTS.flip_side,
            label=QT_TRANSLATE_NOOP("Menuiserie", "Entaille de l'hôte par-dessous"),
        ),
    )
