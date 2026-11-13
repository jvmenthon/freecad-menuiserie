# SPDX-License-Identifier: LGPL-2.1-or-later
"""Noms des usinages pour le menuisier (mortaise, queue, feuillure…), au singulier et au pluriel,
écrits dans le tableau des usinages du plan de pièce (retour de jv du 2026-11-13)."""

from __future__ import annotations

from typing import Final

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP

__all__ = ["NAMES"]

# Noms des usinages, au singulier et au pluriel (textes à traduire).
NAMES: Final = {
    "hole": (
        QT_TRANSLATE_NOOP("Menuiserie", "perçage"),
        QT_TRANSLATE_NOOP("Menuiserie", "perçages"),
    ),
    "cut": (
        QT_TRANSLATE_NOOP("Menuiserie", "entaille"),
        QT_TRANSLATE_NOOP("Menuiserie", "entailles"),
    ),
    "added": (
        QT_TRANSLATE_NOOP("Menuiserie", "partie en saillie"),
        QT_TRANSLATE_NOOP("Menuiserie", "parties en saillie"),
    ),
    "mortise": (
        QT_TRANSLATE_NOOP("Menuiserie", "mortaise"),
        QT_TRANSLATE_NOOP("Menuiserie", "mortaises"),
    ),
    "tenon": (
        QT_TRANSLATE_NOOP("Menuiserie", "tenon"),
        QT_TRANSLATE_NOOP("Menuiserie", "tenons"),
    ),
    "shoulder": (
        QT_TRANSLATE_NOOP("Menuiserie", "arasement"),
        QT_TRANSLATE_NOOP("Menuiserie", "arasements"),
    ),
    "groove": (
        QT_TRANSLATE_NOOP("Menuiserie", "rainure"),
        QT_TRANSLATE_NOOP("Menuiserie", "rainures"),
    ),
    "tongue": (
        QT_TRANSLATE_NOOP("Menuiserie", "languette"),
        QT_TRANSLATE_NOOP("Menuiserie", "languettes"),
    ),
    "rabbet": (
        QT_TRANSLATE_NOOP("Menuiserie", "feuillure"),
        QT_TRANSLATE_NOOP("Menuiserie", "feuillures"),
    ),
    "half_lap": (
        QT_TRANSLATE_NOOP("Menuiserie", "entaille à mi-bois"),
        QT_TRANSLATE_NOOP("Menuiserie", "entailles à mi-bois"),
    ),
    "tail": (
        QT_TRANSLATE_NOOP("Menuiserie", "queue"),
        QT_TRANSLATE_NOOP("Menuiserie", "queues"),
    ),
    "socket": (
        QT_TRANSLATE_NOOP("Menuiserie", "logement de queue"),
        QT_TRANSLATE_NOOP("Menuiserie", "logements de queue"),
    ),
    "miter": (
        QT_TRANSLATE_NOOP("Menuiserie", "coupe d'onglet"),
        QT_TRANSLATE_NOOP("Menuiserie", "coupes d'onglet"),
    ),
    "dowel_hole": (
        QT_TRANSLATE_NOOP("Menuiserie", "perçage de tourillon"),
        QT_TRANSLATE_NOOP("Menuiserie", "perçages de tourillon"),
    ),
    "loose_mortise": (
        QT_TRANSLATE_NOOP("Menuiserie", "mortaise de faux tenon"),
        QT_TRANSLATE_NOOP("Menuiserie", "mortaises de faux tenon"),
    ),
    "biscuit": (
        QT_TRANSLATE_NOOP("Menuiserie", "logement de lamelle"),
        QT_TRANSLATE_NOOP("Menuiserie", "logements de lamelle"),
    ),
    "pin_hole": (
        QT_TRANSLATE_NOOP("Menuiserie", "perçage de taquet"),
        QT_TRANSLATE_NOOP("Menuiserie", "perçages de taquet"),
    ),
    "foot_hole": (
        QT_TRANSLATE_NOOP("Menuiserie", "perçage de pied"),
        QT_TRANSLATE_NOOP("Menuiserie", "perçages de pied"),
    ),
    "screw_hole": (
        QT_TRANSLATE_NOOP("Menuiserie", "avant-trou"),
        QT_TRANSLATE_NOOP("Menuiserie", "avant-trous"),
    ),
}
