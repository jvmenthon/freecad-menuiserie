# SPDX-License-Identifier: LGPL-2.1-or-later
"""Réglages des plans dans la configuration de l'atelier (issue #153, ADR 0031 et 0053).

Paramètres FreeCAD sous ``Mod/Menuiserie`` : format et sens de la feuille, auteur écrit au
cartouche. Une valeur inconnue (fichier de configuration modifié à la main) est remplacée par la
valeur par défaut, jamais transmise.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any, Final

import FreeCAD as App

from freecad.menuiserie.core.drawing import DEFAULT_FORMAT, PAGE_FORMATS, Orientation, clean_field

__all__ = [
    "AUTHOR",
    "PAGE_FORMAT",
    "PAGE_ORIENTATION",
    "PARAM_PATH",
    "DrawingOptions",
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


@dataclass(frozen=True)
class DrawingOptions:
    """Feuille et cartouche du plan. ``None`` : le réglage de la configuration de l'atelier pour
    le format et le sens ; pour le titre, le client et le numéro de devis, la valeur déjà
    enregistrée sur la page que l'on refait, sinon le nom de l'ouvrage (titre) ou rien."""

    page_format: str | None = None
    orientation: Orientation | None = None
    title: str | None = None
    client: str | None = None
    quote: str | None = None
    # Attente de la géométrie des vues que TechDraw calcule en tâche de fond avec l'interface
    # (voir gui/drawing_hlr.py) ; sans elle, une vue pas encore calculée n'est pas cotée.
    settle: Callable[[Sequence[Any]], None] | None = field(default=None, compare=False)

    def resolved_format(self) -> str:
        """Format demandé, sinon celui de la configuration."""
        return self.page_format or default_format()

    def resolved_orientation(self) -> Orientation:
        """Sens demandé, sinon celui de la configuration."""
        return self.orientation or default_orientation()
