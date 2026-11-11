# SPDX-License-Identifier: LGPL-2.1-or-later
"""Icônes des lignes du panneau « Structure » (ADR 0046) : chargement sûr, mis en cache."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from PySide import QtGui

from freecad.menuiserie import icon_path
from freecad.menuiserie.core.structure_icons import ICON_BY_KIND, ICON_BY_SUBTYPE

__all__ = ["load_icons", "reset_icons"]

_CACHE: dict[str, QtGui.QIcon] = {}  # cache explicite et réinitialisable (:func:`reset_icons`)


def reset_icons() -> None:
    """Vide le cache (les icônes sont relues au prochain remplissage)."""
    _CACHE.clear()


def load_icons() -> Mapping[str, QtGui.QIcon]:
    """Une icône par nom de fichier (genres de ligne et types précis), lue une seule fois (le
    panneau se remplit à chaque modification du document). Un fichier absent ou illisible donne
    l'icône vide (la ligne s'affiche sans icône, sans erreur)."""
    if not _CACHE:
        for name in {*ICON_BY_KIND.values(), *ICON_BY_SUBTYPE.values()}:
            path = Path(icon_path(name))
            _CACHE[name] = QtGui.QIcon(str(path)) if path.is_file() else QtGui.QIcon()
    return _CACHE
