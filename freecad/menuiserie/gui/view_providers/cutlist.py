# SPDX-License-Identifier: LGPL-2.1-or-later
"""Affichage de la liste de débit vivante (J2f, ADR 0013) : icône de la commande, aperçu au
double-clic (issue #76), suppression d'une pièce sans l'avertissement « objets référencés » de
FreeCAD.

Contrat de persistance (ADR 0003) : le chemin de ce module et le nom de la classe sont écrits
dans les documents (``GuiDocument.xml``) ; ils ne changent jamais. Sans état enregistré. Ouvert
sans l'atelier, le document n'a pas ce ViewProvider : l'objet est alors affiché comme un objet
ordinaire, sans conséquence.
"""

from __future__ import annotations

from typing import Any, Final

import FreeCADGui as Gui

from freecad.menuiserie import icon_path
from freecad.menuiserie.features.freecad_types import DocumentObject, StatelessProxy

ViewObject = Any

ICON: Final = "Menuiserie_CutList.svg"


class ViewProviderCutList(StatelessProxy):
    """ViewProvider de la liste de débit vivante. Chemin de module figé (ADR 0003)."""

    def __init__(self, vobj: ViewObject) -> None:
        vobj.Proxy = self

    def attach(self, vobj: ViewObject) -> None:
        """Garde le ViewObject (non enregistré) pour ``canDelete``."""
        self.vobj = vobj

    def getIcon(self) -> str:
        """Icône de l'arbre : celle de la commande « Liste de débit »."""
        return icon_path(ICON)

    def getDisplayModes(self, vobj: ViewObject) -> list[str]:
        """Aucune géométrie : un seul mode d'affichage, vide."""
        del vobj
        return ["Default"]

    def getDefaultDisplayMode(self) -> str:
        """Mode d'affichage unique."""
        return "Default"

    def doubleClicked(self, vobj: ViewObject) -> bool:
        """Double-clic : aperçu de la liste sur sa portée (vide : tout le document), comme la
        commande « Aperçu de la liste de débit » ; un refus de l'api est signalé de même.
        Refusé si un panneau de tâche est ouvert (sa transaction serait validée par le
        recalcul de l'aperçu)."""
        if Gui.Control.activeDialog():
            return False
        from freecad.menuiserie.gui.commands.base import report_refusal
        from freecad.menuiserie.gui.commands.cutlist import show_cut_list_preview

        obj = vobj.Object
        try:
            show_cut_list_preview(obj.Document, list(obj.Scope) or None)
        except (TypeError, ValueError) as error:
            report_refusal(str(error))
        return True

    def canDelete(self, obj: DocumentObject) -> bool:
        """Vrai pour un objet que la liste lit ou dont elle limite la portée : « Supprimer » ne
        montre pas l'avertissement « objets référencés » de FreeCAD (la liste n'est qu'un
        observateur et se recalcule sans l'objet). Autre objet : avertissement habituel."""
        cut_list = getattr(getattr(self, "vobj", None), "Object", None)
        if cut_list is None:
            return False
        return obj in cut_list.Sources or obj in cut_list.Scope
