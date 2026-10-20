# SPDX-License-Identifier: LGPL-2.1-or-later
"""Apparence d'une pièce de bois d'après la bibliothèque locale (ADR 0004).

Le fichier image est ouvert et contrôlé sur son descripteur, **sans être lu** : son décodage
appartient à ``gui/``. Rien de l'apparence n'est écrit dans le document : seul ``MaterialId`` y
est lu, comme clé de recherche dans la bibliothèque (jamais comme chemin).
"""

from __future__ import annotations

from collections.abc import Callable

from freecad.menuiserie.core.appearance import Appearance, part_appearance
from freecad.menuiserie.core.materials import Texture
from freecad.menuiserie.core.part_model import GrainDirection
from freecad.menuiserie.core.texture_file import TextureFile, TextureRefusedError
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.library import get_library

__all__ = ["appearance_of", "usable_texture_file"]


def usable_texture_file(texture: Texture) -> bool:
    """Vrai si l'image est un fichier ordinaire non vide d'au plus 16 Mio, resté dans le dossier
    de la bibliothèque (liens résolus puis confinés) ; jamais d'exception."""
    try:
        with TextureFile(texture):
            return True
    except TextureRefusedError:
        return False


def appearance_of(
    obj: DocumentObject, image_usable: Callable[[Texture], bool] = usable_texture_file
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
