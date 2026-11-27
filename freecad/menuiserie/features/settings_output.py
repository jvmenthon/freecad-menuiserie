# SPDX-License-Identifier: LGPL-2.1-or-later
"""Réglages des sorties : liste de débit et plans cotés (ADR 0069).

Ce module ne lit aucune préférence : il décrit seulement les réglages, que
:mod:`freecad.menuiserie.features.settings` réunit dans le catalogue de l'atelier.
"""

from __future__ import annotations

from typing import Final

from freecad.menuiserie.core.cutlist import DEFAULT_MARK_PREFIX
from freecad.menuiserie.core.drawing import DEFAULT_FORMAT, PAGE_FORMATS
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.kit.config.catalog import Kind, Setting

__all__ = [
    "CUTLIST",
    "CUTLIST_EXPORT_FOLDER",
    "DRAWINGS",
    "DRAWING_FORMAT",
    "MARK_PREFIX",
    "MAX_MARK_PREFIX_LENGTH",
    "output_settings",
]

# Clés (noms des paramètres FreeCAD, figés : une clé renommée perd la valeur de l'utilisateur).
MARK_PREFIX: Final = "CutListMarkPrefix"
CUTLIST_EXPORT_FOLDER: Final = "CutListExportFolder"
MAX_MARK_PREFIX_LENGTH: Final = 8  # un repère reste lisible sur la pièce et dans la liste
_MARK_PREFIX_TIP: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Lettres placées devant le numéro des repères automatiques. Vide : « M ».",
)
DRAWING_FORMAT: Final = "DrawingPageFormat"  # clé déjà utilisée par les plans, gardée

CUTLIST: Final = QT_TRANSLATE_NOOP("Menuiserie", "Liste de débit")
DRAWINGS: Final = QT_TRANSLATE_NOOP("Menuiserie", "Plans cotés")


def output_settings() -> list[Setting]:
    """Préfixe des repères, dossier d'export de la liste de débit, format de feuille des plans."""
    return [
        Setting(
            MARK_PREFIX,
            Kind.TEXT,
            DEFAULT_MARK_PREFIX,
            QT_TRANSLATE_NOOP("Menuiserie", "Préfixe des repères"),
            _MARK_PREFIX_TIP,
            CUTLIST,
            max_length=MAX_MARK_PREFIX_LENGTH,
        ),
        Setting(
            CUTLIST_EXPORT_FOLDER,
            Kind.PATH,
            "",
            QT_TRANSLATE_NOOP("Menuiserie", "Dossier d'export"),
            QT_TRANSLATE_NOOP(
                "Menuiserie",
                "Dossier proposé pour exporter la liste de débit. Vide : dossier du document.",
            ),
            CUTLIST,
        ),
        Setting(
            DRAWING_FORMAT,
            Kind.CHOICE,
            DEFAULT_FORMAT,
            QT_TRANSLATE_NOOP("Menuiserie", "Format de feuille"),
            QT_TRANSLATE_NOOP("Menuiserie", "Format de feuille proposé pour un nouveau plan."),
            DRAWINGS,
            choices=tuple(PAGE_FORMATS),
            remember_last=True,
        ),
    ]
