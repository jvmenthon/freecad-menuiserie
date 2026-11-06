# SPDX-License-Identifier: LGPL-2.1-or-later
"""Pieds de caisson du document : proxy ``FootJoint``.

Contrat de persistance (ADR 0003) : chemin de ce module, nom de la classe et des propriétés
figés. Les pieds se posent sous **un seul** panneau : ``HostPart`` et ``GuestPart`` sont la même
pièce (le panneau est percé, l'embase et la tige sont les pièces rapportées de la forme).
"""

from __future__ import annotations

from typing import ClassVar, Final

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.joints import JointKind
from freecad.menuiserie.core.joints.dowels import MAX_DOWEL_COUNT
from freecad.menuiserie.core.joints.feet import FootParams
from freecad.menuiserie.features.joints.base import JointFeature
from freecad.menuiserie.features.schema import LENGTH, PropertySpec

__all__ = ["FootJoint"]

_GROUP: Final = "Pieds"
_DEFAULTS: Final = FootParams()


class FootJoint(JointFeature):
    """Pieds réglables : grille de perçages sous un panneau, embases rapportées."""

    KIND: ClassVar[JointKind] = JointKind.FOOT
    TYPE: ClassVar[str] = "Menuiserie::Foot"
    OBJECT_NAME: ClassVar[str] = "Foot"
    LABEL: ClassVar[str] = QT_TRANSLATE_NOOP("Menuiserie", "Pieds")
    PARAMS: ClassVar[type[FootParams]] = FootParams
    INVERTIBLE: ClassVar[bool] = False  # une seule pièce
    PROPERTIES: ClassVar[tuple[PropertySpec, ...]] = (
        PropertySpec(
            "StemDiameter",
            LENGTH,
            _GROUP,
            QT_TRANSLATE_NOOP(
                "App::Property",
                "Diamètre de la tige filetée du pied (M10 : 10 mm), percé dans le panneau.",
            ),
            default=_DEFAULTS.stem_diameter,
            label=QT_TRANSLATE_NOOP("Menuiserie", "Diamètre de la tige"),
            resolved="stem_diameter",
        ),
        PropertySpec(
            "BaseDiameter",
            LENGTH,
            _GROUP,
            QT_TRANSLATE_NOOP("App::Property", "Diamètre de l'embase du pied, sous le panneau."),
            default=_DEFAULTS.base_diameter,
            label=QT_TRANSLATE_NOOP("Menuiserie", "Diamètre de l'embase"),
            resolved="base_diameter",
        ),
        PropertySpec(
            "Height",
            LENGTH,
            _GROUP,
            QT_TRANSLATE_NOOP("App::Property", "Hauteur visible du pied sous le panneau."),
            default=_DEFAULTS.height,
            label=QT_TRANSLATE_NOOP("Menuiserie", "Hauteur du pied"),
            resolved="height",
        ),
        PropertySpec(
            "HoleDepth",
            LENGTH,
            _GROUP,
            QT_TRANSLATE_NOOP(
                "App::Property", "Profondeur du logement de la tige dans le panneau."
            ),
            default=_DEFAULTS.hole_depth,
            label=QT_TRANSLATE_NOOP("Menuiserie", "Profondeur du logement"),
            resolved="hole_depth",
        ),
        PropertySpec(
            "Columns",
            "App::PropertyIntegerConstraint",
            _GROUP,
            QT_TRANSLATE_NOOP(
                "App::Property", "Nombre de pieds le long de la longueur du panneau."
            ),
            label=QT_TRANSLATE_NOOP("Menuiserie", "Pieds en longueur"),
            resolved="columns",
            default=(_DEFAULTS.columns, 1, MAX_DOWEL_COUNT, 1),
        ),
        PropertySpec(
            "Rows",
            "App::PropertyIntegerConstraint",
            _GROUP,
            QT_TRANSLATE_NOOP("App::Property", "Nombre de pieds le long de la largeur du panneau."),
            label=QT_TRANSLATE_NOOP("Menuiserie", "Pieds en largeur"),
            resolved="rows",
            default=(_DEFAULTS.rows, 1, MAX_DOWEL_COUNT, 1),
        ),
        PropertySpec(
            "EdgeDistance",
            LENGTH,
            _GROUP,
            QT_TRANSLATE_NOOP(
                "App::Property",
                "Distance des pieds extérieurs au bord du panneau. 0 : automatique (50 mm).",
            ),
            label=QT_TRANSLATE_NOOP("Menuiserie", "Distance au bord"),
            resolved="edge_distance",
            default=_DEFAULTS.edge_distance,
        ),
    )
