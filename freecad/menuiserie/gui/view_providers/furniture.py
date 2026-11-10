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

from freecad.menuiserie.features.distance import distances_of
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.furniture import is_furniture
from freecad.menuiserie.features.furniture_bindings import common_furniture, members_of
from freecad.menuiserie.features.furniture_container import std_part_of
from freecad.menuiserie.features.furniture_members import (
    detach_members,
    release_furniture,
    release_repeat_links,
)
from freecad.menuiserie.features.furniture_view import shown_object
from freecad.menuiserie.features.i18n import report_warning
from freecad.menuiserie.features.joints.base import is_joint
from freecad.menuiserie.gui.view_providers.deletion import in_group_deletion, inside_group
from freecad.menuiserie.gui.view_providers.no_geometry import NoGeometryView
from freecad.menuiserie.gui.view_providers.wood_part import PanelEditing

ViewObject = Any

ICON: Final = "Menuiserie_Furniture.svg"


class ViewProviderFurniture(NoGeometryView, PanelEditing):
    """ViewProvider de l'ensemble. Chemin de module figé (ADR 0003), sans état enregistré."""

    ICON = ICON

    def claimChildren(self) -> list[DocumentObject]:
        """Membres (pièce usinée à la place de sa brute), sous-ensembles et assemblages dont
        les deux pièces sont membres."""
        obj = getattr(getattr(self, "vobj", None), "Object", None)
        return furniture_children(obj) if is_furniture(obj) else []

    def open_panel(self, vobj: ViewObject) -> bool | None:
        """Mode 0 (double-clic) : panneau de tâche de l'ensemble."""
        from freecad.menuiserie.gui.task_panels.furniture import start_editing

        return start_editing(vobj.Object)

    def canDelete(self, obj: DocumentObject) -> bool:
        """Vrai pour les objets qui dépendent de l'ensemble **de l'intérieur** : ses membres (et
        sous-ensembles), ses Distances gardées et son Std Part. Leurs liens sont retirés par
        :meth:`onDelete` : FreeCAD n'ouvre pas son avertissement « dépendances » pour eux. Autre
        objet (liste de débit, expression ou lien de l'utilisateur) : avertissement habituel."""
        furniture = getattr(getattr(self, "vobj", None), "Object", None)
        if not is_furniture(furniture):
            return False
        return (
            obj in members_of(furniture)
            or obj in distances_of(furniture)
            or obj == std_part_of(furniture)
        )

    def onDelete(self, vobj: ViewObject, subelements: object) -> bool:
        """Suppression dans l'interface : liaisons de l'atelier et propriétés de membre retirées
        de chaque membre, dans la transaction de la suppression ; aucune expression ne vise
        plus l'ensemble. Son Std Part est supprimé avec lui s'il est vide, conservé sinon (avec
        un avertissement) ; les messages vont dans la vue rapport (ADR 0017). Ses copies de
        répétition sont dissociées (:func:`.release_repeat_links`).

        Groupe supprimé avec son contenu (:mod:`.deletion`) : rien n'est supprimé ni déplacé ici
        (la boucle de FreeCAD s'en charge) ; seuls les membres rangés hors de ce groupe perdent
        leurs liaisons, pour qu'aucune expression ne vise plus l'ensemble supprimé."""
        furniture = vobj.Object
        if in_group_deletion(subelements):
            release_repeat_links(furniture)
            group = furniture.getParentGroup()
            outside = [m for m in members_of(furniture) if not inside_group(m, group)]
            if outside:
                detach_members(outside)
            return True
        for message in release_furniture(furniture):
            report_warning(message)
        return True


def _pieces_below(furniture: DocumentObject) -> list[DocumentObject]:
    """Pièces de ``furniture`` et de ses sous-ensembles (sans les ensembles)."""
    found: list[DocumentObject] = []
    for member in members_of(furniture):
        found.extend(_pieces_below(member) if is_furniture(member) else [member])
    return found


def furniture_children(furniture: DocumentObject) -> list[DocumentObject]:
    """Enfants de l'ensemble dans l'arbre : membres visibles, assemblages dont l'ensemble est le
    plus proche contenant leurs deux pièces (même au travers d'un sous-ensemble), puis
    Distances gardées."""
    members = members_of(furniture)
    joints = {
        parent.Name: parent
        for piece in _pieces_below(furniture)
        for parent in piece.InList
        if is_joint(parent)
        and parent.HostPart is not None
        and parent.GuestPart is not None
        and common_furniture(parent.HostPart, parent.GuestPart) == furniture
    }
    return [
        *(shown_object(member) for member in members),
        *(joints[n] for n in sorted(joints)),
        *distances_of(furniture),
    ]
