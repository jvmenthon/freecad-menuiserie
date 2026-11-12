# SPDX-License-Identifier: LGPL-2.1-or-later
"""Charnières à cuvette du document : proxy ``HingeJoint``.

Contrat de persistance (ADR 0003) : chemin de ce module, nom de la classe et des propriétés
figés. ``HostPart`` est le côté du caisson (il reçoit les vis de platine), ``GuestPart`` la porte
(elle reçoit les cuvettes).
"""

from __future__ import annotations

from typing import ClassVar, Final

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.joints import JointKind
from freecad.menuiserie.core.joints.hinges import HingeParams
from freecad.menuiserie.features.joints.base import JointFeature
from freecad.menuiserie.features.schema import LENGTH, PropertySpec

__all__ = ["HingeJoint"]

_GROUP: Final = "Charnières"
_DEFAULTS: Final = HingeParams()


class HingeJoint(JointFeature):
    """Charnières à cuvette entre un côté de caisson et une porte."""

    KIND: ClassVar[JointKind] = JointKind.HINGE
    TYPE: ClassVar[str] = "Menuiserie::Hinge"
    OBJECT_NAME: ClassVar[str] = "Hinge"
    LABEL: ClassVar[str] = QT_TRANSLATE_NOOP("Menuiserie", "Charnières")
    PARAMS: ClassVar[type[HingeParams]] = HingeParams
    PROPERTIES: ClassVar[tuple[PropertySpec, ...]] = (
        PropertySpec(
            "Count",
            "App::PropertyIntegerConstraint",
            _GROUP,
            QT_TRANSLATE_NOOP(
                "App::Property",
                "Nombre de charnières. 0 : automatique, 2 jusqu'à 900 mm de hauteur, 3 jusqu'à "
                "1 600 mm, puis 4.",
            ),
            label=QT_TRANSLATE_NOOP("Menuiserie", "Nombre"),
            resolved="count",
            default=(_DEFAULTS.count, 0, 50, 1),
        ),
        PropertySpec(
            "EndDistance",
            LENGTH,
            _GROUP,
            QT_TRANSLATE_NOOP(
                "App::Property",
                "Distance du centre de la première et de la dernière charnière à l'angle de la "
                "porte (100 mm usuels) ; les autres sont réparties régulièrement.",
            ),
            default=_DEFAULTS.end_distance,
            label=QT_TRANSLATE_NOOP("Menuiserie", "Distance aux angles"),
        ),
        PropertySpec(
            "CupDiameter",
            LENGTH,
            _GROUP,
            QT_TRANSLATE_NOOP("App::Property", "Diamètre de la cuvette dans la porte (35 mm)."),
            default=_DEFAULTS.cup_diameter,
            label=QT_TRANSLATE_NOOP("Menuiserie", "Diamètre de la cuvette"),
        ),
        PropertySpec(
            "CupDepth",
            LENGTH,
            _GROUP,
            QT_TRANSLATE_NOOP(
                "App::Property", "Profondeur de la cuvette (11,5 à 13 mm selon la charnière)."
            ),
            default=_DEFAULTS.cup_depth,
            label=QT_TRANSLATE_NOOP("Menuiserie", "Profondeur de la cuvette"),
        ),
        PropertySpec(
            "EdgeDistance",
            LENGTH,
            _GROUP,
            QT_TRANSLATE_NOOP(
                "App::Property",
                "Distance du bord de la cuvette au chant de la porte (3 à 6 mm selon la "
                "charnière).",
            ),
            default=_DEFAULTS.edge_distance,
            label=QT_TRANSLATE_NOOP("Menuiserie", "Distance de la cuvette au chant"),
        ),
        PropertySpec(
            "ScrewPitch",
            LENGTH,
            _GROUP,
            QT_TRANSLATE_NOOP("App::Property", "Entraxe des deux vis de platine (32 mm)."),
            default=_DEFAULTS.screw_pitch,
            label=QT_TRANSLATE_NOOP("Menuiserie", "Entraxe des vis"),
        ),
        PropertySpec(
            "PlateDistance",
            LENGTH,
            _GROUP,
            QT_TRANSLATE_NOOP(
                "App::Property", "Distance des vis de platine au chant avant du côté (37 mm)."
            ),
            default=_DEFAULTS.plate_distance,
            label=QT_TRANSLATE_NOOP("Menuiserie", "Distance des vis au chant avant"),
        ),
        PropertySpec(
            "PilotDiameter",
            LENGTH,
            _GROUP,
            QT_TRANSLATE_NOOP("App::Property", "Diamètre des avant-trous de platine dans le côté."),
            default=_DEFAULTS.pilot_diameter,
            label=QT_TRANSLATE_NOOP("Menuiserie", "Diamètre des avant-trous"),
        ),
        PropertySpec(
            "PilotDepth",
            LENGTH,
            _GROUP,
            QT_TRANSLATE_NOOP("App::Property", "Profondeur des avant-trous de platine."),
            default=_DEFAULTS.pilot_depth,
            label=QT_TRANSLATE_NOOP("Menuiserie", "Profondeur des avant-trous"),
        ),
    )
