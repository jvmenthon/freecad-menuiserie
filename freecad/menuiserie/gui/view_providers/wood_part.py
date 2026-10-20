# SPDX-License-Identifier: LGPL-2.1-or-later
"""Affichage de la pièce de bois : icône, couleur et texture du matériau (ADR 0004).

Contrat de persistance (ADR 0003) : le chemin de ce module, le nom de la classe et la propriété
de vue ``MaterialColor`` sont écrits dans les documents (``GuiDocument.xml``) ; ils ne changent
jamais. Le ViewProvider est le seul à écrire la couleur diffuse de ``ShapeAppearance`` : le
blanc de base quand la texture est affichée, sinon ``MaterialColor``. La texture n'est jamais
enregistrée : elle est recalculée depuis la bibliothèque locale.
"""

from __future__ import annotations

from typing import Any, Final

from freecad.menuiserie import icon_path
from freecad.menuiserie.core.appearance import TEXTURE_BASE_COLOR, TextureMapping
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.features.appearance import appearance_of
from freecad.menuiserie.features.freecad_types import HIDDEN, DocumentObject
from freecad.menuiserie.features.library import get_library
from freecad.menuiserie.gui.textures import TextureNode, TextureSwitch, texture_cache

ViewObject = Any
Color = tuple[float, ...]

ICON: Final = "Menuiserie_WoodPart.svg"
MATERIAL_COLOR: Final = "MaterialColor"
# Propriétés de la pièce dont dépend l'apparence (la projection ne dépend pas des cotes).
_APPEARANCE_PROPERTIES: Final = frozenset({"MaterialId", "GrainDirection"})
_COLOR_SCALE: Final = 255
# Gris clair des formes de FreeCAD : couleur initiale si l'apparence ne fournit aucun matériau.
_FALLBACK_DIFFUSE: Final = (0.8, 0.8, 0.8)
_MATERIAL_COLOR_TOOLTIP: Final = QT_TRANSLATE_NOOP(
    "App::Property",
    "Couleur du matériau, enregistrée au choix du matériau ; affichée quand aucune texture ne "
    "peut l'être.",
)


class ViewProviderWoodPart:
    """ViewProvider de la pièce de bois. Chemin de module figé (ADR 0003).

    Sans état enregistré (``dumps`` renvoie ``None``) : la couleur est dans ``MaterialColor``,
    les nœuds de texture sont recréés par ``attach``.
    """

    def __init__(self, vobj: ViewObject) -> None:
        vobj.Proxy = self
        _ensure_material_color(vobj)
        _update_material_color(vobj.Object, vobj)
        self._refresh(vobj)

    def attach(self, vobj: ViewObject) -> None:
        """Garde le ViewObject (non enregistré) pour ``finishRestoring`` et insère les nœuds
        de texture, inactifs, avant le sélecteur de modes d'affichage."""
        self.vobj = vobj
        self._texture = TextureSwitch()
        self._texture.insert_before(vobj.RootNode, vobj.SwitchNode)

    def getIcon(self) -> str:
        """Icône de l'arbre : celle de la commande « Pièce de bois »."""
        return icon_path(ICON)

    def updateData(self, obj: DocumentObject, prop: str) -> None:
        """Nouveau matériau ou sens du fil (hors restauration) : la couleur du matériau est
        enregistrée, puis la texture ou la couleur affichée."""
        if prop not in _APPEARANCE_PROPERTIES or "Restore" in obj.State:
            return
        if prop == "MaterialId":
            _update_material_color(obj, obj.ViewObject)
        self._refresh(obj.ViewObject)

    def onChanged(self, vobj: ViewObject, prop: str) -> None:
        """La couleur enregistrée est reportée sur la couleur diffuse, sauf sous une texture."""
        if prop == MATERIAL_COLOR:
            _show_diffuse(vobj, self._diffuse(vobj))

    def finishRestoring(self) -> None:
        """Recrée ``MaterialColor`` si le document est antérieur, puis réaffiche la texture
        de la bibliothèque locale ou, à défaut, la couleur enregistrée."""
        vobj = getattr(self, "vobj", None)
        if vobj is None:
            return
        _ensure_material_color(vobj)
        self._refresh(vobj)

    def dumps(self) -> None:
        """Proxy sans état : rien à enregistrer."""
        return None

    def loads(self, state: object) -> None:
        """Proxy sans état : rien à relire."""
        del state

    def _refresh(self, vobj: ViewObject) -> None:
        """Affiche la texture du matériau si elle est utilisable, sinon ``MaterialColor``.

        Sans effet tant que ``MaterialColor`` n'existe pas (attachement en cours) : ``__init__``
        et ``finishRestoring`` rappellent cette méthode une fois la propriété créée."""
        if MATERIAL_COLOR not in vobj.PropertiesList:
            return
        switch: TextureSwitch | None = getattr(self, "_texture", None)
        if switch is not None:
            shown = _shown_texture(vobj.Object)
            if shown is None:
                switch.hide()
            else:
                switch.show(*shown)
        _show_diffuse(vobj, self._diffuse(vobj))

    def _diffuse(self, vobj: ViewObject) -> tuple[int, int, int]:
        """Blanc de base sous une texture affichée, sinon la couleur du matériau."""
        switch: TextureSwitch | None = getattr(self, "_texture", None)
        if switch is not None and switch.active:
            return TEXTURE_BASE_COLOR
        return _to_bytes(vobj.MaterialColor)


