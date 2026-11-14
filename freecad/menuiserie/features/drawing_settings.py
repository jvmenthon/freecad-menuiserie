# SPDX-License-Identifier: LGPL-2.1-or-later
"""Réglages des plans dans la configuration de l'atelier (issue #153, ADR 0031 et 0053).

Paramètres FreeCAD sous ``Mod/Menuiserie`` : format et sens de la feuille, auteur écrit au
cartouche. Une valeur inconnue (fichier de configuration modifié à la main) est remplacée par la
valeur par défaut, jamais transmise.
"""

from __future__ import annotations

from typing import Final

import FreeCAD as App

from freecad.menuiserie.core.drawing import DEFAULT_FORMAT, PAGE_FORMATS, Orientation, clean_field

__all__ = [
    "AUTHOR",
    "PAGE_FORMAT",
    "PAGE_ORIENTATION",
    "PARAM_PATH",
    "default_author",
    "default_format",
    "default_orientation",
]

PARAM_PATH: Final = "User parameter:BaseApp/Preferences/Mod/Menuiserie"
PAGE_FORMAT: Final = "DrawingPageFormat"
PAGE_ORIENTATION: Final = "DrawingPageOrientation"
AUTHOR: Final = "DrawingAuthor"


def default_format() -> str:
    """Format de feuille réglé (« A3 » par défaut)."""
    value = str(App.ParamGet(PARAM_PATH).GetString(PAGE_FORMAT, DEFAULT_FORMAT)).strip().upper()
    return value if value in PAGE_FORMATS else DEFAULT_FORMAT


def default_orientation() -> Orientation:
    """Sens de feuille réglé (paysage par défaut)."""
    value = str(App.ParamGet(PARAM_PATH).GetString(PAGE_ORIENTATION, "")).strip().lower()
    return (
        Orientation.PORTRAIT
        if value == Orientation.PORTRAIT.value.lower()
        else Orientation.LANDSCAPE
    )


def default_author(doc_author: str = "") -> str:
    """Auteur écrit au cartouche : celui de la configuration, sinon ``doc_author``."""
    return clean_field(str(App.ParamGet(PARAM_PATH).GetString(AUTHOR, ""))) or clean_field(
        doc_author
    )
