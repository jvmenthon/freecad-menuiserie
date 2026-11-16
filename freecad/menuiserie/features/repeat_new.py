# SPDX-License-Identifier: LGPL-2.1-or-later
"""Création et retrait des copies d'une pièce ou d'un ensemble (ADR 0043, lot R-b3).

Une copie de pièce est une pièce de bois créée par :func:`.wood_part.create_wood_part`, au
libellé « {libellé source} {k+1} », rangée dans le conteneur de la source. Une copie de pièce en
bois (``ShapedPart``, ADR 0050) en est une aussi : elle lie le même ``Source`` (le corps n'est ni
copié ni modifié) et reprend repère, solide désigné, matériau, fil et surcotes ; ses cotes
d'encombrement sont des sorties de ``execute()``, jamais liées. Une copie d'ensemble
est un ensemble neuf (sous-ensemble du même parent s'il y en a un) qui reçoit une copie de chaque
membre de la source, récursivement.

Std Part (ADR 0038 et 0044) : l'ensemble source étant rangé dans son Std Part, sa copie reçoit le
sien, créé comme celui d'un ensemble neuf (:func:`.furniture_container.create_with_std_part`),
dans le conteneur du Std Part de la source (dans le Std Part de la copie du parent pour un
sous-ensemble) ; les copies de ses membres y sont créées, à la même place que dans le Std Part de
la source (le décalage est dans le Std Part de la copie, pas dans leurs placements).

Les copies d'un membre d'ensemble entrent dans l'ensemble avec les mêmes options que la source
(mode, options « fixe », verrou) ; aucune liaison n'est écrite ici.
Leurs expressions sont écrites par :mod:`.repeat_links`.

Rien ici n'ouvre de transaction ni ne recalcule : c'est le rôle de ``_api/repeat.py``.
"""

from __future__ import annotations

from typing import NamedTuple

import FreeCAD as App

from freecad.menuiserie.core.furniture import Edge, FurnitureBox
from freecad.menuiserie.core.geometry import Vec3
from freecad.menuiserie.core.repeat import Cell
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
from freecad.menuiserie.features.furniture_container import (
    create_with_std_part,
    placement_container,
    std_part_of,
)
from freecad.menuiserie.features.furniture_detach import release_furniture
from freecad.menuiserie.features.furniture_members import join_member
from freecad.menuiserie.features.i18n import report_warning
from freecad.menuiserie.features.library import get_library
from freecad.menuiserie.features.machined_part import (
    machined_part_of,
    remove_machined_part,
)
from freecad.menuiserie.features.part_names import label_of_mark
from freecad.menuiserie.features.repeat import COPY_PROPERTIES, cell_of, is_copy, write_cell
from freecad.menuiserie.features.shaped_part import (
    OBJECT_NAME,
    ShapedPart,
    is_profile,
    is_shaped_part,
)
from freecad.menuiserie.features.shaped_part_schema import apply_editor_modes
from freecad.menuiserie.features.wood_material import shows_grain
from freecad.menuiserie.features.wood_part import create_wood_part

__all__ = [
    "Place",
    "add_missing_members",
    "drop_copy",
    "new_copies",
    "new_part_copy",
    "new_shaped_copy",
]

_ALLOWANCES = ("LengthAllowance", "WidthAllowance", "ThicknessAllowance")
# Recopiés par valeur dans une copie de pièce en bois : repère, solide désigné, cotes de départ
# (le recalcul les réécrit), jamais liés par expression.
_SHAPED_VALUES = (
    "SourceAxes",
    "ProfileThickness",
    "SolidIndex",
    "SolidSignature",
    "Length",
    "Width",
    "Thickness",
)


class Place(NamedTuple):
    """Où se trouve une copie dans la grille : sa ``cell`` (identité, ADR 0045), son ``rank``
    linéaire (à partir de 1, ordre d'affichage et libellé) et son décalage ``shift`` par rapport à
    la source (repère du conteneur)."""

    cell: Cell
    rank: int
    shift: App.Vector


def _mark_copy(
    copy: DocumentObject, source: DocumentObject, repeat: DocumentObject, at: Place
) -> None:
    """``copy`` porte ``Repeat``, ``RepeatSource``, ``RepeatIndex`` et ``RepeatCell`` (lecture
    seule)."""
    schema.add_missing_properties(copy, COPY_PROPERTIES)
    schema.apply_editor_modes(copy, COPY_PROPERTIES)
    copy.Repeat, copy.RepeatSource, copy.RepeatIndex = repeat, source, at.rank
    write_cell(copy, at.cell)


def _finish_copy(
    copy: DocumentObject,
    source: DocumentObject,
    repeat: DocumentObject,
    at: Place,
    container: DocumentObject | None,
) -> DocumentObject:
    """Range ``copy`` (pièce de bois ou pièce en bois) dans ``container`` (``None`` : racine), lui
    donne le fil et les surcotes de ``source``, ses marques de copie et sa place ``at``."""
    if container is not None:
        container.addObject(copy)
    copy.GrainDirection = source.GrainDirection
    for name in _ALLOWANCES:
        setattr(copy, name, getattr(source, name))
    _mark_copy(copy, source, repeat, at)
    placement = source.Placement
    copy.Placement = App.Placement(placement.Base + at.shift, placement.Rotation)
    return copy


