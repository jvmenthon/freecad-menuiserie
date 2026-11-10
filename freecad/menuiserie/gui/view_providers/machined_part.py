# SPDX-License-Identifier: LGPL-2.1-or-later
"""Affichage de la pièce usinée (ADR 0006) : icône de la pièce de bois, couleur et texture de sa
brute, brute rangée sous elle dans l'arbre, édition de la brute au double-clic.

Contrat de persistance (ADR 0003) : le chemin de ce module et le nom de la classe sont écrits
dans les documents (``GuiDocument.xml``) ; ils ne changent jamais. Sans propriété de vue
propre : l'apparence est lue sur la brute à chaque recalcul de la pièce usinée (qui suit tout
changement de matériau ou de fil de la brute) et à la réouverture.
"""

from __future__ import annotations

from typing import Any

import FreeCADGui as Gui

from freecad.menuiserie import icon_path
from freecad.menuiserie.features.drag_joints import delete_machined_part
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.shaped_part import is_shaped_part, is_timber
from freecad.menuiserie.features.wood_part import is_wood_part
from freecad.menuiserie.gui import joint_choice
from freecad.menuiserie.gui.part_appearance import PartAppearance, material_color_of
from freecad.menuiserie.gui.view_providers.deletion import in_group_deletion
from freecad.menuiserie.gui.view_providers.wood_part import ICON, PanelEditing

ViewObject = Any

# Propriétés de la pièce usinée après lesquelles l'apparence de la brute est relue.
_REFRESHING_PROPERTIES = frozenset({"Shape", "Base"})


def selected_with_contents() -> set[str]:
    """Noms des objets sélectionnés et de tout ce que contiennent leurs groupes (Std Part
    d'ensemble supprimé avec son contenu) : ce que la suppression en cours emporte."""
    names: set[str] = set()
    pending = list(Gui.Selection.getSelection())
    while pending:
        obj = pending.pop()
        if obj.Name not in names:
            names.add(obj.Name)
            pending.extend(getattr(obj, "Group", ()))
    return names


class ViewProviderMachinedPart(PanelEditing):
    """ViewProvider de la pièce usinée. Chemin de module figé (ADR 0003), sans état enregistré."""

    def __init__(self, vobj: ViewObject) -> None:
        vobj.Proxy = self
        self._refresh(vobj)

    def attach(self, vobj: ViewObject) -> None:
        """Garde le ViewObject (non enregistré) et insère les nœuds de texture, inactifs."""
        self.vobj = vobj
        self._appearance = PartAppearance(vobj)

    def getIcon(self) -> str:
        """Icône de l'arbre : celle de la pièce de bois."""
        return icon_path(ICON)

    def claimChildren(self) -> list[DocumentObject]:
        """La brute apparaît sous sa pièce usinée dans l'arbre."""
        blank = getattr(self.vobj.Object, "Base", None)
        return [blank] if blank is not None else []

    def updateData(self, obj: DocumentObject, prop: str) -> None:
        """Forme recalculée ou brute changée (hors restauration) : apparence de la brute."""
        if prop in _REFRESHING_PROPERTIES and "Restore" not in obj.State:
            self._refresh(obj.ViewObject)

    def finishRestoring(self) -> None:
        """Réaffiche la texture de la bibliothèque locale ou la couleur de la brute."""
        vobj = getattr(self, "vobj", None)
        if vobj is not None:
            self._refresh(vobj)

    def open_panel(self, vobj: ViewObject) -> bool | None:
        """Mode 0 (double-clic) : panneau de tâche de la brute (ses cotes, son matériau, son
        fil, ou sa forme pour une pièce en bois) ; rien sans brute."""
        blank = getattr(vobj.Object, "Base", None)
        if is_shaped_part(blank):
            from freecad.menuiserie.gui.task_panels.shaped_part import start_editing as edit_shaped

            return edit_shaped(blank)
        if not is_wood_part(blank):
            return None
        from freecad.menuiserie.gui.task_panels.wood_part import start_editing

        return start_editing(blank, vobj.Object)

    def canDelete(self, obj: DocumentObject) -> bool:
        """Vrai pour un assemblage de la pièce usinée : « Supprimer » ne montre pas
        l'avertissement « objets référencés » de FreeCAD, la pièce usinée est recalculée sans
        sa coupe (FreeCAD retire le lien de ``Joints``). Autre objet : avertissement habituel."""
        machined = getattr(getattr(self, "vobj", None), "Object", None)
        return obj in getattr(machined, "Joints", ())

    def onDelete(self, vobj: ViewObject, subelements: object) -> bool:
        """Suppression d'une pièce usinée. Sans assemblage : normale (la brute est réaffichée).
        Avec assemblages : la fenêtre « assemblage lié » propose de les supprimer avec la pièce
        (une seule transaction, celle de FreeCAD) ou d'annuler. Faux si la suppression est
        refusée, et aussi quand la pièce vient d'être supprimée avec ses assemblages : FreeCAD ne
        doit pas supprimer un objet déjà détruit."""
        if in_group_deletion(subelements):
            return True  # Std Part supprimé avec son contenu : tout part, rien à demander
        return delete_machined_part(
            vobj.Object, joint_choice.choose_removal, selected_with_contents()
        )

    def _refresh(self, vobj: ViewObject) -> None:
        """Texture et couleur de la brute ; sans effet sans brute ou avant l'attachement."""
        appearance: PartAppearance | None = getattr(self, "_appearance", None)
        blank = getattr(vobj.Object, "Base", None)
        if appearance is not None and is_timber(blank):
            appearance.show(vobj, blank, material_color_of(blank))
