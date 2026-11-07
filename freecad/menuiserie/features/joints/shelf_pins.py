# SPDX-License-Identifier: LGPL-2.1-or-later
"""Perçage LR32 du document : proxy ``ShelfPinsJoint``.

Contrat de persistance (ADR 0003) : chemin de ce module, nom de la classe et des propriétés
figés. Le perçage concerne **un seul** côté debout : ``HostPart`` et ``GuestPart`` sont la même
pièce (le côté est percé, les taquets sont les pièces rapportées de la forme).
"""

from __future__ import annotations

from typing import ClassVar, Final

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.joints import JointKind
from freecad.menuiserie.core.joints.shelf_pins import ShelfPinsParams
from freecad.menuiserie.features.joints.base import JointFeature
from freecad.menuiserie.features.schema import LENGTH, PropertySpec

__all__ = ["ShelfPinsJoint"]

_GROUP: Final = "Perçage LR32"
_DEFAULTS: Final = ShelfPinsParams()
_MAX_ROWS: Final = 50


class ShelfPinsJoint(JointFeature):
    """Perçage au pas de 32 mm dans un côté debout, taquets de tablette rapportés."""

    KIND: ClassVar[JointKind] = JointKind.SHELF_PINS
    TYPE: ClassVar[str] = "Menuiserie::ShelfPins"
    OBJECT_NAME: ClassVar[str] = "ShelfPins"
    LABEL: ClassVar[str] = QT_TRANSLATE_NOOP("Menuiserie", "Perçage LR32")
    PARAMS: ClassVar[type[ShelfPinsParams]] = ShelfPinsParams
    INVERTIBLE: ClassVar[bool] = False  # une seule pièce
    PROPERTIES: ClassVar[tuple[PropertySpec, ...]] = (
        PropertySpec(
            "HoleDiameter",
            LENGTH,
            _GROUP,
            QT_TRANSLATE_NOOP("App::Property", "Diamètre des trous (taquets à tige : 5 mm)."),
            default=_DEFAULTS.hole_diameter,
            label=QT_TRANSLATE_NOOP("Menuiserie", "Diamètre des trous"),
            resolved="hole_diameter",
        ),
        PropertySpec(
            "HoleDepth",
            LENGTH,
            _GROUP,
            QT_TRANSLATE_NOOP("App::Property", "Profondeur des trous dans le côté."),
            default=_DEFAULTS.hole_depth,
            label=QT_TRANSLATE_NOOP("Menuiserie", "Profondeur des trous"),
            resolved="hole_depth",
        ),
        PropertySpec(
            "Pitch",
            LENGTH,
            _GROUP,
            QT_TRANSLATE_NOOP("App::Property", "Pas entre deux trous d'une colonne (32 mm)."),
            default=_DEFAULTS.pitch,
            label=QT_TRANSLATE_NOOP("Menuiserie", "Pas"),
        ),
        PropertySpec(
            "EdgeDistance",
            LENGTH,
            _GROUP,
            QT_TRANSLATE_NOOP(
                "App::Property",
                "Distance des deux colonnes aux bords avant et arrière du côté. 0 : automatique "
                "(37 mm).",
            ),
            default=_DEFAULTS.edge_distance,
            label=QT_TRANSLATE_NOOP("Menuiserie", "Distance au bord"),
            resolved="edge_distance",
        ),
        PropertySpec(
            "EndMargin",
            LENGTH,
            _GROUP,
            QT_TRANSLATE_NOOP(
                "App::Property",
                "Distance du premier et du dernier trou au bas et au haut du côté. 0 : "
                "automatique (64 mm).",
            ),
            default=_DEFAULTS.end_margin,
            label=QT_TRANSLATE_NOOP("Menuiserie", "Marge en haut et en bas"),
            resolved="end_margin",
        ),
        PropertySpec(
            "Rows",
            "App::PropertyIntegerConstraint",
            _GROUP,
            QT_TRANSLATE_NOOP(
                "App::Property",
                "Nombre de trous par colonne. 0 : automatique, autant que le côté en reçoit.",
            ),
            default=(_DEFAULTS.rows, 0, _MAX_ROWS, 1),
            label=QT_TRANSLATE_NOOP("Menuiserie", "Trous par colonne"),
            resolved="rows",
        ),
        PropertySpec(
            "WithPins",
            "App::PropertyBool",
            _GROUP,
            QT_TRANSLATE_NOOP(
                "App::Property", "Poser les taquets de la tablette (un par colonne) dans un rang."
            ),
            default=_DEFAULTS.with_pins,
            label=QT_TRANSLATE_NOOP("Menuiserie", "Poser les taquets"),
        ),
        PropertySpec(
            "PinRow",
            "App::PropertyIntegerConstraint",
            _GROUP,
            QT_TRANSLATE_NOOP(
                "App::Property",
                "Rang des taquets, compté depuis le bas (1 : le plus bas). 0 : automatique, rang "
                "du milieu.",
            ),
            default=(_DEFAULTS.pin_row, 0, _MAX_ROWS, 1),
            label=QT_TRANSLATE_NOOP("Menuiserie", "Rang des taquets"),
            resolved="pin_row",
        ),
        PropertySpec(
            "PinProjection",
            LENGTH,
            _GROUP,
            QT_TRANSLATE_NOOP("App::Property", "Saillie du taquet hors de la face du côté."),
            default=_DEFAULTS.pin_projection,
            label=QT_TRANSLATE_NOOP("Menuiserie", "Saillie des taquets"),
        ),
        PropertySpec(
            "Reversed",
            "App::PropertyBool",
            _GROUP,
            QT_TRANSLATE_NOOP(
                "App::Property",
                "Percer la face opposée du côté (par défaut la face tournée vers +Z de la pièce).",
            ),
            default=_DEFAULTS.reversed,
            label=QT_TRANSLATE_NOOP("Menuiserie", "Face opposée"),
        ),
    )
