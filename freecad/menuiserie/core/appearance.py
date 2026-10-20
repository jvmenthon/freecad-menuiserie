# SPDX-License-Identifier: LGPL-2.1-or-later
"""Apparence d'une pièce de bois : couleur du matériau ou texture à l'échelle réelle (ADR 0004).

Logique pure, sans FreeCAD ni Qt : ``features/`` fournit la bibliothèque et le contrôle du
fichier image, ``gui/`` décode l'image et construit les nœuds Coin. Les longueurs sont en mm,
les directions de projection en mm⁻¹, dans le repère local de la pièce (X = longueur,
Y = largeur, Z = épaisseur).
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from freecad.menuiserie.core.materials import Material
from freecad.menuiserie.core.part_model import GrainDirection

__all__ = [
    "MAX_TEXTURE_FILE_BYTES",
    "MAX_TEXTURE_PIXELS",
    "TEXTURE_BASE_COLOR",
    "Appearance",
    "TextureMapping",
    "Vector3",
    "part_appearance",
    "texture_mapping",
]

TEXTURE_BASE_COLOR: Final = (255, 255, 255)  # couleur diffuse modulée par la texture
MAX_TEXTURE_FILE_BYTES: Final = 16 * 1024 * 1024
MAX_TEXTURE_PIXELS: Final = 4096  # par côté

Vector3 = tuple[float, float, float]


@dataclass(frozen=True)
class TextureMapping:
    """Projection plane, en mm⁻¹ dans le repère local : S = direction_s · p, T = direction_t · p.

    Une coordonnée de texture qui augmente de 1 correspond à une répétition de l'image.
    """

    direction_s: Vector3
    direction_t: Vector3


@dataclass(frozen=True)
class Appearance:
    """Ce qu'affiche une pièce : la couleur du matériau, ou son image projetée par ``mapping``.

    ``color`` reste la couleur de secours ; ``image`` et ``mapping`` sont présents ensemble ou
    absents ensemble (``ValueError`` sinon).
    """

    color: tuple[int, int, int]
    image: Path | None = None
    mapping: TextureMapping | None = None

    def __post_init__(self) -> None:
        if (self.image is None) != (self.mapping is None):
            raise ValueError("Appearance : image et mapping vont ensemble")


def texture_mapping(size: tuple[float, float], grain: GrainDirection) -> TextureMapping:
    """Projection d'une image couvrant ``size`` = (largeur, hauteur) mm, fil selon sa largeur.

    S suit l'axe du fil (X pour ``LENGTH`` et ``NONE``, Y pour ``WIDTH``) divisé par la largeur ;
    T est la somme des deux autres coordonnées divisée par la hauteur. La projection ne dépend
    ni des cotes ni du placement de la pièce. ``ValueError`` si une taille n'est pas un nombre
    fini strictement positif.
    """
    width, height = size
    if not all(math.isfinite(value) and value > 0 for value in (width, height)):
        raise ValueError(f"taille de texture invalide : {size!r}")
    along, across = 1.0 / width, 1.0 / height
    if grain is GrainDirection.WIDTH:
        return TextureMapping((0.0, along, 0.0), (across, 0.0, across))
    return TextureMapping((along, 0.0, 0.0), (0.0, across, across))


def part_appearance(
    material: Material, grain: GrainDirection, image_usable: Callable[[Path], bool]
) -> Appearance:
    """Apparence d'une pièce : texture du matériau si ``image_usable`` l'accepte, sinon sa
    couleur (``image_usable`` n'est pas appelée pour un matériau sans texture)."""
    texture = material.texture
    if texture is None or not image_usable(texture.image):
        return Appearance(material.color)
    return Appearance(material.color, texture.image, texture_mapping(texture.size, grain))
