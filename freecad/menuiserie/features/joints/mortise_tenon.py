# SPDX-License-Identifier: LGPL-2.1-or-later
"""Assemblage tenon-mortaise du document : proxy ``MortiseTenonJoint``.

Contrat de persistance (ADR 0003) : chemin de ce module, nom de la classe et noms des propriétés
figés. Les cotes valent 0 pour « automatique » (proportions de menuisier, :mod:`core.joints`).
"""

from __future__ import annotations

from typing import ClassVar, Final

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.joints import JointKind
from freecad.menuiserie.core.joints.mortise_tenon import MortiseTenonParams
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.joints.base import JointFeature, params_from
from freecad.menuiserie.features.schema import PropertySpec

__all__ = ["MortiseTenonJoint"]

_LENGTH: Final = "App::PropertyLength"
_DISTANCE: Final = "App::PropertyDistance"
_DEFAULTS: Final = MortiseTenonParams()


class MortiseTenonJoint(JointFeature):
    """Tenon ajouté au bout de la pièce invitée, mortaise enlevée dans la pièce hôte."""

    KIND: ClassVar[JointKind] = JointKind.MORTISE_TENON
    TYPE: ClassVar[str] = "Menuiserie::MortiseTenon"
    OBJECT_NAME: ClassVar[str] = "MortiseTenon"
    LABEL: ClassVar[str] = QT_TRANSLATE_NOOP("Menuiserie", "Tenon-mortaise")
    PROPERTIES: ClassVar[tuple[PropertySpec, ...]] = (
        PropertySpec(
            "TenonThickness",
            _LENGTH,
            "Tenon",
            QT_TRANSLATE_NOOP(
                "App::Property",
                "Épaisseur du tenon. 0 : automatique, un tiers de l'épaisseur de la pièce à "
                "tenon arrondi au mm.",
            ),
            default=_DEFAULTS.tenon_thickness,
        ),
        PropertySpec(
            "TenonWidth",
            _LENGTH,
            "Tenon",
            QT_TRANSLATE_NOOP(
                "App::Property",
                "Largeur du tenon. 0 : automatique, largeur de la pièce moins deux épaulements "
                "d'un sixième.",
            ),
            default=_DEFAULTS.tenon_width,
        ),
        PropertySpec(
            "TenonLength",
            _LENGTH,
            "Tenon",
            QT_TRANSLATE_NOOP(
                "App::Property",
                "Longueur du tenon, ajoutée au bout de la pièce. 0 : automatique, deux tiers de "
                "la profondeur de la pièce mortaisée.",
            ),
            default=_DEFAULTS.tenon_length,
        ),
        PropertySpec(
            "WidthOffset",
            _DISTANCE,
            "Tenon",
            QT_TRANSLATE_NOOP(
                "App::Property",
                "Décalage du tenon dans la largeur de la pièce, depuis le milieu. 0 : centré.",
            ),
            default=_DEFAULTS.width_offset,
        ),
        PropertySpec(
            "ThicknessOffset",
            _DISTANCE,
            "Tenon",
            QT_TRANSLATE_NOOP(
                "App::Property",
                "Décalage du tenon dans l'épaisseur de la pièce, depuis le milieu. 0 : centré.",
            ),
            default=_DEFAULTS.thickness_offset,
        ),
        PropertySpec(
            "Through",
            "App::PropertyBool",
            "Tenon",
            QT_TRANSLATE_NOOP(
                "App::Property",
                "Tenon traversant : la mortaise débouche de l'autre côté de la pièce.",
            ),
            default=_DEFAULTS.through,
        ),
        PropertySpec(
            "MortiseClearance",
            _LENGTH,
            "Mortaise",
            QT_TRANSLATE_NOOP(
                "App::Property",
                "Jeu de fond : profondeur de la mortaise au-delà du bout du tenon.",
            ),
            default=_DEFAULTS.mortise_clearance,
        ),
    )

    def params(self, obj: DocumentObject) -> MortiseTenonParams:
        """Paramètres du tenon-mortaise lus dans les propriétés de ``obj``."""
        return params_from(obj, MortiseTenonParams)
