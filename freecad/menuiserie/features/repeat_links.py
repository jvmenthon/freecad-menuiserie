# SPDX-License-Identifier: LGPL-2.1-or-later
"""Liaison d'une copie à sa source par expressions natives (ADR 0043, comme l'ADR 0009).

Pour la copie de rang ``k`` de la source ``S`` d'une répétition ``R`` sur l'axe ``a`` :

- ``Length``, ``Width``, ``Thickness`` = celles de ``S`` ;
- ``Placement.Base.c`` = ``S.Placement.Base.c`` (+ ``k * (R.Reverse ? -1 : 1) * R.Step`` pour la
  seule composante ``c`` de l'axe) ; ``Placement.Rotation`` = celle de ``S`` ;
- matériau, sens du fil et surcotes : **expressions aussi** (FreeCAD accepte une expression sur une
  énumération). Choix vérifié dans FreeCAD 1.1 : à l'évaluation, ``Material`` appelle le proxy de
  la copie (``select_material``), qui recopie identifiant, catégorie et masse volumique ; le sens
  du fil et les surcotes, liés eux aussi, gardent la valeur de la source. Un changement de
  matériau de la source (éditeur de propriétés ou ``set_material``) suit donc sans autre code.
  Limite connue : le libellé de ``Material`` doit figurer dans la liste de la copie, qui est la
  bibliothèque locale, comme celle de la source.

Les expressions citent les objets par leur ``Name`` (stable), jamais par leur libellé. Elles sont
écrites par l'API dans la transaction en cours, jamais pendant un recalcul ni dans un autre objet
que la copie. Retrait (:func:`unlink_copy`) : seules les expressions qui citent la source ou la
répétition sont retirées, une formule de l'utilisateur sur la même propriété est laissée.
"""

from __future__ import annotations

from typing import Final

from freecad.menuiserie.core.repeat import RepeatAxis
from freecad.menuiserie.features.freecad_types import DocumentObject, expressions_of
from freecad.menuiserie.features.furniture import furniture_of, is_furniture
from freecad.menuiserie.features.furniture_bindings import members_of, rebind
from freecad.menuiserie.features.furniture_relink import bind_furniture
from freecad.menuiserie.features.i18n import report_warning
from freecad.menuiserie.features.repeat import (
    COPY_PROPERTY_NAMES,
    cites,
    copies_of,
    is_copy,
    is_inner_copy,
    is_repeat,
    sources_of,
)
from freecad.menuiserie.features.repeat_furniture_links import (
    COMPONENTS,
    DIMENSIONS,
    FURNITURE_PATHS,
    MATERIAL,
    ROTATION,
    furniture_expressions,
    inner_expressions,
    shift_text,
)
from freecad.menuiserie.features.repeat_joints import unlink_part_joints

__all__ = [
    "BOUND_PATHS",
    "copy_expressions",
    "link_copy",
    "link_inner",
    "repeat_removed",
    "source_removed",
    "unlink_copy",
]

BOUND_PATHS: Final = tuple(
    dict.fromkeys(
        (
            *DIMENSIONS,
            *(f"Placement.Base.{c}" for c in COMPONENTS.values()),
            ROTATION,
            *MATERIAL,
            *FURNITURE_PATHS,
        )
    )
)


def copy_expressions(source: str, repeat: str, index: int, axis: RepeatAxis) -> dict[str, str]:
    """Expressions de la copie de rang ``index`` : propriété → texte. ``source`` et ``repeat``
    sont les noms (``Name``) des objets."""
    expressions = {name: f"{source}.{name}" for name in (*DIMENSIONS, *MATERIAL)}
    for component in COMPONENTS.values():
        expressions[f"Placement.Base.{component}"] = f"{source}.Placement.Base.{component}"
    expressions[ROTATION] = f"{source}.{ROTATION}"
    moved = f"Placement.Base.{COMPONENTS[axis]}"
    expressions[moved] += f" + {shift_text(repeat, index)}"
    return expressions


def link_copy(
    copy: DocumentObject, source: DocumentObject, repeat: DocumentObject, axis: RepeatAxis
) -> None:
    """Écrit (ou réécrit) les expressions de ``copy`` (pièce ou ensemble) d'après son rang
    ``RepeatIndex``."""
    make = furniture_expressions if is_furniture(copy) else copy_expressions
    for path, text in make(source.Name, repeat.Name, copy.RepeatIndex, axis).items():
        copy.setExpression(path, text)


