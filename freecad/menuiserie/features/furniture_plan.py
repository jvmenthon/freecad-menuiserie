# SPDX-License-Identifier: LGPL-2.1-or-later
"""Où ranger des pièces qui entrent dans un ensemble quand des assemblages les relient à des pièces
qui restent ailleurs (ADR 0038, ADR 0046), critère ``core/assembly_scope`` partagé avec le panneau
« Structure ».

FreeCAD range avec un objet toute sa **fermeture de liens** (:func:`closure`) : deux pièces
assemblées doivent donc être dans le même ensemble. Si l'endroit demandé séparerait un assemblage,
:func:`plan_entry` renvoie l'endroit cohérent le plus proche (l'ensemble de la pièce qui reste,
s'il est dans la même branche) ou refuse (``ValueError`` traduite). Lecture seule.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Final

from freecad.menuiserie.core.assembly_scope import (
    CREATE_STAYS,
    GOES_TO,
    STAYS_IN,
    destination,
    keeps_assembly,
)
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.notice import Notice
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.furniture import furniture_of, is_furniture
from freecad.menuiserie.features.furniture_container import is_std_part, is_workshop, std_part_of
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.features.joints.base import is_joint
from freecad.menuiserie.features.machined_part import machined_part_of
from freecad.menuiserie.features.shaped_part import is_timber

__all__ = [
    "EntryNoticeKind",
    "Placement",
    "bundle",
    "chain_of",
    "check_assembled",
    "closure",
    "content",
    "is_membership",
    "plan_entry",
    "redirection_notice",
    "refusal",
    "split_creation",
]

_ASSEMBLED: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "« {label} » est assemblée à « {other} », qui est dans un autre ensemble : aucun rangement "
    "cohérent ne les réunit. Déplacez aussi « {other} », ou supprimez d'abord l'assemblage.",
)
_TAKEN_ALONG: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "« {label} » est liée à « {other} » (assemblage, Distance ou formule) : FreeCAD la range avec "
    "elle dans le Std Part de l'ensemble, sans qu'elle en devienne membre.",
)


class EntryNoticeKind(Enum):
    """Nature d'un avertissement à l'entrée de pièces dans le Std Part d'un ensemble."""

    TAKEN_ALONG = "TakenAlong"
    REDIRECTED = "Redirected"
    STAYED = "Stayed"
    CREATE_STAYED = "CreateStayed"

    @property
    def template(self) -> str:
        """Gabarit français marqué pour la traduction."""
        return {
            "TakenAlong": _TAKEN_ALONG,
            "Redirected": GOES_TO,
            "Stayed": STAYS_IN,
            "CreateStayed": CREATE_STAYS,
        }[self.value]


# --- Fermeture de liens -----------------------------------------------------------------------


def bundle(obj: DocumentObject) -> list[DocumentObject]:
    """Objets qui suivent un membre : sa brute, sa pièce usinée et ses assemblages ; le Std Part
    d'un sous-ensemble (qui contient tout le reste)."""
    if is_furniture(obj):
        part = std_part_of(obj)
        return [] if part is None else [part]
    machined = machined_part_of(obj) if is_timber(obj) else None
    joints = [parent for parent in obj.InList if is_joint(parent)]
    return [obj, *([] if machined is None else [machined]), *joints]


def content(part: DocumentObject) -> list[DocumentObject]:
    """Objets d'un Std Part, ceux de ses Std Parts compris."""
    found: list[DocumentObject] = []
    for obj in part.Group:
        found.append(obj)
        if is_std_part(obj):
            found.extend(content(obj))
    return found


def is_membership(obj: DocumentObject, other: DocumentObject) -> bool:
    """Vrai si le lien entre ``obj`` et ``other`` vient des liaisons de l'atelier : un membre et
    son ensemble, ou deux membres du même ensemble (leurs expressions se citent). Ces liens se
    défont avant tout changement de Std Part (``detach_members``, ``relink_remaining``) et ne
    sont pas des dépendances de la pièce ; un assemblage, lui, reste un lien."""
    owner = furniture_of(obj)
    return bool(
        owner == other
        or furniture_of(other) == obj
        or (owner is not None and owner == furniture_of(other))
    )


def closure(start: DocumentObject) -> dict[str, DocumentObject]:
    """Objets de l'atelier liés à ``start`` (dans les deux sens, de proche en proche), par nom :
    ce que FreeCAD range avec lui, une fois les liaisons à son ensemble défaites."""
    found: dict[str, DocumentObject] = {}
    todo = [start]
    while todo:
        obj = todo.pop()
        if obj.Name not in found and is_workshop(obj):
            found[obj.Name] = obj
            todo.extend(o for o in [*obj.InList, *obj.OutList] if not is_membership(obj, o))
    return found


def chain_of(furniture: DocumentObject | None) -> tuple[str, ...]:
    """Noms de ``furniture`` et des ensembles qui le contiennent, du plus proche au plus éloigné
    (vide pour ``None``)."""
    names: list[str] = []
    while furniture is not None and furniture.Name not in names:
        names.append(furniture.Name)
        furniture = furniture_of(furniture)
    return tuple(names)


