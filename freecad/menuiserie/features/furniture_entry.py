# SPDX-License-Identifier: LGPL-2.1-or-later
"""Entrées et sorties d'objets dans le Std Part d'un ensemble (EN-e, ADR 0038, critères E1 à E3).

FreeCAD déplace avec un objet toute sa **fermeture de liens** (pièce usinée, assemblages, pièces
assemblées, objet cité par une expression, source d'une pièce en bois) : on range donc un
sous-ensemble avant de poser ses liaisons, on défait ses liaisons avant de le sortir, et une pièce
assemblée à une pièce qui reste ne peut pas sortir seule (:func:`stays`). Les positions globales de
tout ce que FreeCAD range ainsi sont conservées (:func:`_relocate`). Ni transaction ni recalcul :
c'est à l'appelant de les faire.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

import FreeCAD as App

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.notice import Notice
from freecad.menuiserie.features.distance import is_distance
from freecad.menuiserie.features.freecad_types import (
    Document,
    DocumentObject,
    placement_expression,
)
from freecad.menuiserie.features.furniture import (
    furniture_of,
    is_furniture,
    origin_of,
    writing,
)
from freecad.menuiserie.features.furniture_container import (
    is_std_part,
    std_part_of,
)
from freecad.menuiserie.features.furniture_plan import (
    EntryNoticeKind,
    bundle,
    closure,
    staying,
)
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.features.joints.base import is_joint
from freecad.menuiserie.features.machined_part import is_machined_part
from freecad.menuiserie.features.placement import local_placement
from freecad.menuiserie.features.shaped_part import is_timber

__all__ = [
    "EntryNoticeKind",
    "adopt",
    "dissolve",
    "leave",
    "positioned",
    "stays",
    "taken_along",
    "write_placement",
]

_STAYS: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "« {label} » est assemblée à une pièce qui reste dans l'ensemble : elle reste dans son Std "
    "Part (elle n'est plus membre de l'ensemble).",
)


_KEPT: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Le Std Part « {part} » est conservé : il contient encore {labels}.",
)


# --- Déplacements entre conteneurs ------------------------------------------------------------


def taken_along(members: Sequence[DocumentObject]) -> list[Notice]:
    """Avertissements des pièces **libres** (membres d'aucun ensemble) liées à un des ``members``
    par un assemblage, une Distance ou une formule : FreeCAD les range avec lui dans le Std Part
    sans qu'elles deviennent membres (à appeler avant :func:`adopt`)."""
    pieces = [obj for obj in members if not is_furniture(obj)]
    allowed = {item.Name for obj in pieces for item in bundle(obj)}
    found: dict[str, Notice] = {}
    for piece in pieces:
        for other in closure(piece).values():
            if is_timber(other) and other.Name not in allowed and furniture_of(other) is None:
                params = {"label": str(other.Label), "other": str(piece.Label)}
                found.setdefault(other.Name, Notice(EntryNoticeKind.TAKEN_ALONG, params))
    return list(found.values())


def positioned(obj: DocumentObject) -> bool:
    """Objet géométrique dont le ``Placement`` est à garder quand FreeCAD le change de conteneur :
    tout sauf l'ensemble, la pièce usinée, l'assemblage et la Distance (leur position suit leur
    brute) et l'origine : ses plans et axes (``App::Plane``, ``App::Line`` et ``App::Point`` en
    FreeCAD 1.1, ``App::OriginFeature`` n'existe plus) ne sont jamais dans le groupe d'un
    Std Part."""
    return (
        "Placement" in obj.PropertiesList
        and obj.isDerivedFrom("App::GeoFeature")
        and obj.TypeId != "App::Origin"
        and not (is_furniture(obj) or is_machined_part(obj) or is_joint(obj) or is_distance(obj))
    )


def write_placement(obj: DocumentObject, placement: App.Placement) -> None:
    """Écrit le ``Placement`` de ``obj``, sans réaction de l'atelier si c'est un de ses objets."""
    if getattr(obj, "Proxy", None) is not None:
        with writing(obj):
            obj.Placement = placement
    else:
        obj.Placement = placement


def _depth(obj: DocumentObject) -> int:
    count, parent = 0, obj.getParentGeoFeatureGroup()
    while parent is not None:
        count, parent = count + 1, parent.getParentGeoFeatureGroup()
    return count


def _kept_places(doc: Document) -> dict[str, App.Placement]:
    """Position globale des objets de ``doc`` que FreeCAD pourrait ranger ailleurs avec ceux qu'on
    déplace (pièces, Std Parts, source d'une pièce en bois, corps d'un autre atelier) : à la
    racine ou dans un Std Part, sans expression sur leur ``Placement``."""
    found = {}
    for obj in doc.Objects:
        parent = obj.getParentGeoFeatureGroup()
        inside = parent is None or is_std_part(parent)
        if inside and positioned(obj) and placement_expression(obj) is None:
            found[obj.Name] = obj.getGlobalPlacement()
    return found


def _relocate(objects: Sequence[DocumentObject], target: DocumentObject | None) -> None:
    """Range ``objects`` dans ``target`` (``None`` : racine) en gardant la position globale de tout
    ce que FreeCAD range avec eux (brutes, Std Parts, source des pièces en bois : leur ``Placement``
    est relu dans le nouveau repère), sauf si une expression pilote leur ``Placement``."""
    if not objects:
        return
    doc = objects[0].Document
    kept = _kept_places(doc)
    for obj in objects:
        current = obj.getParentGeoFeatureGroup()
        if current == target:
            continue
        if target is not None:
            target.addObject(obj)
        elif current is not None:
            current.removeObject(obj)
    moved = sorted((doc.getObject(name) for name in kept), key=_depth)  # conteneurs d'abord
    for obj in moved:
        parent = obj.getParentGeoFeatureGroup()
        base = parent.getGlobalPlacement() if parent is not None else App.Placement()
        if not obj.getGlobalPlacement().isSame(kept[obj.Name], 1e-9):
            write_placement(obj, local_placement(kept[obj.Name], base))


def _shift_content(part: DocumentObject, shift: App.Vector) -> None:
    """Brutes et Std Parts de ``part`` décalés de ``-shift`` (le Std Part prend l'``Origin``)."""
    for obj in list(part.Group):
        if is_timber(obj) or is_std_part(obj):
            placement = obj.Placement
            obj.Placement = App.Placement(placement.Base - shift, placement.Rotation)


def _nest(sub: DocumentObject, container: DocumentObject) -> None:
    """Range le Std Part du sous-ensemble ``sub`` dans ``container`` et fait passer son
    ``Origin`` dans le ``Placement`` du Std Part (E3) : ses pièces gardent leur place. Le Std Part
    peut être déjà tourné : sa ``Base`` prend alors ``R · Origin`` et le contenu est décalé de
    ``-Origin`` dans son propre repère."""
    part = std_part_of(sub)
    if part is None:  # ensemble ancien sans Std Part (E5) : son Origin porte sa position
        return
    _relocate([part], container)
    origin = origin_of(sub)
    shift = App.Vector(origin.x, origin.y, origin.z)
    if shift.Length == 0:
        return
    with writing(sub):
        sub.Origin = App.Vector()
    rotation = part.Placement.Rotation  # Std Part déjà tourné : l'Origin passe tournée dans la Base
    part.Placement = App.Placement(part.Placement.Base + rotation.multVec(shift), rotation)
    _shift_content(part, shift)


def adopt(furniture: DocumentObject, members: Sequence[DocumentObject]) -> None:
    """Range les ``members`` (brutes et sous-ensembles) dans le Std Part de ``furniture`` : pièces
    avec leur pièce usinée et leurs assemblages, sous-ensembles avec leur Std Part (E1 à E3).
    Sans effet pour un ensemble ancien sans Std Part (E5). Les liaisons sont posées ensuite."""
    part = std_part_of(furniture)
    if part is None:
        return
    pieces = [obj for obj in members if not is_furniture(obj)]
    for sub in (obj for obj in members if is_furniture(obj)):
        _nest(sub, part)
    _relocate([item for obj in pieces for item in bundle(obj)], part)


def stays(members: Sequence[DocumentObject]) -> set[str]:
    """Noms des pièces de ``members`` qui ne peuvent pas sortir de leur Std Part : leur fermeture
    de liens contient un membre de l'ensemble (ou l'ensemble) qui reste. Une pièce assemblée à une
    pièce libre sort avec elle."""
    leaving = {item.Name for obj in members for item in bundle(obj)}
    pieces = [obj for obj in members if not is_furniture(obj)]
    return {name for name, found in staying(pieces, leaving).items() if found}


def _holder(obj: DocumentObject) -> DocumentObject | None:
    """Std Part dans lequel ``obj`` est rangé (pour un sous-ensemble : celui de son parent)."""
    if is_furniture(obj):
        part = std_part_of(obj)
        return None if part is None else part.getParentGeoFeatureGroup()
    return obj.getParentGeoFeatureGroup()


def leave(members: Sequence[DocumentObject]) -> list[str]:
    """Sort les ``members`` de leur Std Part, dans le conteneur de ce Std Part, à la même position
    globale (E2) ; renvoie les messages traduits des pièces qui restent dedans (:func:`stays`).
    Appelé après le retrait des liaisons et des propriétés de membre."""
    found = [(obj, _holder(obj)) for obj in members]
    holders = [(obj, holder) for obj, holder in found if holder is not None]
    inside = [obj for obj, holder in holders if is_std_part(holder)]
    kept = stays(inside)
    moving = [obj for obj in inside if obj.Name not in kept]
    for holder in {h.Name: h for obj, h in holders if is_std_part(h)}.values():
        mine = [obj for obj in moving if _holder(obj) == holder]
        _relocate([item for obj in mine for item in bundle(obj)], holder.getParentGeoFeatureGroup())
    return [translated(_STAYS, {"label": str(obj.Label)}) for obj in inside if obj.Name in kept]


def dissolve(furniture: DocumentObject) -> list[str]:
    """Suppression de ``furniture`` (après la sortie de ses membres, :func:`leave`) : son Std Part
    est supprimé s'il ne contient plus que l'ensemble ; sinon il est conservé (pièces restées
    dedans, objets de l'utilisateur) et le message traduit le dit. L'ensemble, sorti du Std Part,
    est supprimé ensuite par l'appelant."""
    part = std_part_of(furniture)
    if part is None:
        return []
    rest = [o for o in part.Group if o != furniture and o.TypeId != "App::Origin"]
    if rest:
        labels = ", ".join(f"« {obj.Label} »" for obj in rest)
        return [translated(_KEPT, {"part": str(part.Label), "labels": labels})]
    part.Document.removeObject(part.Name)
    return []