def link_inner(copy: DocumentObject) -> None:
    """Écrit les expressions de ``copy``, copie d'un membre rangée dans un ensemble copie
    (:func:`.repeat_furniture_links.inner_expressions`)."""
    for path, text in inner_expressions(copy, copy.RepeatSource).items():
        copy.setExpression(path, text)


def _unlink_own(copy: DocumentObject) -> None:
    """Retire de ``copy`` ses expressions de liaison et ses propriétés de copie."""
    if not is_furniture(copy):
        unlink_part_joints(copy)
    names = {obj.Name for obj in (copy.Repeat, copy.RepeatSource) if obj is not None}
    for path, text in expressions_of(copy).items():
        if path in BOUND_PATHS and cites(text, names):
            copy.setExpression(path, None)
    for name in COPY_PROPERTY_NAMES:
        copy.removeProperty(name)


def _inner_copies(copy: DocumentObject, seen: set[str] | None = None) -> list[DocumentObject]:
    """Copies des membres de la copie d'ensemble ``copy`` (à tous les niveaux). ``seen`` : noms
    déjà parcourus, pour ne pas boucler sur un document forgé."""
    seen = {copy.Name} if seen is None else seen
    found: list[DocumentObject] = []
    for member in members_of(copy) if is_furniture(copy) else ():
        if member.Name not in seen and is_copy(member) and member.Repeat == copy.Repeat:
            seen.add(member.Name)
            found.append(member)
            found.extend(_inner_copies(member, seen))
    return found


def unlink_copy(copy: DocumentObject, *, relink: bool = True) -> None:
    """Dissocie ``copy`` : retire ses expressions de liaison et ses propriétés ``Repeat``,
    ``RepeatSource`` et ``RepeatIndex``, et dissocie ses assemblages enfants
    (:func:`.repeat_joints.unlink_part_joints`). Elle garde ses valeurs actuelles et devient une
    pièce libre. Une copie d'ensemble est dissociée avec tous ses membres copiés. Sans effet sur
    ce qui n'est pas une copie liée.

    ``relink`` : l'ensemble qui contient la copie, et la copie elle-même si c'est un ensemble,
    sont reliés ensuite (:mod:`.furniture_bindings`) : ce qui était piloté par la source ne l'est
    plus, les liaisons normales de l'ensemble s'appliquent. ``ValueError`` traduite si les
    liaisons forment un cycle avec une formule de l'utilisateur."""
    if not is_copy(copy):
        return
    parent = furniture_of(copy)
    for inner in reversed(_inner_copies(copy)):
        _unlink_own(inner)
    _unlink_own(copy)
    if relink:
        relink_free(copy, parent)


def relink_free(copy: DocumentObject, parent: DocumentObject | None) -> None:
    """Relie ``parent`` (ensemble de la copie dissociée) et, si ``copy`` est un ensemble, ses
    membres à tous les niveaux : la copie retrouve des liaisons normales."""
    if is_furniture(copy):
        rebind(copy)
    if parent is not None:
        bind_furniture(parent)


def _during_deletion(obj: DocumentObject) -> bool:
    """Faux pendant une annulation, un rétablissement ou une restauration : seule une
    suppression par l'utilisateur ou par un script dissocie les copies."""
    return "Restore" in obj.State or bool(obj.Document.Transacting)


def _unlink_quietly(copy: DocumentObject) -> None:
    """Dissocie ``copy`` pendant une suppression : des liaisons impossibles (cycle avec une formule
    de l'utilisateur) sont signalées dans le rapport et laissées telles quelles."""
    try:
        unlink_copy(copy)
    except ValueError as error:
        report_warning(str(error))


def repeat_removed(repeat: DocumentObject) -> None:
    """Répétition supprimée (``unsetupObject``) : ses copies sont dissociées (celles des membres
    d'une copie d'ensemble avec elle)."""
    if _during_deletion(repeat):
        return
    for copy in copies_of(repeat):
        if not is_inner_copy(copy):
            _unlink_quietly(copy)


def source_removed(source: DocumentObject) -> None:
    """Pièce ou ensemble source supprimé (``unsetupObject``) : ses copies restantes sont
    dissociées, puis il sort de ``Source`` de ses répétitions."""
    if _during_deletion(source):
        return
    for parent in list(source.InList):
        if is_copy(parent) and parent.RepeatSource == source:
            _unlink_quietly(parent)
        elif is_repeat(parent) and source in sources_of(parent):
            parent.Source = [obj for obj in sources_of(parent) if obj != source]
