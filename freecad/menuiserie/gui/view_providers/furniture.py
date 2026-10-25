# SPDX-License-Identifier: LGPL-2.1-or-later
"""Affichage de l'ensemble (J4c, critère P2) : icône, membres rangés dessous dans l'arbre,
panneau de tâche au double-clic, liaisons retirées avant la suppression.

Contrat de persistance (ADR 0003) : le chemin de ce module et le nom de la classe sont écrits
dans les documents (``GuiDocument.xml``) ; ils ne changent jamais. Sans état enregistré. Les
enfants de l'arbre sont calculés d'après ``InList`` (affichage seulement, ADR 0008) : le
document ne contient aucun lien de l'ensemble vers ses membres.
"""

from __future__ import annotations

from typing import Any, Final

from freecad.menuiserie import icon_path
from freecad.menuiserie.features.distance import distances_of
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.furniture import is_furniture
from freecad.menuiserie.features.furniture_bindings import members_of
from freecad.menuiserie.features.furniture_members import remove_members
from freecad.menuiserie.features.furniture_view import shown_object
from freecad.menuiserie.features.joints.base import is_joint
from freecad.menuiserie.gui.view_providers.wood_part import PanelEditing

ViewObject = Any

ICON: Final = "Menuiserie_Furniture.svg"


class ViewProviderFurniture(PanelEditing):
    """ViewProvider de l'ensemble. Chemin de module figé (ADR 0003), sans état enregistré."""

    def __init__(self, vobj: ViewObject) -> None:
        vobj.Proxy = self

    def attach(self, vobj: ViewObject) -> None:
        """Garde le ViewObject (non enregistré) pour l'arbre."""
        self.vobj = vobj

    def getIcon(self) -> str:
        """Icône de l'arbre : celle de la commande « Ensemble »."""
        return icon_path(ICON)

    def getDisplayModes(self, vobj: ViewObject) -> list[str]:
        """Aucune géométrie : un seul mode d'affichage, vide."""
        del vobj
        return ["Default"]

    def getDefaultDisplayMode(self) -> str:
        """Mode d'affichage unique."""
        return "Default"

    def claimChildren(self) -> list[DocumentObject]:
        """Membres (pièce usinée à la place de sa brute), sous-ensembles et assemblages dont
        les deux pièces sont membres."""
        obj = getattr(getattr(self, "vobj", None), "Object", None)
        return furniture_children(obj) if is_furniture(obj) else []

    def open_panel(self, vobj: ViewObject) -> bool | None:
        """Mode 0 (double-clic) : panneau de tâche de l'ensemble."""
        from freecad.menuiserie.gui.task_panels.furniture import start_editing

        return start_editing(vobj.Object)

    def onDelete(self, vobj: ViewObject, subelements: object) -> bool:
        """Suppression dans l'interface : liaisons de l'atelier et propriétés de membre retirées
        de chaque membre, dans la transaction de la suppression ; aucune expression ne vise
        plus l'ensemble."""
        del subelements
        members = members_of(vobj.Object)
        if members:
            remove_members(members)
        return True


def furniture_children(furniture: DocumentObject) -> list[DocumentObject]:
    """Enfants de l'ensemble dans l'arbre : membres visibles, assemblages internes, puis
    Distances gardées."""
    members = members_of(furniture)
    names = {member.Name for member in members}
    joints = {
        parent.Name: parent
        for member in members
        for parent in member.InList
        if is_joint(parent)
        and getattr(parent.HostPart, "Name", None) in names
        and getattr(parent.GuestPart, "Name", None) in names
    }
    return [
        *(shown_object(member) for member in members),
        *(joints[n] for n in sorted(joints)),
        *distances_of(furniture),
    ]
