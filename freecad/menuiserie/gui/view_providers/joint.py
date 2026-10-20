# SPDX-License-Identifier: LGPL-2.1-or-later
"""Affichage des assemblages : icône de leur type, pièces rapportées (tourillons) couleur hêtre.

Contrat de persistance (ADR 0003) : le chemin de ce module et le nom de la classe sont écrits
dans les documents (``GuiDocument.xml``) ; ils ne changent jamais. La couleur est posée à la
création puis enregistrée par FreeCAD avec le ViewObject.
"""

from __future__ import annotations

from typing import Any, Final

from freecad.menuiserie import icon_path
from freecad.menuiserie.features.joints.base import JointFeature
from freecad.menuiserie.features.library import get_library
from freecad.menuiserie.gui.part_appearance import Rgb, show_diffuse

ViewObject = Any

BEECH_ID: Final = "hetre"
BEECH_COLOR: Final = (0xD9, 0xB4, 0x8A)  # #D9B48A, si la bibliothèque n'a pas de hêtre
FALLBACK_ICON: Final = "menuiserie.svg"


class ViewProviderJoint:
    """ViewProvider commun aux assemblages. Chemin de module figé (ADR 0003), sans état."""

    def __init__(self, vobj: ViewObject) -> None:
        vobj.Proxy = self
        show_diffuse(vobj, beech_color())

    def attach(self, vobj: ViewObject) -> None:
        """Garde le ViewObject (non enregistré) pour l'icône."""
        self.vobj = vobj

    def getIcon(self) -> str:
        """Icône de la commande du type : ``Menuiserie_<type>.svg``."""
        obj = getattr(getattr(self, "vobj", None), "Object", None)
        proxy = getattr(obj, "Proxy", None)
        if not isinstance(proxy, JointFeature):
            return icon_path(FALLBACK_ICON)
        return icon_path(joint_icon(proxy))

    def dumps(self) -> None:
        """Proxy sans état : rien à enregistrer."""
        return None

    def loads(self, state: object) -> None:
        """Proxy sans état : rien à relire."""
        del state


def joint_icon(proxy: JointFeature) -> str:
    """Nom du fichier d'icône d'un type d'assemblage (le même que celui de sa commande)."""
    return f"Menuiserie_{proxy.KIND.value}.svg"


def beech_color() -> Rgb:
    """Couleur du hêtre de la bibliothèque, à défaut ``#D9B48A``."""
    beech = get_library().find(BEECH_ID)
    return beech.color if beech is not None else BEECH_COLOR