def new_part_copy(
    source: DocumentObject, repeat: DocumentObject, at: Place, container: DocumentObject | None
) -> DocumentObject:
    """Copie de la pièce ``source`` (pièce de bois ou pièce en bois) à la place ``at`` (sans
    expressions), rangée dans ``container`` (``None`` : racine)."""
    if is_shaped_part(source):
        return new_shaped_copy(source, repeat, at, container)
    copy = create_wood_part(
        source.Document,
        length=source.Length.Value,
        width=source.Width.Value,
        thickness=source.Thickness.Value,
        material_id=source.MaterialId,
        mark=f"{source.Label} {at.rank + 1}",
    )
    return _finish_copy(copy, source, repeat, at, container)


def new_shaped_copy(
    source: DocumentObject, repeat: DocumentObject, at: Place, container: DocumentObject | None
) -> DocumentObject:
    """Copie de la pièce en bois ``source`` (ADR 0050) : une ``ShapedPart`` qui lie le même
    ``Source`` (le corps n'est ni copié ni modifié), sans passer par ``create_shaped_parts`` (qui
    refuse un corps déjà converti). Les réglages sont recopiés par valeur ; les cotes
    d'encombrement le sont aussi, pour mémoire seulement : le recalcul les réécrit depuis le
    corps. Aucune expression ici."""
    copy = source.Document.addObject("Part::FeaturePython", OBJECT_NAME)
    proxy = ShapedPart(copy)
    proxy.select_material(copy, get_library().get(source.MaterialId))
    copy.Source = source.Source
    for name in _SHAPED_VALUES:
        setattr(copy, name, getattr(source, name))
    with proxy.synchronizing():
        copy.Mark = f"{source.Label} {at.rank + 1}"
        copy.Label = label_of_mark(copy, copy.Mark)
    apply_editor_modes(
        copy, show_grain=shows_grain(copy, proxy.library()), profile=is_profile(copy)
    )
    return _finish_copy(copy, source, repeat, at, container)


def _new_furniture_copy(
    source: DocumentObject, repeat: DocumentObject, at: Place, outer: DocumentObject | None
) -> DocumentObject:
    """Copie de l'ensemble ``source`` (vide, sans expressions), à la place ``at``.
    Source dans un Std Part : la copie a le sien, rangé dans ``outer`` (``None`` : racine), à la
    place de celui de la source plus ``shift`` ; son ``Origin`` est celle de la source. Sans Std
    Part : ``shift`` est ajouté à l'``Origin``, la copie est rangée dans le conteneur de la
    source."""
    box = FurnitureBox(source.Width.Value, source.Depth.Value, source.Height.Value)
    here, label = origin_of(source), f"{source.Label} {at.rank + 1}"
    shift = at.shift
    source_part = std_part_of(source)
    if source_part is None:
        origin = Vec3(here.x + shift.x, here.y + shift.y, here.z + shift.z)
        copy = create_furniture(
            source.Document, box, origin, label, source.getParentGeoFeatureGroup()
        )
    else:
        copy = create_with_std_part(source.Document, box, here, label, outer)
        placement, part = source_part.Placement, std_part_of(copy)
        if part is not None:
            part.Placement = App.Placement(placement.Base + shift, placement.Rotation)
    _mark_copy(copy, source, repeat, at)
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
    at: Place,
    created: list[DocumentObject],
) -> None:
    """Copie ``original`` dans l'ensemble ``parent`` (``None`` : hors ensemble) ; un ensemble
    reçoit ensuite la copie de chacun de ses membres."""
    inner = parent is not None and is_copy(parent) and std_part_of(parent) is not None
    # copie d'un membre : dans le Std Part de la copie, sans décalage
    here = at._replace(shift=App.Vector()) if inner else at
    holder = std_part_of(parent) if inner and parent is not None else None
    if is_furniture(original):
        outer = holder if inner else placement_container(original)
        copy = _new_furniture_copy(original, repeat, here, outer)
    else:
        container = holder if inner else original.getParentGeoFeatureGroup()
        copy = new_part_copy(original, repeat, here, container)
    created.append(copy)
    if parent is not None:
        _join_like(copy, parent, original)
    if is_furniture(original):
        for member in members_of(original):
            _copy_into(member, copy, repeat, at, created)


def new_copies(source: DocumentObject, repeat: DocumentObject, at: Place) -> list[DocumentObject]:
    """Copie de ``source`` (pièce ou ensemble) à la place ``at`` et, pour un ensemble, de tous ses
    membres : la copie de ``source`` en premier, puis celles des membres, un ensemble avant les
    siens. Elle entre dans l'ensemble de ``source`` s'il y en a un, avec les mêmes options."""
    created: list[DocumentObject] = []
    _copy_into(source, furniture_of(source), repeat, at, created)
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
    repeat, at = copy.Repeat, Place(cell_of(copy), copy.RepeatIndex, shift)
    for member in members_of(source):
        existing = _copy_of(member, copy, repeat)
        if existing is not None and is_furniture(member):
            add_missing_members(member, existing, known, shift, created)
        elif existing is None and member.Name not in known:
            _copy_into(member, copy, repeat, at, created)


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
        for message in release_furniture(copy):  # pièces ajoutées à la main : elles sortent
            report_warning(message)
        copy.Document.removeObject(copy.Name)
    else:
        _drop_part(copy)
