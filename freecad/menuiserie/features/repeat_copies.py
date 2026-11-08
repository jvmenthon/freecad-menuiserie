# SPDX-License-Identifier: LGPL-2.1-or-later
"""Réglage d'une répétition : sources contrôlées, copies créées, retirées et liées (ADR 0043).

Les copies sont de vraies pièces de bois, ou des ensembles copie qui reçoivent une copie de chaque
membre de l'ensemble source (:mod:`.repeat_new`), au libellé « {libellé source} {k+1} », rangées
dans le conteneur de la source et, si la source est membre d'un ensemble, dans cet ensemble avec
les mêmes options. Leurs expressions sont écrites par :mod:`.repeat_links` et
:mod:`.repeat_furniture_links`, leurs assemblages par :mod:`.repeat_joints`, le suivi du
redimensionnement de l'ensemble par :mod:`.repeat_follow`. Les autres types de pièces sont
refusés pour l'instant (pièce en bois à forme libre).

Source = pièce usinée (R-b2) : la sélection naturelle est la pièce visible, donc la pièce usinée.
La répétition porte sur sa **pièce brute** (ADR 0006 : les cotes, le matériau et le placement sont
dans la brute ; la forme usinée dépend de ses assemblages et ne se copie pas). La copie est une
brute neuve qui reçoit sa propre pièce usinée par ses assemblages recopiés ; sans assemblage
recopié, elle reste une pièce brute simple.

Rien ici n'ouvre de transaction ni ne recalcule : c'est le rôle de ``_api/repeat.py``.
Les copies ne se créent et ne se suppriment jamais pendant un recalcul.

Pas commun à plusieurs sources : la cote qui sert aux modes « sur une longueur » est celle de
l'ensemble des sources le long de l'axe (boîte englobante de leurs formes, ou cote d'un ensemble,
lues à l'écriture).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final, NamedTuple

import FreeCAD as App

from freecad.menuiserie.core.furniture import Notice
from freecad.menuiserie.core.geometry import Vec3
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.repeat import RepeatAxis, RepeatParams, Resolved, offsets, resolve
from freecad.menuiserie.core.text import quoted_value
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.furniture import furniture_of, is_furniture
from freecad.menuiserie.features.furniture_bindings import notice_messages, rebind
from freecad.menuiserie.features.furniture_relink import bind_furniture
from freecad.menuiserie.features.i18n import translated, translated_errors
from freecad.menuiserie.features.machined_part import is_machined_part
from freecad.menuiserie.features.repeat import (
    copies_of,
    is_copy,
    is_inner_copy,
    sources_of,
    write_params,
)
from freecad.menuiserie.features.repeat_follow import (
    bind_follow,
    follow_furniture,
    follow_params,
    unbind_follow,
)
from freecad.menuiserie.features.repeat_joints import update_joints
from freecad.menuiserie.features.repeat_links import link_copy, link_inner
from freecad.menuiserie.features.repeat_members import ancestors_of, descendants_of
from freecad.menuiserie.features.repeat_new import drop_copy, new_copies
from freecad.menuiserie.features.wood_part import is_wood_part, validated_arguments

__all__ = ["Created", "apply_repeat", "checked_sources", "resolve_for", "source_extent"]

_NO_SOURCE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Répétition : aucune pièce à répéter.")
_NOT_A_WOOD_PART: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Répétition : « {label} » n'est pas une pièce de bois ; pour l'instant, seules les pièces "
    "de bois (ou leur pièce usinée) et les ensembles se répètent (pas les pièces en bois).",
)
_FOREIGN_MEMBER: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Répétition : l'ensemble « {furniture} » contient « {label} », qui n'est pas une pièce de "
    "bois ; pour l'instant, seuls les ensembles de pièces de bois se répètent.",
)
_IS_A_COPY: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Répétition : « {label} » est déjà la copie d'une répétition ; dissociez-la d'abord pour la "
    "répéter.",
)
_WITH_ITS_FURNITURE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Répétition : « {label} » est membre de « {furniture} », répété en même temps ; répétez "
    "l'ensemble, ou la pièce seule.",
)
_OTHER_DOCUMENT: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Répétition : les pièces à répéter doivent être dans le même document."
)
_EMPTY_SHAPE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Répétition : « {label} » n'a pas de forme ; recalculez le document avant de la répéter.",
)
_AXES: Final = {RepeatAxis.X: "X", RepeatAxis.Y: "Y", RepeatAxis.Z: "Z"}
_SIZES: Final = {RepeatAxis.X: "Width", RepeatAxis.Y: "Depth", RepeatAxis.Z: "Height"}


def _checked_part(obj: DocumentObject) -> None:
    """Pièce de bois de dimensions et matériau valides (``ValueError`` traduite sinon)."""
    validated_arguments(*(obj.Length.Value, obj.Width.Value, obj.Thickness.Value), obj.MaterialId)


def _checked_furniture(furniture: DocumentObject) -> None:
    """Un ensemble ne se répète que si tous ses membres, à tous les niveaux, sont des pièces de
    bois ou des ensembles (``TypeError`` traduite sinon)."""
    for member in descendants_of(furniture):
        if is_furniture(member):
            continue
        if not is_wood_part(member):
            params = {
                "furniture": quoted_value(furniture.Label),
                "label": quoted_value(member.Label),
            }
            raise TypeError(translated(_FOREIGN_MEMBER, params))
        _checked_part(member)


def _checked_source(obj: DocumentObject) -> None:
    """Une source valide : pièce de bois ou ensemble, qui n'est pas déjà une copie liée."""
    params = {"label": quoted_value(getattr(obj, "Label", obj))}
    if not (is_furniture(obj) or is_wood_part(obj)):
        raise TypeError(translated(_NOT_A_WOOD_PART, params))
    if is_copy(obj):
        raise ValueError(translated(_IS_A_COPY, params))
    if is_furniture(obj):
        _checked_furniture(obj)
    else:
        _checked_part(obj)


