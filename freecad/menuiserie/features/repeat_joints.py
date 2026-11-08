# SPDX-License-Identifier: LGPL-2.1-or-later
"""Assemblages recopiés par une répétition (ADR 0043, lot R-b2, spécification § 3, Q4).

Quand ``CopyJoints`` est vrai, chaque assemblage « d'origine » dont une pièce est une source de la
répétition est recréé pour chaque copie :

- A : les deux pièces sont des sources → assemblage entre les copies de même rang ;
- B : une seule pièce est une source → assemblage entre la copie et l'autre pièce, rôles
  conservés (la traverse reçoit un tenon par copie) ;
- C : aucune pièce n'est une source → rien (l'assemblage n'est pas une origine) ;
- D : l'assemblage enfant est créé même s'il est infaisable : la vérification existante le
  signale au recalcul, la copie reste modifiable.

Un assemblage enfant porte ``RepeatJoint`` (lien vers l'assemblage d'origine, lecture seule) et
**partage sa configuration** : chaque propriété de paramètre du type (``PARAMS``, noms de
:func:`.joints.base.property_name`) est une expression ``{origine}.{propriété}``, en lecture seule
dans l'éditeur. Changer l'origine change donc les enfants. Retrait (:func:`unlink_joint`) :
expressions retirées, valeurs gardées, propriété ``RepeatJoint`` retirée, modes d'édition rendus.

Les enfants se créent et se suppriment hors recalcul, dans la transaction de l'API. Contrat de
persistance (ADR 0003) : le nom de la propriété ``RepeatJoint`` ne change jamais.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import fields
from typing import Final

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.features import schema
from freecad.menuiserie.features.drag_joints import remove_joints
from freecad.menuiserie.features.freecad_types import (
    READ_ONLY,
    DocumentObject,
    expressions_of,
    restoring_or_undoing,
)
from freecad.menuiserie.features.joints.base import is_joint, property_name
from freecad.menuiserie.features.joints.factories import create_joint
from freecad.menuiserie.features.repeat import copies_of, sources_of
from freecad.menuiserie.features.schema import PropertySpec, set_editor_mode

__all__ = [
    "PROPERTY",
    "children_of",
    "joint_removed",
    "joints_of_part",
    "origin_of",
    "param_paths",
    "restored",
    "unlink_joint",
    "unlink_part_joints",
    "update_joints",
]

PROPERTY: Final = "RepeatJoint"
_SPEC: Final = PropertySpec(
    PROPERTY,
    "App::PropertyLink",
    "Répétition",
    QT_TRANSLATE_NOOP(
        "App::Property",
        "Assemblage d'origine dont celui-ci partage la configuration (répétition).",
    ),
    mode=READ_ONLY,
)
_DERIVED: Final = "joint_derived"  # champ fourni par le document, pas par une propriété


def origin_of(joint: DocumentObject) -> DocumentObject | None:
    """Assemblage d'origine de ``joint`` s'il est un enfant d'une répétition, ``None`` sinon."""
    origin: DocumentObject | None = getattr(joint, PROPERTY, None)
    return origin


def param_paths(joint: DocumentObject) -> list[str]:
    """Propriétés de paramètres du type de ``joint`` (``PARAMS``), celles que l'enfant partage."""
    names = (
        property_name(item.name)
        for item in fields(joint.Proxy.PARAMS)
        if not item.metadata.get(_DERIVED)
    )
    return [name for name in names if name in joint.PropertiesList]


def _unique(objects: Iterable[DocumentObject]) -> list[DocumentObject]:
    """Les objets sans doublon (un objet figure autant de fois dans ``InList`` qu'il cite), triés
    par nom : ordre stable d'un recalcul à l'autre."""
    return sorted({obj.Name: obj for obj in objects}.values(), key=lambda obj: obj.Name)


def joints_of_part(part: DocumentObject) -> list[DocumentObject]:
    """Assemblages dont ``part`` (pièce brute) est l'hôte ou l'invitée."""
    return _unique(
        joint
        for joint in part.InList
        if is_joint(joint) and part in (joint.HostPart, joint.GuestPart)
    )


def children_of(origin: DocumentObject) -> list[DocumentObject]:
    """Assemblages enfants de l'assemblage d'origine ``origin``."""
    return _unique(
        joint for joint in origin.InList if is_joint(joint) and origin_of(joint) == origin
    )


def _bind(child: DocumentObject, origin: DocumentObject) -> None:
    """Lie ``child`` à ``origin`` : lien, expressions de tous les paramètres, lecture seule."""
    schema.add_missing_properties(child, (_SPEC,))
    setattr(child, PROPERTY, origin)
    schema.apply_editor_modes(child, (_SPEC,))
    for path in param_paths(child):
        child.setExpression(path, f"{origin.Name}.{path}")
        set_editor_mode(child, path, READ_ONLY)


