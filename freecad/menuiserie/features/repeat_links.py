# SPDX-License-Identifier: LGPL-2.1-or-later
"""Liaison d'une copie à sa source par expressions natives (ADR 0043, comme l'ADR 0009).

Pour la copie de cellule ``(i, j, k)`` de la source ``S`` d'une répétition ``R`` (rang ``i`` sur X,
``j`` sur Y, ``k`` sur Z ; un seul est non nul pour une répétition sur un axe) :

- ``Length``, ``Width``, ``Thickness`` = celles de ``S`` (sauf pour une pièce en bois, ADR 0050 :
  ce sont des sorties de ``execute()``, sans expression ; ``SourceAxes`` et ``ProfileThickness``
  sont liés à ``S`` à leur place, la copie recalcule ses cotes depuis le même corps) ;
- ``Placement.Base.c`` = ``S.Placement.Base.c`` (+ ``n * (R.Reverse ? -1 : 1) * R.Step`` pour chaque
  composante ``c`` dont le rang ``n`` n'est pas nul ; ``Reverse2`` et ``Step2`` pour la deuxième
  ligne de la grille, ``Reverse3`` et ``Step3`` pour la troisième, ADR 0045) ;
  ``Placement.Rotation`` = celle de ``S`` ;
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

from collections.abc import Mapping
from typing import Final

from freecad.menuiserie.core.repeat import RepeatAxis
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.furniture import furniture_of, is_furniture
from freecad.menuiserie.features.furniture_bindings import members_of, rebind
from freecad.menuiserie.features.furniture_container import (
    member_expressions,
    set_member_expression,
    std_part_of,
)
from freecad.menuiserie.features.furniture_relink import bind_furniture
from freecad.menuiserie.features.i18n import report_warning
from freecad.menuiserie.features.repeat import (
    COPY_PROPERTY_NAMES,
    cell_of,
    cited_names,
    cites,
    copies_of,
    is_copy,
    is_inner_copy,
    is_repeat,
    sources_of,
    stored_lines,
)
from freecad.menuiserie.features.repeat_furniture_links import (
    COMPONENTS,
    DIMENSIONS,
    FURNITURE_PATHS,
    MATERIAL,
    ROTATION,
    SHAPED,
    furniture_cell_expressions,
    furniture_expressions,
    inner_expressions,
    shift_terms,
    shift_text,
)
from freecad.menuiserie.features.repeat_joints import unlink_part_joints
from freecad.menuiserie.features.repeat_props import CELL_PROPERTY
from freecad.menuiserie.features.shaped_part import is_shaped_part

__all__ = [
    "BOUND_PATHS",
    "cell_expressions",
    "copy_expressions",
    "detach_copies",
    "furniture_expressions",
    "link_copy",
    "link_inner",
    "repeat_removed",
    "source_removed",
    "unlink_copy",
    "unlink_inner_copies",
]

BOUND_PATHS: Final = tuple(
    dict.fromkeys(
        (
            *DIMENSIONS,
            *(f"Placement.Base.{c}" for c in COMPONENTS.values()),
            ROTATION,
            *MATERIAL,
            *SHAPED,
            *FURNITURE_PATHS,
        )
    )
)


def cell_expressions(
    source: str, shifts: Mapping[RepeatAxis, str], *, shaped: bool = False
) -> dict[str, str]:
    """Expressions d'une copie de pièce : propriété → texte. ``source`` : nom (``Name``) de la
    source ; ``shifts`` : décalage sur chaque axe où la copie n'est pas à l'original
    (:func:`.repeat_furniture_links.shift_terms`) ; ``shaped`` : copie de pièce en bois, sans
    expression sur les cotes (``SourceAxes`` et ``ProfileThickness`` à la place, ADR 0050)."""
    linked = (*SHAPED, *MATERIAL) if shaped else (*DIMENSIONS, *MATERIAL)
    expressions = {name: f"{source}.{name}" for name in linked}
    for component in COMPONENTS.values():
        expressions[f"Placement.Base.{component}"] = f"{source}.Placement.Base.{component}"
    expressions[ROTATION] = f"{source}.{ROTATION}"
    for axis, text in shifts.items():
        expressions[f"Placement.Base.{COMPONENTS[axis]}"] += f" + {text}"
    return expressions


def copy_expressions(source: str, repeat: str, index: int, axis: RepeatAxis) -> dict[str, str]:
    """Expressions de la copie de rang ``index`` d'une répétition sur un seul axe : propriété →
    texte. ``source`` et ``repeat`` sont les noms (``Name``) des objets."""
    return cell_expressions(source, {axis: shift_text(repeat, index)})


def link_copy(copy: DocumentObject, source: DocumentObject, repeat: DocumentObject) -> None:
    """Écrit (ou réécrit) les expressions de ``copy`` (pièce ou ensemble) d'après sa cellule
    ``RepeatCell`` et les lignes de la répétition (axe, pas et sens de chacune)."""
    shifts = shift_terms(repeat.Name, cell_of(copy), [line.axis for line in stored_lines(repeat)])
    if is_furniture(copy):
        part = std_part_of(source) if std_part_of(copy) is not None else None
        made = furniture_cell_expressions(source.Name, shifts, None if part is None else part.Name)
    else:
        made = cell_expressions(source.Name, shifts, shaped=is_shaped_part(copy))
    for path, text in made.items():
        set_member_expression(copy, path, text)


def link_inner(copy: DocumentObject) -> None:
    """Écrit les expressions de ``copy``, copie d'un membre rangée dans un ensemble copie
    (:func:`.repeat_furniture_links.inner_expressions`)."""
    for path, text in inner_expressions(copy, copy.RepeatSource).items():
        set_member_expression(copy, path, text)


def _unlink_own(copy: DocumentObject) -> None:
    """Retire de ``copy`` ses expressions de liaison et ses propriétés de copie."""
    if not is_furniture(copy):
        unlink_part_joints(copy)
    names = cited_names(copy)
    for path, text in member_expressions(copy).items():
        if path in BOUND_PATHS and cites(text, names):
            set_member_expression(copy, path, None)
    for name in (*COPY_PROPERTY_NAMES, CELL_PROPERTY):
        if name in copy.PropertiesList:
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


def unlink_inner_copies(copy: DocumentObject) -> None:
    """Dissocie les copies des membres de la copie d'ensemble ``copy`` (à tous les niveaux), sans
    toucher à ``copy`` : ses membres deviennent libres, ``copy`` garde ses expressions (elle va
    être supprimée : FreeCAD ne retire pas proprement le lien d'un objet supprimé dont on vient
    de retirer les expressions)."""
    for inner in reversed(_inner_copies(copy)):
        _unlink_own(inner)


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
    """Répétition supprimée (``unsetupObject``) : ses copies sont supprimées avec elle (demande de
    jv, 2026-11-10), avec leurs assemblages et leur Std Part ; une copie d'ensemble emporte les
    copies de ses membres. Une copie dissociée n'en est plus une : elle reste."""
    from freecad.menuiserie.features.repeat_new import drop_copy  # repeat_new importe ce module

    if _during_deletion(repeat):
        return
    for copy in [c for c in copies_of(repeat) if not is_inner_copy(c)]:
        drop_copy(copy)  # une copie d'ensemble emporte les copies de ses membres


def detach_copies(source: DocumentObject) -> None:
    """Dissocie les copies de ``source`` (aucune expression ne doit citer un objet qui disparaît :
    la source, ou le Std Part d'un ensemble source supprimé à la main). Rien pendant une
    annulation, un rétablissement ou une restauration."""
    if _during_deletion(source):
        return
    for parent in list(source.InList):
        if is_copy(parent) and parent.RepeatSource == source:
            _unlink_quietly(parent)


def source_removed(source: DocumentObject) -> None:
    """Pièce ou ensemble source supprimé (``unsetupObject``) : ses copies restantes sont
    dissociées, puis il sort de ``Source`` de ses répétitions."""
    if _during_deletion(source):
        return
    detach_copies(source)
    for parent in list(source.InList):
        if is_repeat(parent) and source in sources_of(parent):
            parent.Source = [obj for obj in sources_of(parent) if obj != source]