def _refuse_nested(sources: Sequence[DocumentObject]) -> None:
    """Une source ne peut pas être répétée en même temps que l'un de ses ensembles (``ValueError``
    traduite) : elle serait copiée deux fois."""
    names = {obj.Name for obj in sources}
    for obj in sources:
        for furniture in ancestors_of(obj):
            if furniture.Name in names:
                params = {
                    "label": quoted_value(obj.Label),
                    "furniture": quoted_value(furniture.Label),
                }
                raise ValueError(translated(_WITH_ITS_FURNITURE, params))


def checked_sources(objects: Sequence[DocumentObject]) -> list[DocumentObject]:
    """Pièces et ensembles à répéter, sans doublon, dans l'ordre. Refus traduits avant toute
    création : ``ValueError`` (aucune pièce, documents différents, copie déjà liée, pièce répétée
    en même temps que son propre ensemble, cote ou matériau inconnu), ``TypeError`` (autre chose
    qu'une pièce de bois ou un ensemble de pièces de bois) ; ``KeyError`` pour un matériau absent
    de la bibliothèque locale."""
    sources = list(
        dict.fromkeys(
            machined.Base if is_machined_part(machined) else machined for machined in objects
        )
    )
    if not sources:
        raise ValueError(translated(_NO_SOURCE))
    for obj in sources:
        _checked_source(obj)
    if len({obj.Document.Name for obj in sources}) > 1:
        raise ValueError(translated(_OTHER_DOCUMENT))
    _refuse_nested(sources)
    return sources


def source_extent(sources: Sequence[DocumentObject], axis: RepeatAxis) -> float:
    """Cote des ``sources`` le long de l'axe global (mm) : boîte englobante de leurs formes, ou
    de ``Origin`` à ``Origin`` plus la cote pour un ensemble."""
    low, high = [], []
    for source in sources:
        if is_furniture(source):
            start = getattr(source.Origin, _AXES[axis].lower())
            low.append(start)
            high.append(start + getattr(source, _SIZES[axis]).Value)
            continue
        if source.Shape.isNull():
            raise ValueError(translated(_EMPTY_SHAPE, {"label": quoted_value(source.Label)}))
        box = source.Shape.BoundBox
        low.append(getattr(box, f"{_AXES[axis]}Min"))
        high.append(getattr(box, f"{_AXES[axis]}Max"))
    return float(max(high) - min(low))


