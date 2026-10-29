# SPDX-License-Identifier: LGPL-2.1-or-later
"""Affichage de la pièce en bois (ADR 0020, D2, D4, D5) : icône d'objet, texture et couleur du
matériau, source rangée sous la pièce dans l'arbre, édition au double-clic.

Contrat de persistance (ADR 0003) : le chemin de ce module, le nom de la classe et la propriété de
vue ``MaterialColor`` sont écrits dans les documents (``GuiDocument.xml``) ; ils ne changent
jamais. Le ViewProvider est sans état enregistré. La texture et la couleur sont celles de la pièce
de bois (:class:`.MaterialViewProvider`) : la texture se projette dans le repère de la pièce, juste
sur les faces planes parallèles au fil, étirée sur le bois de bout et les surfaces gauches
(limite acceptée, ADR 0004). Le panneau de tâche est importé à l'édition seulement.
"""

from __future__ import annotations

from typing import Any, ClassVar, Final

from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.gui.view_providers.wood_part import MaterialViewProvider

ViewObject = Any

# Icône d'objet de l'arbre ; l'icône de la commande est « Menuiserie_ShapedPart.svg ».
ICON: Final = "Menuiserie_ShapedPartObject.svg"


class ViewProviderShapedPart(MaterialViewProvider):
    """ViewProvider de la pièce en bois. Chemin de module figé (ADR 0003, ADR 0020).

    Sans état enregistré (``dumps`` renvoie ``None``) : la couleur est dans ``MaterialColor``, les
    nœuds de texture sont recréés par ``attach``.
    """

    ICON_NAME: ClassVar[str] = ICON

    def claimChildren(self) -> list[DocumentObject]:
        """La source apparaît sous la pièce en bois dans l'arbre ; elle reste modifiable par
        double-clic (PartDesign, Sketcher)."""
        source = getattr(getattr(getattr(self, "vobj", None), "Object", None), "Source", None)
        return [source] if source is not None else []

    def open_panel(self, vobj: ViewObject) -> bool | None:
        """Mode 0 (double-clic dans l'arbre ou la vue 3D) : panneau de tâche de la pièce."""
        from freecad.menuiserie.gui.task_panels.shaped_part import start_editing

        return start_editing(vobj.Object)

    def canDelete(self, obj: DocumentObject) -> bool:
        """Vrai pour la source de la pièce : « Supprimer » ne montre pas l'avertissement « objets
        référencés » de FreeCAD, la pièce passe en erreur avec un message traduit (B8) et revient
        avec « Annuler ». Autre objet : avertissement habituel."""
        part = getattr(getattr(self, "vobj", None), "Object", None)
        return obj is not None and obj == getattr(part, "Source", None)

    def onDelete(self, vobj: ViewObject, subelements: object) -> bool:
        """Suppression de la pièce : la source est réaffichée (seule visibilité modifiée, ADR 0007
        et ADR 0020 décision 9)."""
        del subelements
        show_source(getattr(vobj.Object, "Source", None))
        return True


def show_source(source: DocumentObject | None) -> None:
    """Réaffiche la source d'une pièce en bois supprimée ; sans effet si elle a disparu."""
    if source is None:
        return
    try:
        source.Visibility = True
    except ReferenceError:  # source supprimée dans la même opération
        return
