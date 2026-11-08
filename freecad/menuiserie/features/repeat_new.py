# SPDX-License-Identifier: LGPL-2.1-or-later
"""Création et retrait des copies d'une pièce ou d'un ensemble (ADR 0043, lot R-b3).

Une copie de pièce est une pièce de bois créée par :func:`.wood_part.create_wood_part`, au
libellé « {libellé source} {k+1} », rangée dans le conteneur de la source. Une copie d'ensemble
est un ensemble neuf (sous-ensemble du même parent s'il y en a un) qui reçoit une copie de chaque
membre de la source, récursivement. Les copies d'un membre d'ensemble entrent dans l'ensemble avec
les mêmes options que la source (mode, options « fixe », verrou) ; aucune liaison n'est écrite
ici. Leurs expressions sont écrites par :mod:`.repeat_links`.

Rien ici n'ouvre de transaction ni ne recalcule : c'est le rôle de ``_api/repeat.py``.
"""

from __future__ import annotations

import FreeCAD as App

from freecad.menuiserie.core.furniture import Edge, FurnitureBox
from freecad.menuiserie.core.geometry import Vec3
from freecad.menuiserie.features import schema
from freecad.menuiserie.features.drag_joints import remove_joints
from freecad.menuiserie.features.freecad_types import Document, DocumentObject
from freecad.menuiserie.features.furniture import (
    create_furniture,
    furniture_of,
    is_furniture,
    option_name,
    origin_of,
    writing,
)
from freecad.menuiserie.features.furniture_bindings import members_of
from freecad.menuiserie.features.furniture_members import join_member
from freecad.menuiserie.features.machined_part import (
    machined_part_of,
    remove_machined_part,
)
from freecad.menuiserie.features.repeat import COPY_PROPERTIES, is_copy
from freecad.menuiserie.features.wood_part import create_wood_part

__all__ = ["add_missing_members", "drop_copy", "new_copies", "new_part_copy"]


def _mark_copy(
    copy: DocumentObject, source: DocumentObject, repeat: DocumentObject, index: int
) -> None:
    """``copy`` porte ``Repeat``, ``RepeatSource`` et ``RepeatIndex`` (lecture seule)."""
    schema.add_missing_properties(copy, COPY_PROPERTIES)
    schema.apply_editor_modes(copy, COPY_PROPERTIES)
    copy.Repeat, copy.RepeatSource, copy.RepeatIndex = repeat, source, index


def new_part_copy(
    source: DocumentObject, repeat: DocumentObject, index: int, shift: App.Vector
) -> DocumentObject:
    """Copie de rang ``index`` de la pièce ``source`` (sans expressions), à ``shift`` d'elle."""
    copy = create_wood_part(
        source.Document,
        length=source.Length.Value,
        width=source.Width.Value,
        thickness=source.Thickness.Value,
        material_id=source.MaterialId,
        mark=f"{source.Label} {index + 1}",
    )
    container = source.getParentGeoFeatureGroup()
    if container is not None:
        container.addObject(copy)
    copy.GrainDirection = source.GrainDirection
    for name in ("LengthAllowance", "WidthAllowance", "ThicknessAllowance"):
        setattr(copy, name, getattr(source, name))
    _mark_copy(copy, source, repeat, index)
    placement = source.Placement
    copy.Placement = App.Placement(placement.Base + shift, placement.Rotation)
    return copy


def _new_furniture_copy(
    source: DocumentObject, repeat: DocumentObject, index: int, shift: App.Vector
) -> DocumentObject:
    """Copie de rang ``index`` de l'ensemble ``source`` (vide, sans expressions), à ``shift``."""
    box = FurnitureBox(source.Width.Value, source.Depth.Value, source.Height.Value)
    here = origin_of(source)
    origin = Vec3(here.x + shift.x, here.y + shift.y, here.z + shift.z)
    copy = create_furniture(
        source.Document,
        box,
        origin,
        f"{source.Label} {index + 1}",
        source.getParentGeoFeatureGroup(),
    )
    _mark_copy(copy, source, repeat, index)
    return copy


