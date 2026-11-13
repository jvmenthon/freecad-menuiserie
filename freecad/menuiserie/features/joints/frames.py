# SPDX-License-Identifier: LGPL-2.1-or-later
"""Repère commun de deux pièces rangées dans des conteneurs différents (ADR 0054).

Chaque ensemble et chaque sous-ensemble a son Std Part (ADR 0038) : deux pièces d'un même
ensemble peuvent donc avoir des conteneurs différents. Le plan d'un assemblage se calcule dans le
repère du conteneur de l'hôte ; l'invitée y est ramenée par son placement global. Entre pièces
d'un même conteneur, rien ne change (``Placement`` local).
"""

from __future__ import annotations

from typing import Final

import FreeCAD as App

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.i18n import translated

__all__ = ["frame_containers", "placement_in_frame_of", "related_containers"]

_STD_PART: Final = "App::Part"
OTHER_CONTAINER: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Les deux pièces doivent être dans le même conteneur, ou chacune dans un Std Part ou à la "
    "racine (corps : même conteneur seulement).",
)


def _chain(obj: DocumentObject) -> list[DocumentObject] | None:
    """Conteneurs de ``obj`` du plus proche à la racine ; ``None`` si l'un n'est pas un Std Part."""
    chain: list[DocumentObject] = []
    holder = obj.getParentGeoFeatureGroup()
    while holder is not None:
        if holder.TypeId != _STD_PART:
            return None
        chain.append(holder)
        holder = holder.getParentGeoFeatureGroup()
    return chain


def related_containers(first: DocumentObject, second: DocumentObject) -> bool:
    """Vrai si ``first`` et ``second`` ont le même conteneur, ou si tous leurs conteneurs sont des
    Std Part (une pièce hors de tout Std Part est à la racine) : le repère global les relie. Faux
    si l'un est dans un autre type de conteneur (corps PartDesign…) et pas dans le même."""
    if bool(first.getParentGeoFeatureGroup() == second.getParentGeoFeatureGroup()):
        return True
    return _chain(first) is not None and _chain(second) is not None


def placement_in_frame_of(obj: DocumentObject, reference: DocumentObject) -> App.Placement:
    """Placement de ``obj`` dans le repère du conteneur de ``reference`` : son ``Placement`` s'ils
    ont le même conteneur, sinon son placement global ramené dans ce repère."""
    holder = reference.getParentGeoFeatureGroup()
    if obj.getParentGeoFeatureGroup() == holder:
        return obj.Placement
    base = holder.getGlobalPlacement() if holder is not None else App.Placement()
    return base.inverse() * obj.getGlobalPlacement()


def frame_containers(*objects: DocumentObject) -> list[DocumentObject]:
    """Std Part qui contiennent les pièces ``objects`` (eux et leurs parents), sans doublon,
    quand les conteneurs diffèrent ; vide s'ils sont communs : le recalcul suit leur
    ``Placement`` (un déplacement de Std Part ne touche pas les pièces qu'il contient)."""
    first = objects[0].getParentGeoFeatureGroup()
    if all(obj.getParentGeoFeatureGroup() == first for obj in objects):
        return []
    found: list[DocumentObject] = []
    for obj in objects:
        for holder in _chain(obj) or []:
            if holder not in found:
                found.append(holder)
    return found


def refusal(first: DocumentObject, second: DocumentObject) -> str | None:
    """Message traduit si les conteneurs ne sont pas apparentés, ``None`` sinon."""
    return None if related_containers(first, second) else translated(OTHER_CONTAINER)
