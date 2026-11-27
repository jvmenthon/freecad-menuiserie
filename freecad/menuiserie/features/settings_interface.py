# SPDX-License-Identifier: LGPL-2.1-or-later
"""Réglages d'interface : clés et catalogue du groupe « Affichage » (ADR 0069).

Ce module ne lit aucune préférence : il décrit seulement les réglages, que
:mod:`freecad.menuiserie.features.settings` réunit dans le catalogue de l'atelier. Ces réglages
n'influencent aucun document : ils sont lus au moment de l'usage
(:mod:`freecad.menuiserie.features.interface_settings`).
"""

from __future__ import annotations

from typing import Final

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.rotation import DEFAULT_STEP_DEGREES
from freecad.menuiserie.features.settings_build import DEGREES, flag_setting
from freecad.menuiserie.kit.config.catalog import Kind, Setting

__all__ = ["DISPLAY", "ROTATION_STEP", "STRUCTURE_AUTO_OPEN", "interface_settings"]

# Clés (noms des paramètres FreeCAD, figés : une clé renommée perd la valeur de l'utilisateur).
ROTATION_STEP: Final = "RotationSnapStep"
STRUCTURE_AUTO_OPEN: Final = "StructureAutoOpen"

DISPLAY: Final = QT_TRANSLATE_NOOP("Menuiserie", "Affichage")

_MIN_ROTATION_STEP_DEG: Final = 1.0
_MAX_ROTATION_STEP_DEG: Final = 90.0
_STRUCTURE_TIP: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Ouvre le panneau Structure à l'activation de l'atelier, sauf si vous l'avez fermé.",
)


def interface_settings() -> list[Setting]:
    """Pas de rotation aimanté et ouverture automatique du panneau « Structure »."""
    return [
        Setting(
            ROTATION_STEP,
            Kind.FLOAT,
            DEFAULT_STEP_DEGREES,
            QT_TRANSLATE_NOOP("Menuiserie", "Pas de rotation aimanté"),
            QT_TRANSLATE_NOOP(
                "Menuiserie", "Angle d'aimantation d'une rotation à la souris (Maj : libre)."
            ),
            DISPLAY,
            unit=DEGREES,
            minimum=_MIN_ROTATION_STEP_DEG,
            maximum=_MAX_ROTATION_STEP_DEG,
        ),
        flag_setting(
            STRUCTURE_AUTO_OPEN,
            True,
            QT_TRANSLATE_NOOP("Menuiserie", "Ouvrir le panneau Structure au démarrage"),
            _STRUCTURE_TIP,
            DISPLAY,
            remember_last=False,
        ),
    ]
