# SPDX-License-Identifier: LGPL-2.1-or-later
"""Std Part de l'ensemble (EN-e, ADR 0038, critères E1 à E3).

Chaque ensemble est rangé, dès sa création, dans un Std Part (``App::Part``) avec ses pièces
(brutes et usinées), ses assemblages et ses Distances ; les rotations et déplacements à la souris
écrivent son ``Placement``. Un sous-ensemble a son propre Std Part, rangé dans celui de son
parent : son ``Origin`` y vaut (0, 0, 0), sa position est le ``Placement.Base`` de ce Std Part,
et les liaisons du parent portent sur lui (:func:`carrier`).

Les entrées et sorties d'objets dans le Std Part sont dans :mod:`.furniture_entry`.
"""

from __future__ import annotations

from typing import Final

import FreeCAD as App

from freecad.menuiserie.core.geometry import Vec3
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.features.distance import is_distance
from freecad.menuiserie.features.freecad_types import (
    Document,
    DocumentObject,
    expressions_of,
)
from freecad.menuiserie.features.furniture import (
    create_furniture,
    furniture_of,
    is_furniture,
    origin_of,
)
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.features.joints.base import is_joint
from freecad.menuiserie.features.machined_part import is_machined_part
from freecad.menuiserie.features.shaped_part import is_timber

__all__ = [
    "STD_PART",
    "carried_furniture",
    "carrier",
    "create_with_std_part",
    "follow_label",
    "guide_container",
    "is_std_part",
    "is_workshop",
    "member_expressions",
    "outer_container",
    "own_std_part",
    "placement_container",
    "position_of",
    "scopes",
    "set_member_expression",
    "std_part_of",
]

STD_PART: Final = "App::Part"
LABEL: Final = QT_TRANSLATE_NOOP("Menuiserie", "{label} (Std Part)")


def is_std_part(obj: object) -> bool:
    """Vrai si ``obj`` est un Std Part (``App::Part``)."""
    return getattr(obj, "TypeId", None) == STD_PART


def std_part_of(furniture: DocumentObject) -> DocumentObject | None:
    """Std Part qui contient l'ensemble ``furniture`` (le sien), ``None`` s'il n'en a pas."""
    parent = furniture.getParentGeoFeatureGroup()
    return parent if is_std_part(parent) else None


def is_workshop(obj: DocumentObject) -> bool:
    """Vrai si ``obj`` est un objet de l'atelier (pièce, usinée, assemblage, ensemble, Distance)."""
    return (
        is_timber(obj)
        or is_machined_part(obj)
        or is_joint(obj)
        or is_furniture(obj)
        or is_distance(obj)
    )


def _sub_std_part(obj: DocumentObject, furniture: DocumentObject) -> bool:
    """Vrai si ``obj`` est le Std Part d'un sous-ensemble **membre** de ``furniture`` (et non un
    ``App::Part`` de l'utilisateur)."""
    return is_std_part(obj) and any(
        is_furniture(item) and furniture_of(item) == furniture for item in obj.Group
    )


def carried_furniture(obj: object) -> DocumentObject | None:
    """Ensemble que porte le Std Part ``obj`` (celui qui y est rangé directement), ``None`` si
    ``obj`` n'est pas le Std Part d'un ensemble."""
    if not is_std_part(obj):
        return None
    return next((item for item in obj.Group if is_furniture(item)), None)  # type: ignore[attr-defined]


def own_std_part(furniture: DocumentObject) -> DocumentObject | None:
    """Std Part **propre** à l'ensemble : celui qui ne contient que l'ensemble, ses membres (pièces,
    pièces usinées, assemblages, Distances), les Std Parts de ses sous-ensembles et les objets que
    FreeCAD y range avec ses pièces (source d'une pièce en bois). ``None`` sans Std Part (ancien
    document) ou si le Std Part contient autre chose (objet de l'utilisateur, autre ensemble, Std
    Part de l'utilisateur) : le tourner ou le déplacer entraînerait ces objets."""
    part = std_part_of(furniture)
    if part is None:
        return None
    others = [o for o in part.Group if o != furniture and o.TypeId != "App::Origin"]
    ours = [o for o in others if is_workshop(o) and not is_furniture(o)]
    for obj in others:
        if obj in ours:
            continue
        linked = any(obj in item.OutList for item in ours)  # source tirée dans le Std Part
        if not (_sub_std_part(obj, furniture) or (linked and not is_std_part(obj))):
            return None
    return part