def resolve_for(sources: Sequence[DocumentObject], params: RepeatParams) -> Resolved:
    """Nombre de copies et pas effectifs de ``params`` pour ces ``sources`` ; ``ValueError``
    traduite si la répétition est refusée (longueur trop courte, trop de copies, « suivre le
    redimensionnement » sans ensemble…)."""
    if params.follow_resize:
        follow_furniture(sources)
    extent = source_extent(sources, params.axis)
    with translated_errors():
        return resolve(params, extent)


class Created(NamedTuple):
    """Objets créés par :func:`apply_repeat` : copies (pièces et ensembles), assemblages, et
    avertissements traduits des liaisons des ensembles."""

    copies: list[DocumentObject]
    joints: list[DocumentObject]
    notices: tuple[str, ...] = ()


def _sync_copies(
    repeat: DocumentObject,
    source: DocumentObject,
    resolved: Resolved,
    previous: int,
    shifts: Sequence[Vec3],
    axis: RepeatAxis,
) -> list[DocumentObject]:
    """Copies de ``source`` : celles de rang supérieur au nombre sont supprimées, celles qui
    manquent créées (rangs à la suite de ``previous``), puis les expressions de toutes réécrites.
    Renvoie les objets créés (copie d'un ensemble et copies de ses membres comprises)."""
    for copy in copies_of(repeat, source):
        if copy.RepeatIndex > resolved.count:
            drop_copy(copy)
    created: list[DocumentObject] = []
    for index in range(previous + 1, resolved.count + 1):
        shift = shifts[index - 1]
        made = new_copies(source, repeat, index, App.Vector(shift.x, shift.y, shift.z))
        for copy in made:
            if is_inner_copy(copy):
                link_inner(copy)
        created.extend(made)
    for copy in copies_of(repeat, source):
        link_copy(copy, source, repeat, axis)
    return created


def _bind_furnitures(
    sources: Sequence[DocumentObject], created: Sequence[DocumentObject]
) -> list[Notice]:
    """Liaisons des ensembles touchés : chaque ensemble copie créé (membres et sous-ensembles
    compris), puis l'ensemble de chaque source, dont les copies comptent désormais comme membres."""
    notices: list[Notice] = []
    for copy in created:
        if is_furniture(copy) and not is_inner_copy(copy):
            notices.extend(rebind(copy))
    parents = {parent.Name: parent for parent in map(furniture_of, sources) if parent is not None}
    for parent in parents.values():
        notices.extend(bind_furniture(parent))
    return notices


def apply_repeat(repeat: DocumentObject, params: RepeatParams) -> Created:
    """Met la répétition au réglage ``params`` : écrit ses propriétés, supprime les copies de
    rang supérieur au nombre, crée celles qui manquent (rangs à la suite de l'ancien nombre : une
    copie dissociée ou supprimée à la main ne revient pas), réécrit les expressions de toutes,
    puis recopie les assemblages (``CopyJoints`` vrai : ceux des nouvelles copies, ou de toutes
    si la case vient d'être cochée ; faux : les assemblages enfants sont supprimés) et relie les
    ensembles touchés. ``FollowResize`` vrai : le pas devient une expression sur la cote de
    l'ensemble (:mod:`.repeat_follow`). Renvoie les copies, les assemblages créés et les
    avertissements. Aucune transaction ni recalcul."""
    sources = sources_of(repeat)
    resolved = resolve_for(sources, params)
    extent = source_extent(sources, params.axis)
    shifts = offsets(params, extent)
    previous = int(repeat.Count)
    joints_were_copied = bool(repeat.CopyJoints)
    unbind_follow(repeat)
    written = follow_params(params, resolved, extent) if params.follow_resize else params
    write_params(repeat, written, resolved)
    if params.follow_resize:
        bind_follow(repeat, follow_furniture(sources), params.axis, extent, resolved)
    created: list[DocumentObject] = []
    for source in sources:
        created.extend(_sync_copies(repeat, source, resolved, previous, shifts, params.axis))
    first = previous + 1 if joints_were_copied else 1
    joints = update_joints(
        repeat, enabled=params.copy_joints, ranks=range(first, resolved.count + 1)
    )
    notices = _bind_furnitures(sources, created)
    return Created(created, joints, notice_messages(notices))
