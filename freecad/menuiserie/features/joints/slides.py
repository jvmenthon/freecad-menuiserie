# SPDX-License-Identifier: LGPL-2.1-or-later
"""Coulisses de tiroir du document : proxy ``DrawerSlideJoint``.

Contrat de persistance (ADR 0003) : chemin de ce module, nom de la classe et des propriétés
figés. ``HostPart`` est le côté du caisson, ``GuestPart`` le côté du tiroir : ils se font face avec
un jeu que la coulisse (pièce rapportée) occupe, et reçoivent chacun des avant-trous.
"""

from __future__ import annotations

from typing import ClassVar, Final

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.joints import JointKind
from freecad.menuiserie.core.joints.slides import SlideParams
from freecad.menuiserie.features.joints.base import JointFeature
from freecad.menuiserie.features.schema import DISTANCE, LENGTH, PropertySpec

__all__ = ["DrawerSlideJoint"]

_GROUP: Final = "Coulisse"
_DEFAULTS: Final = SlideParams()


class DrawerSlideJoint(JointFeature):
    """Coulisse à billes entre un côté de caisson et un côté de tiroir."""

    KIND: ClassVar[JointKind] = JointKind.DRAWER_SLIDE
    TYPE: ClassVar[str] = "Menuiserie::DrawerSlide"
    OBJECT_NAME: ClassVar[str] = "DrawerSlide"
    LABEL: ClassVar[str] = QT_TRANSLATE_NOOP("Menuiserie", "Coulisse")
    PARAMS: ClassVar[type[SlideParams]] = SlideParams
    PROPERTIES: ClassVar[tuple[PropertySpec, ...]] = (
        PropertySpec(
            "Length",
            LENGTH,
            _GROUP,
            QT_TRANSLATE_NOOP(
                "App::Property",
                "Longueur de la coulisse. 0 : automatique, la plus longue taille du commerce "
                "(250 à 600 mm) qui tient dans le recouvrement des côtés.",
            ),
            default=_DEFAULTS.length,
            label=QT_TRANSLATE_NOOP("Menuiserie", "Longueur"),
            resolved="length",
        ),
        PropertySpec(
            "HeightOffset",
            DISTANCE,
            _GROUP,
            QT_TRANSLATE_NOOP(
                "App::Property",
                "Décalage de la coulisse en hauteur, depuis le milieu du recouvrement.",
            ),
            default=_DEFAULTS.height_offset,
            label=QT_TRANSLATE_NOOP("Menuiserie", "Décalage en hauteur"),
        ),
        PropertySpec(
            "FrontSetback",
            LENGTH,
            _GROUP,
            QT_TRANSLATE_NOOP(
                "App::Property",
                "Retrait de la coulisse depuis l'avant des côtés (ou l'arrière si inversé).",
            ),
            default=_DEFAULTS.front_setback,
            label=QT_TRANSLATE_NOOP("Menuiserie", "Retrait à l'avant"),
        ),
        PropertySpec(
            "Reversed",
            "App::PropertyBool",
            _GROUP,
            QT_TRANSLATE_NOOP(
                "App::Property",
                "L'avant est le bout opposé : la coulisse et ses trous sont comptés depuis l'autre "
                "extrémité des côtés.",
            ),
            default=_DEFAULTS.reversed,
            label=QT_TRANSLATE_NOOP("Menuiserie", "Avant inversé"),
        ),
        PropertySpec(
            "Thickness",
            LENGTH,
            _GROUP,
            QT_TRANSLATE_NOOP(
                "App::Property", "Épaisseur de la coulisse (12,7 mm pour une coulisse à billes)."
            ),
            default=_DEFAULTS.thickness,
            label=QT_TRANSLATE_NOOP("Menuiserie", "Épaisseur"),
        ),
        PropertySpec(
            "SlideHeight",
            LENGTH,
            _GROUP,
            QT_TRANSLATE_NOOP("App::Property", "Hauteur de la coulisse (45 mm usuels)."),
            default=_DEFAULTS.slide_height,
            label=QT_TRANSLATE_NOOP("Menuiserie", "Hauteur"),
        ),
        PropertySpec(
            "HoleCount",
            "App::PropertyIntegerConstraint",
            _GROUP,
            QT_TRANSLATE_NOOP(
                "App::Property",
                "Nombre de trous de fixation par côté, au pas de 32 mm (le premier à 37 mm de "
                "l'avant). 0 : automatique (3).",
            ),
            label=QT_TRANSLATE_NOOP("Menuiserie", "Nombre de trous"),
            resolved="hole_count",
            default=(_DEFAULTS.hole_count, 0, 50, 1),
        ),
        PropertySpec(
            "HoleDiameter",
            LENGTH,
            _GROUP,
            QT_TRANSLATE_NOOP(
                "App::Property", "Diamètre des trous du côté du caisson (5 mm, système 32)."
            ),
            default=_DEFAULTS.hole_diameter,
            label=QT_TRANSLATE_NOOP("Menuiserie", "Diamètre des trous"),
        ),
        PropertySpec(
            "HoleDepth",
            LENGTH,
            _GROUP,
            QT_TRANSLATE_NOOP("App::Property", "Profondeur des trous du côté du caisson."),
            default=_DEFAULTS.hole_depth,
            label=QT_TRANSLATE_NOOP("Menuiserie", "Profondeur des trous"),
        ),
    )
