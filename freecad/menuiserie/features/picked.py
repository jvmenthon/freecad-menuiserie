# SPDX-License-Identifier: LGPL-2.1-or-later
"""Élément (face, arête, sommet) sélectionné avant de lancer « Pièce de bois » (J6d, ADR 0011).

``gui/selection.py`` lit la sélection de l'interface et construit des :class:`PickedElement` ;
tout le reste (formes, conteneur, ensemble) se lit ici, sans ``FreeCADGui``, donc dans
``freecadcmd``. Rien n'est jamais modifié dans les objets sélectionnés.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

from freecad.menuiserie.core.geometry import Vec3
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.furniture import furniture_of, is_furniture
from freecad.menuiserie.features.i18n import translated

__all__ = ["PickedElement", "container_of", "furniture_candidate"]

ELEMENT_PATTERN: Final = re.compile(r"(Face|Edge|Vertex)[1-9][0-9]*$")
STD_PART: Final = "App::Part"
_LINK_TYPES: Final = ("App::Link", "App::LinkElement", "App::LinkGroup")
_ELEMENT_LABEL: Final = QT_TRANSLATE_NOOP("Menuiserie", "{element} de « {label} »")


@dataclass(frozen=True)
class PickedElement:
    """Sous-élément sélectionné : objet racine, chemin complet (``Meuble.Cote.Face3``) qui finit
    par le nom de l'élément, et point cliqué en coordonnées globales (``None`` : sélection par
    script)."""

    root: DocumentObject
    subname: str
    point: Vec3 | None = None

    @property
    def element(self) -> str:
        """Nom de l'élément (``Face3``), vide si c'est un objet entier."""
        return self.subname.rsplit(".", 1)[-1]

    def is_subelement(self) -> bool:
        """Vrai pour ``FaceN``, ``EdgeN`` ou ``VertexN``."""
        return ELEMENT_PATTERN.fullmatch(self.element) is not None

    @property
    def owner_subname(self) -> str:
        """Chemin de l'objet qui porte l'élément (``Meuble.Cote.``)."""
        return self.subname[: len(self.subname) - len(self.element)]

    def owner(self) -> DocumentObject:
        """Objet qui porte l'élément (le dernier du chemin)."""
        # getSubObject() renvoie la forme d'un objet Part, pas l'objet : on prend le chemin.
        return _path_objects(self)[-1]

    def label(self) -> str:
        """« Face3 de « Côté gauche » » (libellé de FreeCAD)."""
        owner = self.owner()
        params = {"element": self.element, "label": str(owner.Label)}
        return translated(_ELEMENT_LABEL, params)


def _path_objects(element: PickedElement) -> list[DocumentObject]:
    """Objets du chemin de sélection, de la racine à l'objet qui porte l'élément."""
    return list(element.root.getSubObjectList(element.owner_subname) or [element.root])


def container_of(element: PickedElement) -> DocumentObject | None:
    """Std Part (``App::Part``) le plus profond du chemin de ``element``, sans traverser un
    ``App::Link`` : un élément vu à travers un lien ne place jamais la pièce dans l'original.
    Jamais un ``PartDesign::Body`` ni un assemblage (types distincts). ``None`` : le document."""
    container = None
    for obj in _path_objects(element):
        if obj.TypeId in _LINK_TYPES:
            break
        if obj.TypeId == STD_PART:
            container = obj
    return container


def furniture_candidate(element: PickedElement) -> DocumentObject | None:
    """Ensemble dont l'élément sélectionné est un membre : celui de la pièce de bois ou en bois
    (ou de la brute de la pièce usinée) la plus profonde du chemin, ou l'ensemble lui-même ;
    ``None`` sinon. L'ensemble n'est pas cherché derrière un lien."""
    # Import différé : la pièce usinée lit la pièce en bois, dont le repère lit ce module.
    from freecad.menuiserie.features.machined_part import is_machined_part
    from freecad.menuiserie.features.shaped_part import is_timber

    for obj in reversed(_path_objects(element)):
        if obj.TypeId in _LINK_TYPES:
            return None
        if is_furniture(obj):
            return obj
        blank = obj.Base if is_machined_part(obj) else obj
        if is_timber(blank):
            return furniture_of(blank)
    return None
