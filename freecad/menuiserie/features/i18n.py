# SPDX-License-Identifier: LGPL-2.1-or-later
"""Traduction, côté ``features/``, des gabarits français de l'atelier.

Les gabarits (marqués par ``QT_TRANSLATE_NOOP`` dans ``core/`` ou ``features/``) sont traduits
par ``App.Qt.translate``, disponible sans interface : aucun import de Qt ici.
"""

from __future__ import annotations

from collections.abc import Mapping

import FreeCAD as App

from freecad.menuiserie.core.i18n import CONTEXT

__all__ = ["translated"]


def translated(template: str, params: Mapping[str, str] | None = None) -> str:
    """Gabarit français traduit (contexte « Menuiserie »), puis rempli avec ``params``."""
    text: str = App.Qt.translate(CONTEXT, template)
    return text.format_map(params or {})