def placement_container(obj: DocumentObject) -> DocumentObject | None:
    """Conteneur où se lit la position de ``obj`` : pour un ensemble qui a son Std Part, le
    conteneur de ce Std Part ; sinon celui de ``obj``."""
    if is_furniture(obj):
        part = std_part_of(obj)
        if part is not None:
            return part.getParentGeoFeatureGroup()
    return obj.getParentGeoFeatureGroup()


def scopes(furniture: DocumentObject) -> tuple[DocumentObject | None, ...]:
    """Conteneurs d'où un membre peut entrer dans ``furniture`` : celui de son Std Part, ou son
    Std Part lui-même (pièce restée dedans) ; son seul conteneur sans Std Part."""
    part = std_part_of(furniture)
    if part is None:
        return (furniture.getParentGeoFeatureGroup(),)
    return (part.getParentGeoFeatureGroup(), part)


def position_of(furniture: DocumentObject) -> Vec3:
    """Coin (avant, gauche, bas) de l'ensemble dans le repère du conteneur de son Std Part :
    ``Placement.Base`` du Std Part, plus ``Origin`` (nul pour un sous-ensemble)."""
    origin = origin_of(furniture)
    part = std_part_of(furniture)
    if part is None:
        return origin
    point = part.Placement.multVec(App.Vector(origin.x, origin.y, origin.z))
    return Vec3(point.x, point.y, point.z)


def outer_container(container: DocumentObject | None) -> DocumentObject | None:
    """``container`` remonté au-delà des Std Parts d'ensemble (transparents) ; un Std Part de
    l'utilisateur ou la racine (``None``) sont gardés."""
    while carried_furniture(container) is not None:
        container = container.getParentGeoFeatureGroup()  # type: ignore[union-attr]
    return container


def guide_container(part: DocumentObject) -> DocumentObject | None:
    """Conteneur dont les objets guident l'aimant de la pièce ``part`` : les Std Parts d'ensemble
    sont transparents, la pièce voit aussi ce qui entoure son ensemble (E6)."""
    return outer_container(part.getParentGeoFeatureGroup())


# --- Liaisons portées par le Std Part d'un sous-ensemble --------------------------------------


def carrier(obj: DocumentObject, prop: str) -> DocumentObject:
    """Objet qui porte l'expression de ``prop`` : le Std Part pour le ``Placement`` d'un
    sous-ensemble, ``obj`` sinon."""
    if is_furniture(obj) and prop.split(".")[0] == "Placement":
        part = std_part_of(obj)
        if part is not None:
            return part
    return obj


def member_expressions(obj: DocumentObject) -> dict[str, str]:
    """Expressions de ``obj``, avec celles du ``Placement`` de son Std Part s'il est un
    sous-ensemble."""
    found = expressions_of(obj)
    part = std_part_of(obj) if is_furniture(obj) else None
    if part is not None:
        found.update({p: t for p, t in expressions_of(part).items() if p.startswith("Placement")})
    return found


def set_member_expression(obj: DocumentObject, prop: str, text: str | None) -> None:
    """Pose (ou retire, ``None``) l'expression de ``prop`` sur son porteur (:func:`carrier`)."""
    carrier(obj, prop).setExpression(prop, text)


# --- Création ---------------------------------------------------------------------------------


def follow_label(furniture: DocumentObject) -> None:
    """Le libellé du Std Part de ``furniture`` suit le sien (« {libellé} (Std Part) »), pour un
    ensemble renommé par l'utilisateur."""
    part = std_part_of(furniture)
    if part is None:
        return
    wanted = translated(LABEL, {"label": str(furniture.Label)})
    if part.Label != wanted:
        part.Label = wanted


def create_with_std_part(
    doc: Document, box: object, origin: Vec3, label: str, outer: DocumentObject | None
) -> DocumentObject:
    """Crée l'ensemble vide et son Std Part, rangé dans ``outer`` (``None`` : racine)."""
    furniture = create_furniture(doc, box, origin, label, None)  # type: ignore[arg-type]
    part = doc.addObject(STD_PART, "Part")
    part.Label = translated(LABEL, {"label": str(furniture.Label)})
    if outer is not None:
        outer.addObject(part)
    part.addObject(furniture)
    return furniture
