# SPDX-License-Identifier: LGPL-2.1-or-later
"""Icônes des lignes du panneau « Structure » (ADR 0046) : chargement sûr, sans état global."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from PySide import QtGui

from freecad.menuiserie import icon_path
from freecad.menuiserie.core.structure_icons import ICON_BY_KIND, ICON_BY_SUBTYPE

__all__ = ["load_icons"]


def load_icons() -> Mapping[str, QtGui.QIcon]:
    """Une icône par nom de fichier (genres de ligne et types précis), chargée une fois par
    remplissage de l'arbre. Un fichier absent ou illisible donne l'icône vide (la ligne s'affiche
    sans icône, sans erreur)."""
    icons: dict[str, QtGui.QIcon] = {}
    for name in {*ICON_BY_KIND.values(), *ICON_BY_SUBTYPE.values()}:
        path = Path(icon_path(name))
        icons[name] = QtGui.QIcon(str(path)) if path.is_file() else QtGui.QIcon()
    return icons