def _shown_texture(obj: DocumentObject) -> tuple[TextureMapping, TextureNode] | None:
    """Projection et nœud partagé de la texture à afficher ; ``None`` : couleur seule."""
    cache = texture_cache()
    appearance = appearance_of(obj, cache.usable)
    if appearance is None or appearance.texture is None or appearance.mapping is None:
        return None
    texture = cache.node(appearance.texture)
    return None if texture is None else (appearance.mapping, texture)


def _to_bytes(color: Color) -> tuple[int, int, int]:
    """Composantes rouge, vert, bleu de 0 à 255 (comparaison sans erreur d'arrondi)."""
    red, green, blue = (round(component * _COLOR_SCALE) for component in color[:3])
    return red, green, blue


def _from_bytes(color: tuple[int, int, int]) -> Color:
    return tuple(component / _COLOR_SCALE for component in color)


def _ensure_material_color(vobj: ViewObject) -> None:
    """Ajoute ``MaterialColor`` (masquée) si elle manque, initialisée à la couleur diffuse."""
    if MATERIAL_COLOR in vobj.PropertiesList:
        return
    diffuse = _diffuse_color(vobj)
    vobj.addProperty("App::PropertyColor", MATERIAL_COLOR, "Matériau", _MATERIAL_COLOR_TOOLTIP)
    vobj.setEditorMode(MATERIAL_COLOR, HIDDEN)
    vobj.MaterialColor = _from_bytes(_to_bytes(diffuse))


def _update_material_color(obj: DocumentObject, vobj: ViewObject) -> None:
    """Couleur du matériau de la bibliothèque ; inconnu localement : valeur enregistrée gardée."""
    if MATERIAL_COLOR not in vobj.PropertiesList:
        return
    material = get_library().find(obj.MaterialId)
    if material is not None and _to_bytes(vobj.MaterialColor) != material.color:
        vobj.MaterialColor = _from_bytes(material.color)


def _diffuse_color(vobj: ViewObject) -> Color:
    """Couleur diffuse du premier matériau d'affichage ; gris clair si ``ShapeAppearance`` est
    vide (document altéré)."""
    appearance = vobj.ShapeAppearance
    if not appearance:
        return _FALLBACK_DIFFUSE
    color: Color = tuple(appearance[0].DiffuseColor)
    return color


def _show_diffuse(vobj: ViewObject, wanted: tuple[int, int, int]) -> None:
    """Couleur diffuse de chaque matériau d'affichage = ``wanted`` (transparence et autres
    champs inchangés) ; rien n'est écrit si elle est déjà affichée."""
    appearance = list(vobj.ShapeAppearance)
    if all(_to_bytes(material.DiffuseColor) == wanted for material in appearance):
        return
    for material in appearance:
        alpha = tuple(material.DiffuseColor)[3:]
        material.DiffuseColor = _from_bytes(wanted) + alpha
    vobj.ShapeAppearance = appearance
