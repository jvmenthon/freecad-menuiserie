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

from freecad.menuiserie import icon_path
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.i18n import report_warning
from freecad.menuiserie.features.machined_part import removal_refusal, show_blank
from freecad.menuiserie.features.wood_part import is_wood_part
from freecad.menuiserie.gui.part_appearance import PartAppearance, material_color_of
from freecad.menuiserie.gui.view_providers.wood_part import ICON, PanelEditing

ViewObject = Any

# Propriétés de la pièce usinée après lesquelles l'apparence de la brute est relue.
_REFRESHING_PROPERTIES = frozenset({"Shape", "Base"})


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
        fil) ; rien sans brute."""
        blank = getattr(vobj.Object, "Base", None)
        if not is_wood_part(blank):
            return None
        from freecad.menuiserie.gui.task_panels.wood_part import start_editing

        return start_editing(blank, vobj.Object)

    def onDelete(self, vobj: ViewObject, subelements: object) -> bool:
        """Suppression refusée (message dans la vue rapport) tant que la pièce porte des
        assemblages ; sinon la brute est réaffichée."""
        del subelements
        obj = vobj.Object
        refusal = removal_refusal(obj)
        if refusal is not None:
            report_warning(refusal)
            return False
        show_blank(getattr(obj, "Base", None))
        return True

    def _refresh(self, vobj: ViewObject) -> None:
        """Texture et couleur de la brute ; sans effet sans brute ou avant l'attachement."""
        appearance: PartAppearance | None = getattr(self, "_appearance", None)
        blank = getattr(vobj.Object, "Base", None)
        if appearance is not None and is_wood_part(blank):
            appearance.show(vobj, blank, material_color_of(blank))
