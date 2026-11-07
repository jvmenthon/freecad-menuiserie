# SPDX-License-Identifier: LGPL-2.1-or-later
"""Std Part de l'ensemble (EN-e, ADR 0038, critères E1 à E3).

Chaque ensemble est rangé, dès sa création, dans un Std Part (``App::Part``) avec ses pièces
(brutes et usinées), ses assemblages et ses Distances ; les rotations et déplacements à la souris
écrivent son ``Placement``. Un sous-ensemble a son propre Std Part, rangé dans celui de son
parent : son ``Origin`` y vaut (0, 0, 0), sa position est le ``Placement.Base`` de ce Std Part,
et les liaisons du parent portent sur lui (:func:`carrier`).

FreeCAD déplace avec un objet toute sa **fermeture de liens** (pièce usinée, assemblages, pièces
assemblées, objet cité par une expression) : on range donc un sous-ensemble avant de poser ses
liaisons, on défait ses liaisons avant de le sortir, et une pièce assemblée à une pièce qui reste
ne peut pas sortir seule (:func:`stays`). Les positions globales sont conservées. Ni transaction
ni recalcul : c'est à l'appelant de les faire.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

import FreeCAD as App

from freecad.menuiserie.core.geometry import Vec3
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.features.distance import is_distance
from freecad.menuiserie.features.freecad_types import (
    Document,
    DocumentObject,
    expressions_of,
    placement_expression,
)
from freecad.menuiserie.features.furniture import (
    create_furniture,
    furniture_of,
    is_furniture,
    origin_of,
    writing,
)
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.features.joints.base import is_joint
from freecad.menuiserie.features.machined_part import is_machined_part, machined_part_of
from freecad.menuiserie.features.placement import local_placement
from freecad.menuiserie.features.shaped_part import is_timber

__all__ = [
    "STD_PART",
    "adopt",
    "carrier",
    "check_assembled",
    "create_with_std_part",
    "dissolve",
    "guide_container",
    "is_std_part",
    "leave",
    "member_expressions",
    "own_std_part",
    "placement_container",
    "position_of",
    "positioned",
    "scopes",
    "set_member_expression",
    "std_part_of",
    "write_placement",
]

STD_PART: Final = "App::Part"
LABEL: Final = QT_TRANSLATE_NOOP("Menuiserie", "{label} (Std Part)")
_ASSEMBLED: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "« {label} » est assemblée à « {other} », qui n'entre pas avec elle dans l'ensemble.",
)
_STAYS: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "« {label} » est assemblée à une pièce qui reste dans l'ensemble : elle reste dans son Std "
    "Part (elle n'est plus membre de l'ensemble).",
)


_KEPT: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Le Std Part « {part} » est conservé : il contient encore {labels}.",
)


def is_std_part(obj: object) -> bool:
    """Vrai si ``obj`` est un Std Part (``App::Part``)."""
    return getattr(obj, "TypeId", None) == STD_PART


def std_part_of(furniture: DocumentObject) -> DocumentObject | None:
    """Std Part qui contient l'ensemble ``furniture`` (le sien), ``None`` s'il n'en a pas."""
    parent = furniture.getParentGeoFeatureGroup()
    return parent if is_std_part(parent) else None


def _sub_std_part(obj: DocumentObject, furniture: DocumentObject) -> bool:
    """Vrai si ``obj`` est le Std Part d'un sous-ensemble **membre** de ``furniture`` (et non un
    ``App::Part`` de l'utilisateur)."""
    return is_std_part(obj) and any(
        is_furniture(item) and furniture_of(item) == furniture for item in obj.Group
    )


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
    ours = [o for o in others if _workshop(o) and not is_furniture(o)]
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


def guide_container(part: DocumentObject) -> DocumentObject | None:
    """Conteneur dont les objets guident l'aimant de la pièce ``part`` : les Std Parts d'ensemble
    sont transparents, la pièce voit aussi ce qui entoure son ensemble (E6)."""
    container = part.getParentGeoFeatureGroup()
    while is_std_part(container) and any(is_furniture(obj) for obj in container.Group):
        container = container.getParentGeoFeatureGroup()
    return container


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


# --- Déplacements entre conteneurs ------------------------------------------------------------


