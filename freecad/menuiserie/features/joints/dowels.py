# SPDX-License-Identifier: LGPL-2.1-or-later
"""Assemblage par tourillons du document : proxy ``DowelJoint``.

Contrat de persistance (ADR 0003) : chemin de ce module, nom de la classe et noms des propriétés
figés. La forme de l'assemblage est l'ensemble des tourillons ; les deux pièces sont percées.
Les cotes et le nombre valent 0 pour « automatique » (:mod:`core.joints.dowels`).
"""

from __future__ import annotations

from typing import ClassVar, Final

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.joints import JointKind
from freecad.menuiserie.core.joints.dowels import MAX_DOWEL_COUNT, DowelParams
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.joints.base import JointFeature, params_from
from freecad.menuiserie.features.schema import DISTANCE, LENGTH, PropertySpec

__all__ = ["DowelJoint"]

_GROUP: Final = "Tourillons"
_DEFAULTS: Final = DowelParams()


class DowelJoint(JointFeature):
    """Tourillons percés dans les deux pièces à travers leur contact."""

    KIND: ClassVar[JointKind] = JointKind.DOWELS
    TYPE: ClassVar[str] = "Menuiserie::Dowels"
    OBJECT_NAME: ClassVar[str] = "Dowels"
    LABEL: ClassVar[str] = QT_TRANSLATE_NOOP("Menuiserie", "Tourillons")
    PROPERTIES: ClassVar[tuple[PropertySpec, ...]] = (
        PropertySpec(
            "Diameter",
            LENGTH,
            _GROUP,
            QT_TRANSLATE_NOOP(
                "App::Property",
                "Diamètre des tourillons. 0 : automatique, 6, 8, 10 ou 12 mm sans dépasser la "
                "moitié de l'épaisseur au contact.",
            ),
            default=_DEFAULTS.diameter,
        ),
        PropertySpec(
            "DowelLength",
            LENGTH,
            _GROUP,
            QT_TRANSLATE_NOOP(
                "App::Property",
                "Longueur des tourillons. 0 : automatique, selon le diamètre (30, 35, 40 ou "
                "50 mm).",
            ),
            default=_DEFAULTS.dowel_length,
        ),
        PropertySpec(
            "HostDepth",
            LENGTH,
            _GROUP,
            QT_TRANSLATE_NOOP(
                "App::Property",
                "Profondeur des tourillons dans la pièce hôte. 0 : automatique, la moitié de "
                "leur longueur.",
            ),
            default=_DEFAULTS.host_depth,
        ),
        PropertySpec(
            "Count",
            "App::PropertyIntegerConstraint",
            _GROUP,
            QT_TRANSLATE_NOOP(
                "App::Property",
                "Nombre de tourillons. 0 : automatique, selon la longueur du contact (entraxe "
                "de 128 mm au plus).",
            ),
            default=(_DEFAULTS.count, 0, MAX_DOWEL_COUNT, 1),
        ),
        PropertySpec(
            "EdgeDistance",
            LENGTH,
            _GROUP,
            QT_TRANSLATE_NOOP(
                "App::Property",
                "Distance du bord du contact à l'axe du premier et du dernier tourillon. 0 : "
                "automatique, deux fois le diamètre.",
            ),
            default=_DEFAULTS.edge_distance,
        ),
        PropertySpec(
            "ThicknessOffset",
            DISTANCE,
            _GROUP,
            QT_TRANSLATE_NOOP(
                "App::Property",
                "Décalage des tourillons dans l'épaisseur de la pièce, depuis le milieu. "
                "0 : centrés.",
            ),
            default=_DEFAULTS.thickness_offset,
        ),
        PropertySpec(
            "HoleClearance",
            LENGTH,
            _GROUP,
            QT_TRANSLATE_NOOP(
                "App::Property",
                "Jeu de fond : profondeur de chaque perçage au-delà du bout du tourillon.",
            ),
            default=_DEFAULTS.hole_clearance,
        ),
    )

    def params(self, obj: DocumentObject) -> DowelParams:
        """Paramètres des tourillons lus dans les propriétés de ``obj``."""
        return params_from(obj, DowelParams)
