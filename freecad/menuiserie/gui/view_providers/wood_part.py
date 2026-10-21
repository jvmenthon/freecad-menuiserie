# SPDX-License-Identifier: LGPL-2.1-or-later
"""Affichage de la pièce de bois : icône, couleur et texture du matériau (ADR 0004), édition au
double-clic.

Contrat de persistance (ADR 0003) : le chemin de ce module, le nom de la classe et la propriété
de vue ``MaterialColor`` sont écrits dans les documents (``GuiDocument.xml``) ; ils ne changent
jamais. Le ViewProvider est le seul à écrire la couleur diffuse de ``ShapeAppearance`` : le
blanc de base quand la texture est affichée, sinon ``MaterialColor``. La texture n'est jamais
enregistrée : elle est recalculée depuis la bibliothèque locale. Le panneau de tâche est importé
à l'édition seulement (il importe ce module).
"""

from __future__ import annotations

from typing import Any, Final

import FreeCADGui as Gui

from freecad.menuiserie import icon_path
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.features.freecad_types import HIDDEN, DocumentObject
from freecad.menuiserie.features.library import get_library
from freecad.menuiserie.gui.part_appearance import (
    FALLBACK_DIFFUSE,
    MATERIAL_COLOR,
    PartAppearance,
    from_bytes,
    to_bytes,
)

ViewObject = Any
Color = tuple[float, ...]

ICON: Final = "Menuiserie_WoodPart.svg"
# Propriétés de la pièce dont dépend l'apparence (la projection ne dépend pas des cotes).
_APPEARANCE_PROPERTIES: Final = frozenset({"MaterialId", "GrainDirection"})
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
        self._appearance = PartAppearance(vobj)

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
        appearance: PartAppearance | None = getattr(self, "_appearance", None)
        if prop == MATERIAL_COLOR and appearance is not None:
            appearance.show_color(vobj, to_bytes(vobj.MaterialColor))

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

    def setEdit(self, vobj: ViewObject, mode: int) -> bool | None:
        """Mode 0 : panneau de tâche de la pièce ; les autres modes restent à FreeCAD."""
        if mode != 0:
            return None
        from freecad.menuiserie.gui.task_panels.wood_part import start_editing

        return start_editing(vobj.Object)

    def unsetEdit(self, vobj: ViewObject, mode: int) -> bool | None:
        """Fin du mode 0 : le panneau est fermé."""
        del vobj
        return end_panel_edit(mode)

    def doubleClicked(self, vobj: ViewObject) -> bool:
        """Double-clic dans l'arbre ou la vue 3D : édition de la pièce dans le panneau."""
        return edit_by_double_click(vobj)

    def _refresh(self, vobj: ViewObject) -> None:
        """Affiche la texture du matériau si elle est utilisable, sinon ``MaterialColor``.

        Sans effet tant que ``MaterialColor`` ou les nœuds de texture n'existent pas
        (attachement en cours) : ``__init__`` et ``finishRestoring`` rappellent cette méthode."""
        appearance: PartAppearance | None = getattr(self, "_appearance", None)
        if MATERIAL_COLOR in vobj.PropertiesList and appearance is not None:
            appearance.show(vobj, vobj.Object, to_bytes(vobj.MaterialColor))


def end_panel_edit(mode: int) -> bool | None:
    """Fin du mode d'édition 0 (``unsetEdit``) : le panneau de la pièce est fermé ; les autres
    modes restent à FreeCAD (``None``)."""
    if mode != 0:
        return None
    from freecad.menuiserie.gui.task_panels.base import finish_editing

    finish_editing()
    return True


def edit_by_double_click(vobj: ViewObject) -> bool:
    """Double-clic : mode d'édition 0 de ``vobj``. Refusé si un panneau de tâche est ouvert :
    ``setEdit`` quitterait d'abord l'édition en cours, fermant son panneau sans « OK » ni
    « Annuler »."""
    if Gui.Control.activeDialog():
        return False
    return bool(vobj.Document.setEdit(vobj.Object, 0))


def _ensure_material_color(vobj: ViewObject) -> None:
    """Ajoute ``MaterialColor`` (masquée) si elle manque, initialisée à la couleur diffuse."""
    if MATERIAL_COLOR in vobj.PropertiesList:
        return
    diffuse = _diffuse_color(vobj)
    vobj.addProperty("App::PropertyColor", MATERIAL_COLOR, "Matériau", _MATERIAL_COLOR_TOOLTIP)
    vobj.setEditorMode(MATERIAL_COLOR, HIDDEN)
    vobj.MaterialColor = from_bytes(to_bytes(diffuse))


def _update_material_color(obj: DocumentObject, vobj: ViewObject) -> None:
    """Couleur du matériau de la bibliothèque ; inconnu localement : valeur enregistrée gardée."""
    if MATERIAL_COLOR not in vobj.PropertiesList:
        return
    material = get_library().find(obj.MaterialId)
    if material is not None and to_bytes(vobj.MaterialColor) != material.color:
        vobj.MaterialColor = from_bytes(material.color)


def _diffuse_color(vobj: ViewObject) -> Color:
    """Couleur diffuse du premier matériau d'affichage ; gris clair si ``ShapeAppearance`` est
    vide (document altéré)."""
    appearance = vobj.ShapeAppearance
    if not appearance:
        return FALLBACK_DIFFUSE
    color: Color = tuple(appearance[0].DiffuseColor)
    return color