def staying(
    pieces: Sequence[DocumentObject], leaving: set[str]
) -> dict[str, list[tuple[DocumentObject, tuple[str, ...]]]]:
    """Pour chaque pièce de ``pieces`` (par nom), les objets de sa fermeture de liens qui ne sont
    pas dans ``leaving`` et appartiennent à un ensemble (ou en sont un), avec la chaîne de
    celui-ci : ce que FreeCAD rangerait avec elle."""
    found: dict[str, list[tuple[DocumentObject, tuple[str, ...]]]] = {}
    for piece in pieces:
        found[piece.Name] = []
        for other in closure(piece).values():
            owner = other if is_furniture(other) else furniture_of(other)
            if other.Name not in leaving and owner is not None:
                found[piece.Name].append((other, chain_of(owner)))
    return found


# --- Plan d'entrée ----------------------------------------------------------------------------


@dataclass(frozen=True)
class Placement:
    """Où va une pièce (ou un sous-ensemble) qui entre : ``dest``, chaîne d'ensembles (nom vide :
    l'ensemble à créer). ``other`` : la pièce assemblée qui impose un autre endroit que celui
    demandé, ``None`` si l'endroit demandé convient."""

    obj: DocumentObject
    dest: tuple[str, ...]
    other: DocumentObject | None = None


def plan_entry(members: Sequence[DocumentObject], wanted: Sequence[str]) -> list[Placement]:
    """Endroit de chaque objet de ``members`` qu'on veut ranger dans les ensembles ``wanted`` (noms,
    du plus proche au plus éloigné ; ``""`` : un ensemble à créer). Un sous-ensemble entre en
    entier. Une pièce assemblée à une pièce libre est rangée avec elle, à la même position (elle ne
    compte pas). ``ValueError`` traduite, rien n'étant modifié, s'il n'y a aucun rangement
    cohérent."""
    pieces = [obj for obj in members if not is_furniture(obj)]
    allowed = {item.Name for obj in pieces for item in bundle(obj)}
    for sub in (obj for obj in members if is_furniture(obj)):
        part = std_part_of(sub)
        allowed.add(sub.Name)
        allowed |= {obj.Name for obj in content(part)} if part is not None else set()
    linked = staying(pieces, allowed)
    placements: list[Placement] = []
    for obj in members:
        pairs = linked.get(obj.Name, [])
        dest = destination(wanted, [chain for _other, chain in pairs], ignore_free=True)
        broken = next((o for o, chain in pairs if not keeps_assembly(wanted, chain)), None)
        if dest is None:
            raise refusal(Placement(obj, tuple(wanted), broken))
        placements.append(Placement(obj, dest, broken))
    return placements


def refusal(placement: Placement) -> ValueError:
    """Refus traduit : ``placement.obj`` est assemblée à une pièce d'un autre ensemble."""
    other = placement.other
    params = {"label": str(placement.obj.Label), "other": str(other.Label if other else "")}
    return ValueError(translated(_ASSEMBLED, params))


def check_assembled(
    members: Sequence[DocumentObject], target: DocumentObject | None = None
) -> None:
    """Comme :func:`plan_entry` mais sans redirection : ``ValueError`` traduite si une pièce serait
    rangée ailleurs que dans ``target`` (``None`` : un nouvel ensemble)."""
    wanted = chain_of(target) if target is not None else ("",)
    for placement in plan_entry(members, wanted):
        if placement.dest != wanted and placement.other is not None:
            raise refusal(placement)


def redirection_notice(
    placement: Placement,
    target: DocumentObject | None,
    home: DocumentObject,
    kind: EntryNoticeKind,
) -> Notice:
    """Avertissement : ``placement.obj`` est assemblée à ``placement.other`` et va (ou reste) dans
    ``home`` au lieu de ``target`` (``None`` : le nouvel ensemble) ; ``kind`` dit si elle y va
    (``REDIRECTED``) ou y reste (``STAYED``, ``CREATE_STAYED``)."""
    params = {
        "piece": str(placement.obj.Label),
        "other": str(placement.other.Label if placement.other is not None else ""),
        "dest": str(home.Label),
        "target": str(target.Label) if target is not None else "",
    }
    return Notice(kind, params)


def split_creation(
    placements: Sequence[Placement], wanted: tuple[str, ...], parent: DocumentObject | None
) -> tuple[list[DocumentObject], list[Notice]]:
    """Objets qui entrent dans l'ensemble à créer (endroit demandé) et avertissements de ceux qui
    restent dans ``parent`` ; ``ValueError`` si un objet irait ailleurs ou si aucun n'entre."""
    entering = [pl.obj for pl in placements if pl.dest == wanted]
    staying = [pl for pl in placements if pl.dest != wanted]
    for pl in staying:
        if parent is None or pl.dest != wanted[1:]:
            raise refusal(pl)
    notices = [
        redirection_notice(pl, None, parent, EntryNoticeKind.CREATE_STAYED)
        for pl in staying
        if parent is not None
    ]
    if not entering:
        raise ValueError(translated(notices[0].template, notices[0].params))
    return entering, notices