def _bundle(obj: DocumentObject) -> list[DocumentObject]:
    """Objets qui suivent un membre : sa brute, sa pièce usinée et ses assemblages ; le Std Part
    d'un sous-ensemble (qui contient tout le reste)."""
    if is_furniture(obj):
        part = std_part_of(obj)
        return [] if part is None else [part]
    machined = machined_part_of(obj) if is_timber(obj) else None
    joints = [parent for parent in obj.InList if is_joint(parent)]
    return [obj, *([] if machined is None else [machined]), *joints]


def _workshop(obj: DocumentObject) -> bool:
    return (
        is_timber(obj)
        or is_machined_part(obj)
        or is_joint(obj)
        or is_furniture(obj)
        or is_distance(obj)
    )


def _closure(start: DocumentObject) -> dict[str, DocumentObject]:
    """Objets de l'atelier liés à ``start`` (dans les deux sens, de proche en proche), par nom :
    ce que FreeCAD range avec lui."""
    found: dict[str, DocumentObject] = {}
    todo = [start]
    while todo:
        obj = todo.pop()
        if obj.Name not in found and _workshop(obj):
            found[obj.Name] = obj
            todo.extend([*obj.InList, *obj.OutList])
    return found


def _linked_members(
    pieces: Sequence[DocumentObject], allowed: set[str], target: DocumentObject | None
) -> DocumentObject | None:
    """Membre d'un autre ensemble (ou ensemble) que FreeCAD rangerait avec ``pieces`` : un objet
    de leur fermeture de liens qui n'est pas dans ``allowed`` et qui n'est pas ``target`` ou l'un
    de ses membres."""
    for piece in pieces:
        for other in _closure(piece).values():
            owner = other if is_furniture(other) else furniture_of(other)
            if other.Name not in allowed and owner is not None and owner != target:
                return other
    return None


def check_assembled(
    members: Sequence[DocumentObject], target: DocumentObject | None = None
) -> None:
    """Refuse (``ValueError`` traduite, rien n'est modifié) l'entrée de pièces assemblées à un
    membre d'un autre ensemble : FreeCAD les rangerait avec lui. ``target`` : ensemble qui les
    reçoit (ses membres sont permis), ``None`` pour un nouvel ensemble. Une pièce assemblée à une
    pièce libre est rangée avec elle, à la même position."""
    pieces = [obj for obj in members if not is_furniture(obj)]
    allowed = {item.Name for obj in pieces for item in _bundle(obj)}
    for sub in (obj for obj in members if is_furniture(obj)):  # un sous-ensemble entre en entier
        part = std_part_of(sub)
        allowed.add(sub.Name)
        allowed |= {obj.Name for obj in _content(part)} if part is not None else set()
    other = _linked_members(pieces, allowed, target)
    if other is not None:
        label = next(p.Label for p in pieces if other.Name in _closure(p))
        raise ValueError(translated(_ASSEMBLED, {"label": str(label), "other": str(other.Label)}))


def _content(part: DocumentObject) -> list[DocumentObject]:
    """Objets d'un Std Part, ceux de ses Std Parts compris."""
    found: list[DocumentObject] = []
    for obj in part.Group:
        found.append(obj)
        if is_std_part(obj):
            found.extend(_content(obj))
    return found


def positioned(obj: DocumentObject) -> bool:
    """Objet géométrique dont le ``Placement`` est à garder quand FreeCAD le change de conteneur :
    tout sauf l'ensemble, la pièce usinée, l'assemblage et la Distance (leur position suit leur
    brute) et les éléments d'une origine."""
    return (
        "Placement" in obj.PropertiesList
        and obj.isDerivedFrom("App::GeoFeature")
        and not obj.isDerivedFrom("App::OriginFeature")
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
        if (parent is None or is_std_part(parent)) and positioned(obj):
            if placement_expression(obj) is None:
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
    _relocate([item for obj in pieces for item in _bundle(obj)], part)


def stays(members: Sequence[DocumentObject]) -> set[str]:
    """Noms des pièces de ``members`` qui ne peuvent pas sortir de leur Std Part : leur fermeture
    de liens contient un membre de l'ensemble (ou l'ensemble) qui reste. Une pièce assemblée à une
    pièce libre sort avec elle."""
    leaving = {item.Name for obj in members for item in _bundle(obj)}
    pieces = [obj for obj in members if not is_furniture(obj)]
    return {obj.Name for obj in pieces if _linked_members([obj], leaving, None) is not None}


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
        _relocate(
            [item for obj in mine for item in _bundle(obj)], holder.getParentGeoFeatureGroup()
        )
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
