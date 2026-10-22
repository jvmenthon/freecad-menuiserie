# SPDX-License-Identifier: LGPL-2.1-or-later
"""Assemblage à queue d'aronde traversante du document : proxy ``DovetailJoint``.

Contrat de persistance (ADR 0003) : chemin de ce module, nom de la classe et noms des propriétés
figés. Les queues sont ajoutées au bout de la pièce invitée (pièce à queues), les logements
enlevés dans la pièce hôte (pièce à griffes), qu'ils traversent. Nombre, griffes et angle (en
degrés) valent 0 pour « automatique » (:mod:`core.joints.dovetail`).
"""

from __future__ import annotations

import math
from typing import ClassVar, Final

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.joints import JointKind
from freecad.menuiserie.core.joints.dovetail import MAX_TAIL_COUNT, DovetailParams
from freecad.menuiserie.features import schema
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.joints.base import JointFeature
from freecad.menuiserie.features.schema import ANGLE, LENGTH, PropertySpec

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
            "Angle",
            ANGLE,
            _GROUP,
            QT_TRANSLATE_NOOP(
                "App::Property",
                "Angle des flancs des queues, en degrés (0 à 30) ; 0 = automatique (10°).",
            ),
            default=_DEFAULTS.angle,
            label=QT_TRANSLATE_NOOP("Menuiserie", "Angle des queues"),
            resolved="angle",
        ),
    )

    def onDocumentRestored(self, obj: DocumentObject) -> None:
        """Comme les autres assemblages ; l'ancienne propriété ``Slope`` (pente 1:n, versions de
        développement) est convertie en ``Angle`` puis retirée."""
        slope = getattr(obj, "Slope", None) if "Slope" in obj.PropertiesList else None
        if "Slope" in obj.PropertiesList:
            obj.removeProperty("Slope")
        super().onDocumentRestored(obj)
        schema.add_missing_properties(obj, self.specs())
        if isinstance(slope, (int, float)) and slope > 0 and not obj.Angle.Value:
            obj.Angle = math.degrees(math.atan(1 / slope))
