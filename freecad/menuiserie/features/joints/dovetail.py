# SPDX-License-Identifier: LGPL-2.1-or-later
"""Assemblage à queue d'aronde traversante du document : proxy ``DovetailJoint``.

Contrat de persistance (ADR 0003) : chemin de ce module, nom de la classe et noms des propriétés
figés. Les queues sont ajoutées au bout de la pièce invitée (pièce à queues), les logements
enlevés dans la pièce hôte (pièce à griffes), qu'ils traversent. Nombre, griffes et pente valent
0 pour « automatique » (:mod:`core.joints.dovetail`).
"""

from __future__ import annotations

from typing import ClassVar, Final

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.joints import JointKind
from freecad.menuiserie.core.joints.dovetail import MAX_TAIL_COUNT, DovetailParams
from freecad.menuiserie.features.joints.base import JointFeature
from freecad.menuiserie.features.schema import LENGTH, PropertySpec

__all__ = ["DovetailJoint"]

_GROUP: Final = "Queue d'aronde"
_DEFAULTS: Final = DovetailParams()


class DovetailJoint(JointFeature):
    """Queues ajoutées à la pièce invitée, logements traversants dans la pièce hôte."""

    KIND: ClassVar[JointKind] = JointKind.DOVETAIL
    TYPE: ClassVar[str] = "Menuiserie::Dovetail"
    OBJECT_NAME: ClassVar[str] = "Dovetail"
    LABEL: ClassVar[str] = QT_TRANSLATE_NOOP("Menuiserie", "Queue d'aronde")
    PARAMS: ClassVar[type[DovetailParams]] = DovetailParams
    PROPERTIES: ClassVar[tuple[PropertySpec, ...]] = (
        PropertySpec(
            "TailCount",
            "App::PropertyIntegerConstraint",
            _GROUP,
            QT_TRANSLATE_NOOP(
                "App::Property",
                "Nombre de queues ; 0 = automatique, environ une queue par largeur de trois "
                "épaisseurs.",
            ),
            default=(_DEFAULTS.tail_count, 0, MAX_TAIL_COUNT, 1),
            label=QT_TRANSLATE_NOOP("Menuiserie", "Nombre de queues"),
            resolved="tail_count",
        ),
        PropertySpec(
            "PinWidth",
            LENGTH,
            _GROUP,
            QT_TRANSLATE_NOOP(
                "App::Property",
                "Largeur des griffes au plus étroit, sur la face extérieure de la pièce à "
                "griffes ; 0 = automatique, le tiers de son épaisseur.",
            ),
            default=_DEFAULTS.pin_width,
            label=QT_TRANSLATE_NOOP("Menuiserie", "Largeur des griffes"),
            resolved="pin_width",
        ),
        PropertySpec(
            "Slope",
            "App::PropertyFloat",
            _GROUP,
            QT_TRANSLATE_NOOP("App::Property", "Pente 1:n des queues ; 0 = automatique (1:6)."),
            default=_DEFAULTS.slope,
            label=QT_TRANSLATE_NOOP("Menuiserie", "Pente 1:n"),
            resolved="slope",
        ),
    )
