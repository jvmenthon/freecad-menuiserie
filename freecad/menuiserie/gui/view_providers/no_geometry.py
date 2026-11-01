# SPDX-License-Identifier: LGPL-2.1-or-later
"""Socle des ViewProviders d'objets sans géométrie (liste de débit, distance gardée, ensemble) :
icône de l'arbre, un seul mode d'affichage vide, ViewObject gardé pour l'arbre.

Mixin sans état placé avant la base concrète (``class ViewProviderX(NoGeometryView, Base)``) :
FreeCAD n'enregistre que le chemin de la classe concrète (ADR 0003), ce module peut donc
évoluer sans toucher aux documents."""

from __future__ import annotations

from typing import Any, ClassVar

from freecad.menuiserie import icon_path

ViewObject = Any


class NoGeometryView:
    """Méthodes communes aux ViewProviders sans géométrie ; ``ICON`` est le fichier d'icône de
    l'arbre, fourni par la sous-classe."""

    ICON: ClassVar[str]

    def __init__(self, vobj: ViewObject) -> None:
        vobj.Proxy = self

    def attach(self, vobj: ViewObject) -> None:
        """Garde le ViewObject (non enregistré) pour l'arbre et ``canDelete``."""
        self.vobj = vobj

    def getIcon(self) -> str:
        """Icône de l'arbre, celle de la commande qui crée l'objet."""
        return icon_path(self.ICON)

    def getDisplayModes(self, vobj: ViewObject) -> list[str]:
        """Aucune géométrie : un seul mode d'affichage, vide."""
        del vobj
        return ["Default"]

    def getDefaultDisplayMode(self) -> str:
        """Mode d'affichage unique."""
        return "Default"
