# SPDX-License-Identifier: LGPL-2.1-or-later
"""Affichage de la pièce de bois : icône, couleur du matériau et édition au double-clic.

Contrat de persistance (ADR 0003) : le chemin de ce module, le nom de la classe et la propriété
de vue ``MaterialColor`` sont écrits dans les documents (``GuiDocument.xml``) ; ils ne changent
jamais. Le ViewProvider est le seul à écrire la couleur diffuse de ``ShapeAppearance``.
Le panneau de tâche est importé à l'édition seulement (il importe ce module).
"""

from __future__ import annotations

from typing import Any, Final

from freecad.menuiserie import icon_path
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.features.freecad_types import HIDDEN, DocumentObject
from freecad.menuiserie.features.library import get_library

ViewObject = Any
Color = tuple[float, ...]

ICON: Final = "Menuiserie_WoodPart.svg"
MATERIAL_COLOR: Final = "MaterialColor"
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

    Sans état propre (``dumps`` renvoie ``None``) : la couleur est dans ``MaterialColor``.
    """

    def __init__(self, vobj: ViewObject) -> None:
        vobj.Proxy = self
        _ensure_material_color(vobj)
        _update_material_color(vobj.Object, vobj)

    def attach(self, vobj: ViewObject) -> None:
        """Garde le ViewObject (non enregistré) pour ``finishRestoring``."""
        self.vobj = vobj

    def getIcon(self) -> str:
        """Icône de l'arbre : celle de la commande « Pièce de bois »."""
        return icon_path(ICON)

    def updateData(self, obj: DocumentObject, prop: str) -> None:
        """Nouveau matériau (hors restauration) : sa couleur est enregistrée puis affichée."""
        if prop == "MaterialId" and "Restore" not in obj.State:
            _update_material_color(obj, obj.ViewObject)

    def onChanged(self, vobj: ViewObject, prop: str) -> None:
        """La couleur enregistrée est reportée sur la couleur diffuse affichée."""
        if prop == MATERIAL_COLOR:
            _show_material_color(vobj)

    def finishRestoring(self) -> None:
        """Recrée ``MaterialColor`` si le document est antérieur, puis l'affiche."""
        vobj = getattr(self, "vobj", None)
        if vobj is None:
            return
        _ensure_material_color(vobj)
        _show_material_color(vobj)

    def dumps(self) -> None:
        """Proxy sans état : rien à enregistrer."""
        return None

    def loads(self, state: object) -> None:
        """Proxy sans état : rien à relire."""
        del state

    def setEdit(self, vobj: ViewObject, mode: int) -> bool | None:
        """Mode 0 : panneau de tâche de la pièce ; les autres modes restent à FreeCAD."""
        if mode != 0:
            return None
        from freecad.menuiserie.gui.task_panels.wood_part import start_editing

        return start_editing(vobj.Object)

    def unsetEdit(self, vobj: ViewObject, mode: int) -> bool | None:
        """Fin du mode 0 : le panneau est fermé."""
        del vobj
        if mode != 0:
            return None
        from freecad.menuiserie.gui.task_panels.wood_part import finish_editing

        finish_editing()
        return True

    def doubleClicked(self, vobj: ViewObject) -> bool:
        """Double-clic dans l'arbre ou la vue 3D : édition de la pièce dans le panneau."""
        return bool(vobj.Document.setEdit(vobj.Object, 0))


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


def _show_material_color(vobj: ViewObject) -> None:
    """Couleur diffuse de chaque matériau d'affichage = ``MaterialColor`` (transparence et
    autres champs inchangés) ; rien n'est écrit si elle est déjà affichée."""
    wanted = _to_bytes(vobj.MaterialColor)
    appearance = list(vobj.ShapeAppearance)
    if all(_to_bytes(material.DiffuseColor) == wanted for material in appearance):
        return
    for material in appearance:
        alpha = tuple(material.DiffuseColor)[3:]
        material.DiffuseColor = _from_bytes(wanted) + alpha
    vobj.ShapeAppearance = appearance
