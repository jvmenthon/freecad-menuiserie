# SPDX-License-Identifier: LGPL-2.1-or-later
"""Apparence d'une pièce de bois d'après la bibliothèque locale (ADR 0004).

Le fichier image est contrôlé par ``os.stat`` **sans être ouvert** : son décodage appartient à
``gui/``. Rien de l'apparence n'est écrit dans le document : seul ``MaterialId`` y est lu, comme
clé de recherche dans la bibliothèque (jamais comme chemin).
"""

from __future__ import annotations

import os
import stat
from collections.abc import Callable
from pathlib import Path

from freecad.menuiserie.core.appearance import (
    MAX_TEXTURE_FILE_BYTES,
    Appearance,
    part_appearance,
)
from freecad.menuiserie.core.part_model import GrainDirection
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.library import get_library

__all__ = ["appearance_of", "usable_texture_file"]


def usable_texture_file(path: Path) -> bool:
    """Vrai pour un fichier ordinaire non vide d'au plus 16 Mio (liens suivis), sans exception."""
    try:
        status = os.stat(path)
    except (OSError, ValueError):
        return False
    return stat.S_ISREG(status.st_mode) and 0 < status.st_size <= MAX_TEXTURE_FILE_BYTES


def appearance_of(
    obj: DocumentObject, image_usable: Callable[[Path], bool] = usable_texture_file
) -> Appearance | None:
    """Apparence de la pièce ``obj``, ou ``None`` si son matériau est inconnu localement.

    ``image_usable`` décide si l'image de la texture peut être affichée (par défaut : contrôle
    du fichier) ; l'interface y ajoute le décodage. Lecture seule : l'objet n'est pas modifié.
    """
    material = get_library().find(obj.MaterialId)
    if material is None:
        return None
    return part_appearance(material, _grain_of(obj), image_usable)


def _grain_of(obj: DocumentObject) -> GrainDirection:
    """Sens du fil de la pièce ; une valeur inconnue (document plus récent) vaut ``LENGTH``."""
    try:
        return GrainDirection(obj.GrainDirection)
    except ValueError:
        return GrainDirection.LENGTH
