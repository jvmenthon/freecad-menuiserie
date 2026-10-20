# SPDX-License-Identifier: LGPL-2.1-or-later
"""Apparence affichée d'une pièce : texture du matériau (ADR 0004) ou couleur diffuse.

Partagée par composition entre le ViewProvider de la pièce de bois et celui de la pièce usinée
(spécification J3, § 4.6) : la pièce usinée montre la texture, le fil et la couleur
``MaterialColor`` de sa brute. Rien n'est enregistré dans le document par ce module hormis la
couleur diffuse de ``ShapeAppearance`` du ViewObject affiché.
"""

from __future__ import annotations

from typing import Any, Final

from freecad.menuiserie.core.appearance import TEXTURE_BASE_COLOR, TextureMapping
from freecad.menuiserie.core.materials import Texture
from freecad.menuiserie.features.appearance import appearance_of
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.library import get_library
from freecad.menuiserie.gui.textures import TextureNode, TextureSwitch, texture_cache

__all__ = [
    "FALLBACK_DIFFUSE",
    "MATERIAL_COLOR",
    "PartAppearance",
    "Rgb",
    "from_bytes",
    "material_color_of",
    "show_diffuse",
    "to_bytes",
]

ViewObject = Any
Color = tuple[float, ...]
Rgb = tuple[int, int, int]

MATERIAL_COLOR: Final = "MaterialColor"
# Gris clair des formes de FreeCAD : couleur si l'apparence ne fournit aucun matériau.
FALLBACK_DIFFUSE: Final = (0.8, 0.8, 0.8)
_COLOR_SCALE: Final = 255


class PartAppearance:
    """Nœuds de texture d'un ViewObject et choix de sa couleur diffuse.

    Les nœuds, inactifs, sont insérés avant le sélecteur de modes d'affichage du ViewObject.
    """

    def __init__(self, vobj: ViewObject) -> None:
        self._texture = TextureSwitch()
        self._texture.insert_before(vobj.RootNode, vobj.SwitchNode)

    def show(self, vobj: ViewObject, part: DocumentObject, color: Rgb) -> None:
        """Affiche sur ``vobj`` la texture du matériau de ``part`` (pièce de bois brute) si elle
        est utilisable, sinon la couleur ``color``."""
        shown = _shown_texture(part)
        if shown is None:
            self._texture.hide()
        else:
            self._texture.show(*shown)
        self.show_color(vobj, color)

    def show_color(self, vobj: ViewObject, color: Rgb) -> None:
        """Couleur diffuse : blanc de base sous une texture affichée, sinon ``color``."""
        show_diffuse(vobj, TEXTURE_BASE_COLOR if self._texture.active else color)


def material_color_of(part: DocumentObject) -> Rgb:
    """Couleur du matériau de la pièce de bois ``part`` : sa propriété de vue ``MaterialColor``,
    à défaut la couleur de la bibliothèque, à défaut le gris clair de FreeCAD."""
    vobj = getattr(part, "ViewObject", None)
    if vobj is not None and MATERIAL_COLOR in vobj.PropertiesList:
        return to_bytes(vobj.MaterialColor)
    material = get_library().find(part.MaterialId)
    return material.color if material is not None else to_bytes(FALLBACK_DIFFUSE)


def _shown_texture(obj: DocumentObject) -> tuple[TextureMapping, TextureNode] | None:
    """Projection et nœud partagé de la texture à afficher ; ``None`` : couleur seule."""
    cache = texture_cache()
    nodes: dict[Texture, TextureNode | None] = {}

    def usable(texture: Texture) -> bool:
        # Le nœud obtenu en contrôlant l'image est gardé : le fichier n'est ouvert qu'une fois.
        nodes[texture] = cache.node(texture)
        return nodes[texture] is not None

    appearance = appearance_of(obj, usable)
    if appearance is None or appearance.texture is None or appearance.mapping is None:
        return None
    texture = nodes.get(appearance.texture)
    return None if texture is None else (appearance.mapping, texture)


def to_bytes(color: Color) -> Rgb:
    """Composantes rouge, vert, bleu de 0 à 255 (comparaison sans erreur d'arrondi)."""
    red, green, blue = (round(component * _COLOR_SCALE) for component in color[:3])
    return red, green, blue


def from_bytes(color: Rgb) -> Color:
    """Composantes de 0 à 1 de la couleur ``color`` (0 à 255)."""
    return tuple(component / _COLOR_SCALE for component in color)


def show_diffuse(vobj: ViewObject, wanted: Rgb) -> None:
    """Couleur diffuse de chaque matériau d'affichage = ``wanted`` (transparence et autres
    champs inchangés) ; rien n'est écrit si elle est déjà affichée."""
    appearance = list(vobj.ShapeAppearance)
    if all(to_bytes(material.DiffuseColor) == wanted for material in appearance):
        return
    for material in appearance:
        alpha = tuple(material.DiffuseColor)[3:]
        material.DiffuseColor = from_bytes(wanted) + alpha
    vobj.ShapeAppearance = appearance
