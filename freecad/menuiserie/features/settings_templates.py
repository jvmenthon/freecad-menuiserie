# SPDX-License-Identifier: LGPL-2.1-or-later
"""Réglages des gabarits : clés et catalogue du groupe « Gabarits » (ADR 0069).

Ce module ne lit aucune préférence : il décrit seulement les réglages, que
:mod:`freecad.menuiserie.features.settings` réunit dans le catalogue de l'atelier. Les valeurs ne
sont que celles proposées à l'ouverture du formulaire du caisson
(:mod:`freecad.menuiserie.features.template_settings`) ; le caisson créé les garde, et l'API
(``make_carcass``) reste sur les valeurs de ``core``.
"""

from __future__ import annotations

from typing import Final

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.materials import MAX_THICKNESS_MM
from freecad.menuiserie.core.part_model import MAX_DIMENSION_MM
from freecad.menuiserie.core.templates.carcass import CarcassParams
from freecad.menuiserie.features.settings_build import length_setting
from freecad.menuiserie.kit.config.catalog import Setting

__all__ = [
    "CARCASS_BACK_THICKNESS",
    "CARCASS_DEPTH",
    "CARCASS_FIELDS",
    "CARCASS_HEIGHT",
    "CARCASS_RABBET_DEPTH",
    "CARCASS_THICKNESS",
    "CARCASS_WIDTH",
    "TEMPLATES",
    "template_settings",
]

# Clés (noms des paramètres FreeCAD, figés : une clé renommée perd la valeur de l'utilisateur).
CARCASS_WIDTH: Final = "CarcassWidth"
CARCASS_DEPTH: Final = "CarcassDepth"
CARCASS_HEIGHT: Final = "CarcassHeight"
CARCASS_THICKNESS: Final = "CarcassThickness"
CARCASS_BACK_THICKNESS: Final = "CarcassBackThickness"
CARCASS_RABBET_DEPTH: Final = "CarcassRabbetDepth"
# Champ de ``CarcassParams`` → clé du réglage.
CARCASS_FIELDS: Final = {
    "width": CARCASS_WIDTH,
    "depth": CARCASS_DEPTH,
    "height": CARCASS_HEIGHT,
    "thickness": CARCASS_THICKNESS,
    "back_thickness": CARCASS_BACK_THICKNESS,
    "rabbet_depth": CARCASS_RABBET_DEPTH,
}

TEMPLATES: Final = QT_TRANSLATE_NOOP("Menuiserie", "Gabarits")


def _carcass(
    key: str, field: str, label: str, tooltip: str, maximum: float = MAX_DIMENSION_MM
) -> Setting:
    """Cote proposée au formulaire du caisson, de même défaut que ``CarcassParams``."""
    default = float(getattr(CarcassParams(), field))
    return length_setting(
        key, default, label, tooltip, TEMPLATES, maximum=maximum, remember_last=True
    )


def template_settings() -> list[Setting]:
    """Cotes et épaisseurs proposées à l'ouverture du formulaire du caisson."""
    return [
        _carcass(
            CARCASS_WIDTH,
            "width",
            QT_TRANSLATE_NOOP("Menuiserie", "Caisson : largeur"),
            QT_TRANSLATE_NOOP("Menuiserie", "Largeur hors tout proposée pour un nouveau caisson."),
        ),
        _carcass(
            CARCASS_DEPTH,
            "depth",
            QT_TRANSLATE_NOOP("Menuiserie", "Caisson : profondeur"),
            QT_TRANSLATE_NOOP(
                "Menuiserie", "Profondeur hors tout proposée pour un nouveau caisson."
            ),
        ),
        _carcass(
            CARCASS_HEIGHT,
            "height",
            QT_TRANSLATE_NOOP("Menuiserie", "Caisson : hauteur"),
            QT_TRANSLATE_NOOP("Menuiserie", "Hauteur hors tout proposée pour un nouveau caisson."),
        ),
        _carcass(
            CARCASS_THICKNESS,
            "thickness",
            QT_TRANSLATE_NOOP("Menuiserie", "Caisson : épaisseur des panneaux"),
            QT_TRANSLATE_NOOP(
                "Menuiserie", "Épaisseur des panneaux proposée pour un nouveau caisson."
            ),
            MAX_THICKNESS_MM,
        ),
        _carcass(
            CARCASS_BACK_THICKNESS,
            "back_thickness",
            QT_TRANSLATE_NOOP("Menuiserie", "Caisson : épaisseur du fond"),
            QT_TRANSLATE_NOOP("Menuiserie", "Épaisseur du fond proposée pour un nouveau caisson."),
            MAX_THICKNESS_MM,
        ),
        _carcass(
            CARCASS_RABBET_DEPTH,
            "rabbet_depth",
            QT_TRANSLATE_NOOP("Menuiserie", "Caisson : feuillure du fond"),
            QT_TRANSLATE_NOOP(
                "Menuiserie", "Profondeur de feuillure du fond proposée pour un nouveau caisson."
            ),
            MAX_THICKNESS_MM,
        ),
    ]
