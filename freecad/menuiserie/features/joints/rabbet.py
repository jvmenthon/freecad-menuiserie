# SPDX-License-Identifier: LGPL-2.1-or-later
"""Assemblage en feuillure ou logement du document : proxy ``RabbetJoint``.

Contrat de persistance (ADR 0003) : chemin de ce module, nom de la classe et noms des propriétés
figés. La pièce logée occupe déjà la place de la feuillure : elle est enlevée de la pièce hôte.
"""

from __future__ import annotations

from typing import ClassVar, Final

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.joints import JointKind
from freecad.menuiserie.core.joints.rabbet import RabbetParams
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.joints.base import JointFeature, params_from
from freecad.menuiserie.features.schema import PropertySpec

__all__ = ["RabbetJoint"]

_DEFAULTS: Final = RabbetParams()


class RabbetJoint(JointFeature):
    """Feuillure enlevée dans la pièce hôte à la place de la pièce logée."""

    KIND: ClassVar[JointKind] = JointKind.RABBET
    TYPE: ClassVar[str] = "Menuiserie::Rabbet"
    OBJECT_NAME: ClassVar[str] = "Rabbet"
    LABEL: ClassVar[str] = QT_TRANSLATE_NOOP("Menuiserie", "Feuillure")
    PROPERTIES: ClassVar[tuple[PropertySpec, ...]] = (
        PropertySpec(
            "Through",
            "App::PropertyBool",
            "Feuillure",
            QT_TRANSLATE_NOOP(
                "App::Property",
                "Feuillure filante : prolongée sur toute la longueur de la pièce qui la reçoit.",
            ),
            default=_DEFAULTS.through,
            label=QT_TRANSLATE_NOOP("Menuiserie", "Feuillure filante"),
        ),
    )

    def params(self, obj: DocumentObject) -> RabbetParams:
        """Paramètres de la feuillure lus dans les propriétés de ``obj``."""
        return params_from(obj, RabbetParams)
