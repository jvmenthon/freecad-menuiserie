# SPDX-License-Identifier: LGPL-2.1-or-later
"""Création, retrait et réécriture des copies d'une répétition (ADR 0043).

Les copies sont de vraies pièces de bois créées par :func:`.wood_part.create_wood_part` (les
autres types de pièces sont refusés pour l'instant : pièce en bois, ensemble), au libellé
« {libellé source} {k+1} », rangées dans le conteneur de la source. Leurs expressions sont écrites
par :mod:`.repeat_links`, leurs assemblages par :mod:`.repeat_joints`.

Source = pièce usinée (R-b2) : la sélection naturelle est la pièce visible, donc la pièce usinée.
La répétition porte sur sa **pièce brute** (ADR 0006 : les cotes, le matériau et le placement sont
dans la brute ; la forme usinée dépend de ses assemblages et ne se copie pas). La copie est une
brute neuve qui reçoit sa propre pièce usinée par ses assemblages recopiés ; sans assemblage
recopié, elle reste une pièce brute simple.

Rien ici n'ouvre de transaction ni ne recalcule : c'est le rôle de ``_api/repeat.py``.
Les copies ne se créent et ne se suppriment jamais pendant un recalcul.

Pas commun à plusieurs sources : la cote qui sert aux modes « sur une longueur » est celle de
l'ensemble des sources le long de l'axe (boîte englobante de leurs formes, lue à l'écriture).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final, NamedTuple

import FreeCAD as App

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.repeat import RepeatAxis, RepeatParams, Resolved, offsets, resolve
from freecad.menuiserie.core.text import quoted_value
from freecad.menuiserie.features import schema
from freecad.menuiserie.features.drag_joints import remove_joints
from freecad.menuiserie.features.freecad_types import Document, DocumentObject
from freecad.menuiserie.features.i18n import translated, translated_errors
from freecad.menuiserie.features.machined_part import (
    is_machined_part,
    machined_part_of,
    remove_machined_part,
)
from freecad.menuiserie.features.repeat import (
    COPY_PROPERTIES,
    copies_of,
    is_copy,
    sources_of,
    write_params,
)
from freecad.menuiserie.features.repeat_joints import update_joints
from freecad.menuiserie.features.repeat_links import link_copy
from freecad.menuiserie.features.wood_part import (
    create_wood_part,
    is_wood_part,
    validated_arguments,
)

__all__ = ["Created", "apply_repeat", "checked_sources", "resolve_for"]

_NO_SOURCE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Répétition : aucune pièce à répéter.")
_NOT_A_WOOD_PART: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Répétition : « {label} » n'est pas une pièce de bois ; pour l'instant, seules les pièces "
    "de bois (ou leur pièce usinée) se répètent (pas les pièces en bois ni les ensembles).",
)
_IS_A_COPY: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Répétition : « {label} » est déjà la copie d'une répétition ; dissociez-la d'abord pour la "
    "répéter.",
)
_OTHER_DOCUMENT: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Répétition : les pièces à répéter doivent être dans le même document."
)
_EMPTY_SHAPE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Répétition : « {label} » n'a pas de forme ; recalculez le document avant de la répéter.",
)
_AXES: Final = {RepeatAxis.X: "X", RepeatAxis.Y: "Y", RepeatAxis.Z: "Z"}


def checked_sources(objects: Sequence[DocumentObject]) -> list[DocumentObject]:
    """Pièces à répéter, sans doublon, dans l'ordre. Refus traduits avant toute création :
    ``ValueError`` (aucune pièce, documents différents, copie déjà liée, cote ou matériau
    inconnu), ``TypeError`` (autre chose qu'une pièce de bois) ; ``KeyError`` pour un matériau
    absent de la bibliothèque locale."""
    sources = list(
        dict.fromkeys(
            machined.Base if is_machined_part(machined) else machined for machined in objects
        )
    )
    if not sources:
        raise ValueError(translated(_NO_SOURCE))
    for obj in sources:
        params = {"label": quoted_value(getattr(obj, "Label", obj))}
        if not is_wood_part(obj):
            raise TypeError(translated(_NOT_A_WOOD_PART, params))
        if is_copy(obj):
            raise ValueError(translated(_IS_A_COPY, params))
        validated_arguments(
            *(obj.Length.Value, obj.Width.Value, obj.Thickness.Value), obj.MaterialId
        )
    if len({obj.Document.Name for obj in sources}) > 1:
        raise ValueError(translated(_OTHER_DOCUMENT))
    return sources


def source_extent(sources: Sequence[DocumentObject], axis: RepeatAxis) -> float:
    """Cote des ``sources`` le long de l'axe global (mm) : boîte englobante de leurs formes."""
    low, high = [], []
    for source in sources:
        if source.Shape.isNull():
            raise ValueError(translated(_EMPTY_SHAPE, {"label": quoted_value(source.Label)}))
        box = source.Shape.BoundBox
        low.append(getattr(box, f"{_AXES[axis]}Min"))
        high.append(getattr(box, f"{_AXES[axis]}Max"))
    return float(max(high) - min(low))


def resolve_for(sources: Sequence[DocumentObject], params: RepeatParams) -> Resolved:
    """Nombre de copies et pas effectifs de ``params`` pour ces ``sources`` ; ``ValueError``
    traduite si la répétition est refusée (longueur trop courte, trop de copies…)."""
    extent = source_extent(sources, params.axis)
    with translated_errors():
        return resolve(params, extent)


def _new_copy(
    source: DocumentObject, repeat: DocumentObject, index: int, shift: App.Vector
) -> DocumentObject:
    """Copie de rang ``index`` de ``source`` (sans expressions), à ``shift`` de la source."""
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
    schema.add_missing_properties(copy, COPY_PROPERTIES)
    schema.apply_editor_modes(copy, COPY_PROPERTIES)
    copy.Repeat, copy.RepeatSource, copy.RepeatIndex = repeat, source, index
    placement = source.Placement
    copy.Placement = App.Placement(placement.Base + shift, placement.Rotation)
    return copy


def drop_copy(copy: DocumentObject) -> None:
    """Supprime une copie avec sa pièce usinée et ses assemblages, s'il y en a (G)."""
    doc: Document = copy.Document
    machined = machined_part_of(copy)
    if machined is not None:
        name = machined.Name
        remove_joints(list(machined.Joints))  # retire aussi la pièce usinée devenue sans assemblage
        if doc.getObject(name) is not None:
            remove_machined_part(machined)
    doc.removeObject(copy.Name)


class Created(NamedTuple):
    """Objets créés par :func:`apply_repeat`."""

    copies: list[DocumentObject]
    joints: list[DocumentObject]


def apply_repeat(repeat: DocumentObject, params: RepeatParams) -> Created:
    """Met la répétition au réglage ``params`` : écrit ses propriétés, supprime les copies de
    rang supérieur au nombre, crée celles qui manquent (rangs à la suite de l'ancien nombre : une
    copie dissociée ou supprimée à la main ne revient pas), réécrit les expressions de toutes,
    puis recopie les assemblages (``CopyJoints`` vrai : ceux des nouvelles copies, ou de toutes
    si la case vient d'être cochée ; faux : les assemblages enfants sont supprimés). Renvoie les
    copies et les assemblages créés. Aucune transaction ni recalcul."""
    sources = sources_of(repeat)
    resolved = resolve_for(sources, params)
    shifts = offsets(params, source_extent(sources, params.axis))
    previous = int(repeat.Count)
    joints_were_copied = bool(repeat.CopyJoints)
    write_params(repeat, params, resolved)
    created: list[DocumentObject] = []
    for source in sources:
        for copy in copies_of(repeat, source):
            if copy.RepeatIndex > resolved.count:
                drop_copy(copy)
        for index in range(previous + 1, resolved.count + 1):
            shift = shifts[index - 1]
            created.append(_new_copy(source, repeat, index, App.Vector(shift.x, shift.y, shift.z)))
        for copy in copies_of(repeat, source):
            link_copy(copy, source, repeat, params.axis)
    first = previous + 1 if joints_were_copied else 1
    joints = update_joints(
        repeat, enabled=params.copy_joints, ranks=range(first, resolved.count + 1)
    )
    return Created(created, joints)