def _join_like(obj: DocumentObject, furniture: DocumentObject, like: DocumentObject) -> None:
    """Fait de ``obj`` un membre de ``furniture`` avec les mêmes options que le membre ``like`` :
    mode, options « fixe » et verrou. Aucune liaison n'est écrite."""
    fixed = frozenset(edge for edge in Edge if bool(getattr(like, option_name(edge), False)))
    join_member(obj, furniture, fixed)
    with writing(obj):
        obj.PositionMode = like.PositionMode
        obj.Locked = bool(like.Locked)


def _copy_into(
    original: DocumentObject,
    parent: DocumentObject | None,
    repeat: DocumentObject,
    index: int,
    shift: App.Vector,
    created: list[DocumentObject],
) -> None:
    """Copie ``original`` dans l'ensemble ``parent`` (``None`` : hors ensemble) ; un ensemble
    reçoit ensuite la copie de chacun de ses membres."""
    if is_furniture(original):
        copy = _new_furniture_copy(original, repeat, index, shift)
    else:
        copy = new_part_copy(original, repeat, index, shift)
    created.append(copy)
    if parent is not None:
        _join_like(copy, parent, original)
    if is_furniture(original):
        for member in members_of(original):
            _copy_into(member, copy, repeat, index, shift, created)


def new_copies(
    source: DocumentObject, repeat: DocumentObject, index: int, shift: App.Vector
) -> list[DocumentObject]:
    """Copie de rang ``index`` de ``source`` (pièce ou ensemble) et, pour un ensemble, de tous ses
    membres : la copie de ``source`` en premier, puis celles des membres, un ensemble avant les
    siens. Elle entre dans l'ensemble de ``source`` s'il y en a un, avec les mêmes options."""
    created: list[DocumentObject] = []
    _copy_into(source, furniture_of(source), repeat, index, shift, created)
    return created


def _copy_of(
    member: DocumentObject, furniture: DocumentObject, repeat: DocumentObject
) -> DocumentObject | None:
    """Copie de ``member`` rangée dans l'ensemble copie ``furniture``, ``None`` si elle manque."""
    return next(
        (
            obj
            for obj in members_of(furniture)
            if is_copy(obj) and obj.Repeat == repeat and obj.RepeatSource == member
        ),
        None,
    )


def add_missing_members(
    source: DocumentObject,
    copy: DocumentObject,
    known: set[str],
    shift: App.Vector,
    created: list[DocumentObject],
) -> None:
    """Ajoute à l'ensemble copie ``copy`` la copie de chaque membre de l'ensemble ``source`` qui
    n'a encore aucune copie dans la répétition (``known`` : noms des originaux déjà copiés à un
    rang quelconque) : un membre ajouté à la source après coup. Un membre dont la copie a été
    supprimée ou dissociée ne revient pas, sauf s'il n'a plus aucune copie nulle part. Les
    sous-ensembles déjà copiés sont parcourus à leur tour."""
    repeat, index = copy.Repeat, copy.RepeatIndex
    for member in members_of(source):
        existing = _copy_of(member, copy, repeat)
        if existing is not None and is_furniture(member):
            add_missing_members(member, existing, known, shift, created)
        elif existing is None and member.Name not in known:
            _copy_into(member, copy, repeat, index, shift, created)


def _drop_part(copy: DocumentObject) -> None:
    """Supprime une copie de pièce avec sa pièce usinée et ses assemblages, s'il y en a (G)."""
    doc: Document = copy.Document
    machined = machined_part_of(copy)
    if machined is not None:
        name = machined.Name
        remove_joints(list(machined.Joints))  # retire aussi la pièce usinée devenue sans assemblage
        if doc.getObject(name) is not None:
            remove_machined_part(machined)
    doc.removeObject(copy.Name)


def drop_copy(copy: DocumentObject) -> None:
    """Supprime une copie. Une copie d'ensemble emporte les copies de ses membres (les pièces
    qu'on y aurait ajoutées à la main restent, libres)."""
    if is_furniture(copy):
        for member in members_of(copy):
            if is_copy(member) and member.Repeat == copy.Repeat:
                drop_copy(member)
        copy.Document.removeObject(copy.Name)
    else:
        _drop_part(copy)