def restored(joint: DocumentObject) -> None:
    """Assemblage rouvert : les paramètres d'un enfant redeviennent en lecture seule (les modes
    du schéma du type les ont rendus modifiables)."""
    if origin_of(joint) is None:
        return
    schema.apply_editor_modes(joint, (_SPEC,))
    for path in param_paths(joint):
        set_editor_mode(joint, path, READ_ONLY)


def unlink_joint(joint: DocumentObject) -> None:
    """Dissocie l'assemblage enfant ``joint`` : expressions retirées (valeurs gardées), lien
    ``RepeatJoint`` retiré, paramètres de nouveau modifiables. Sans effet sur un autre
    assemblage."""
    origin = origin_of(joint)
    if origin is None:
        return
    for path, text in expressions_of(joint).items():
        if path in param_paths(joint) and text.startswith(f"{origin.Name}."):
            joint.setExpression(path, None)
    joint.removeProperty(PROPERTY)
    schema.apply_editor_modes(joint, joint.Proxy.specs())


def unlink_part_joints(part: DocumentObject) -> None:
    """Dissocie les assemblages enfants qui touchent la copie ``part`` (copie dissociée)."""
    for joint in joints_of_part(part):
        unlink_joint(joint)


def joint_removed(origin: DocumentObject) -> None:
    """Assemblage d'origine supprimé (``unsetupObject``) : ses enfants sont dissociés, ils
    gardent leurs valeurs et aucune expression ne vise un objet absent. Rien pendant une
    annulation, un rétablissement ou une restauration."""
    if restoring_or_undoing(origin):
        return
    for child in children_of(origin):
        unlink_joint(child)


def _origins(repeat: DocumentObject) -> list[DocumentObject]:
    """Assemblages d'origine : ceux d'une source de ``repeat`` qui ne sont pas déjà des enfants."""
    found: list[DocumentObject] = []
    for source in sources_of(repeat):
        found.extend(joint for joint in joints_of_part(source) if origin_of(joint) is None)
    return _unique(found)


def _repeat_children(repeat: DocumentObject) -> list[DocumentObject]:
    """Assemblages enfants qui touchent une copie liée de ``repeat``."""
    found: list[DocumentObject] = []
    for copy in copies_of(repeat):
        found.extend(joint for joint in joints_of_part(copy) if origin_of(joint) is not None)
    return _unique(found)


def _counterpart(
    part: DocumentObject | None,
    rank: int,
    by_rank: dict[tuple[str, int], DocumentObject],
    sources: set[str],
) -> DocumentObject | None:
    """Pièce qui remplace ``part`` dans l'assemblage du rang ``rank`` : sa copie si c'est une
    source (``None`` si elle n'existe pas ou plus), elle-même sinon."""
    if part is None or part.Name not in sources:
        return part
    return by_rank.get((part.Name, rank))


def _create_child(
    origin: DocumentObject, host: DocumentObject, guest: DocumentObject
) -> DocumentObject | None:
    """Assemblage enfant de ``origin`` entre ``host`` et ``guest`` ; ``None`` s'il existe déjà."""
    if any((child.HostPart, child.GuestPart) == (host, guest) for child in children_of(origin)):
        return None
    child = create_joint(
        type(origin.Proxy),
        origin.Document,
        host,
        guest,
        origin.Proxy.params(origin),
        same_part=host == guest,
    )
    _bind(child, origin)
    return child


def update_joints(
    repeat: DocumentObject, *, enabled: bool, ranks: Iterable[int]
) -> list[DocumentObject]:
    """Met les assemblages enfants de ``repeat`` au réglage ``CopyJoints`` = ``enabled`` : faux,
    tous sont supprimés (avec leurs pièces usinées devenues sans assemblage) ; vrai, ils sont
    créés pour les copies des rangs ``ranks`` (une copie dissociée ou supprimée n'en reçoit pas).
    Renvoie les assemblages créés. Ni transaction ni recalcul."""
    if not enabled:
        remove_joints(_repeat_children(repeat))
        return []
    by_rank = {(copy.RepeatSource.Name, copy.RepeatIndex): copy for copy in copies_of(repeat)}
    sources = {source.Name for source in sources_of(repeat)}
    origins = _origins(repeat)
    created: list[DocumentObject] = []
    for rank in ranks:
        for origin in origins:
            host = _counterpart(origin.HostPart, rank, by_rank, sources)
            guest = _counterpart(origin.GuestPart, rank, by_rank, sources)
            child = None if host is None or guest is None else _create_child(origin, host, guest)
            if child is not None:
                created.append(child)
    return created
