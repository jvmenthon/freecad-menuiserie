# SPDX-License-Identifier: LGPL-2.1-or-later
"""Assemblage rainure-languette du document : proxy ``TongueGrooveJoint``.

Contrat de persistance (ADR 0003) : chemin de ce module, nom de la classe et noms des propriétés
figés. L'épaisseur de la languette vaut 0 pour « automatique » (un tiers, :mod:`core.joints`).
"""

from __future__ import annotations

from typing import ClassVar, Final

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.joints import JointKind
from freecad.menuiserie.core.joints.tongue_groove import TongueGrooveParams
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.joints.base import JointFeature, params_from
from freecad.menuiserie.features.schema import PropertySpec

__all__ = ["TongueGrooveJoint"]

_LENGTH: Final = "App::PropertyLength"
_DEFAULTS: Final = TongueGrooveParams()


class TongueGrooveJoint(JointFeature):
    """Languette ajoutée au chant ou au bout de la pièce invitée, rainure dans la pièce hôte."""

    KIND: ClassVar[JointKind] = JointKind.TONGUE_GROOVE
    TYPE: ClassVar[str] = "Menuiserie::TongueGroove"
    OBJECT_NAME: ClassVar[str] = "TongueGroove"
    LABEL: ClassVar[str] = QT_TRANSLATE_NOOP("Menuiserie", "Rainure-languette")
    PROPERTIES: ClassVar[tuple[PropertySpec, ...]] = (
        PropertySpec(
            "TongueThickness",
            _LENGTH,
            "Languette",
            QT_TRANSLATE_NOOP(
                "App::Property",
                "Épaisseur de la languette. 0 : automatique, un tiers de l'épaisseur de la "
                "pièce à languette arrondi au mm.",
            ),
            default=_DEFAULTS.tongue_thickness,
        ),
        PropertySpec(
            "TongueLength",
            _LENGTH,
            "Languette",
            QT_TRANSLATE_NOOP(
                "App::Property",
                "Longueur de la languette, ajoutée au chant ou au bout de la pièce. 0 : 10 mm.",
            ),
            default=_DEFAULTS.tongue_length,
        ),
        PropertySpec(
            "ThicknessOffset",
            "App::PropertyDistance",
            "Languette",
            QT_TRANSLATE_NOOP(
                "App::Property",
                "Décalage de la languette dans l'épaisseur de la pièce, depuis le milieu. "
                "0 : centrée.",
            ),
            default=_DEFAULTS.thickness_offset,
        ),
        PropertySpec(
            "GrooveClearance",
            _LENGTH,
            "Rainure",
            QT_TRANSLATE_NOOP(
                "App::Property",
                "Jeu de fond : profondeur de la rainure au-delà du bout de la languette.",
            ),
            default=_DEFAULTS.groove_clearance,
        ),
        PropertySpec(
            "ThroughGroove",
            "App::PropertyBool",
            "Rainure",
            QT_TRANSLATE_NOOP(
                "App::Property",
                "Rainure filante : prolongée sur toute l'étendue de la pièce qui la reçoit, le "
                "long du contact.",
            ),
            default=_DEFAULTS.through_groove,
        ),
    )

    def params(self, obj: DocumentObject) -> TongueGrooveParams:
        """Paramètres de la rainure-languette lus dans les propriétés de ``obj``."""
        return params_from(obj, TongueGrooveParams)
