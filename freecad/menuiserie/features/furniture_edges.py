# SPDX-License-Identifier: LGPL-2.1-or-later
"""Distance au bord saisie pour un membre d'un ensemble (J4c, panneau et api).

La règle (déplacer la pièce, ou changer sa cote si la distance opposée est fixe) est celle de
:func:`~freecad.menuiserie.core.furniture.edge_edit` ; ce module l'applique au document puis
relie le seul membre modifié. Ni transaction ni recalcul : c'est à l'appelant de les faire.
"""

from __future__ import annotations

import math
from typing import Final

from freecad.menuiserie.core.furniture import Edge, EdgeEdit, Notice, edge_edit
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.text import quoted_value
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.furniture import furniture_of, is_furniture, writing
from freecad.menuiserie.features.furniture_bindings import (
    bind_members,
    read_members,
    remove_bindings,
)
from freecad.menuiserie.features.furniture_members import (
    NOT_IN_FURNITURE,
    UNKNOWN_EDGE,
    member_object,
    quoted_label,
)
from freecad.menuiserie.features.i18n import translated, translated_errors

__all__ = ["set_edge_distance"]

_INVALID_DISTANCE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Distance au bord invalide : « {value} » (nombre fini en mm attendu)."
)


def _shifted(obj: DocumentObject, change: EdgeEdit) -> None:
    """Déplace l'origine locale de ``obj`` (``Placement`` d'une pièce, ``Origin`` d'un
    sous-ensemble) de ``change.shift`` le long de son axe."""
    coordinate = "xyz"[change.axis.index]
    if is_furniture(obj):
        origin = obj.Origin
        setattr(origin, coordinate, getattr(origin, coordinate) + change.shift)
        obj.Origin = origin
        return
    placement = obj.Placement
    base = placement.Base
    setattr(base, coordinate, getattr(base, coordinate) + change.shift)
    placement.Base = base
    obj.Placement = placement


def set_edge_distance(obj: DocumentObject, edge: str, distance: float) -> list[Notice]:
    """Distance ``distance`` (mm) entre la face ``edge`` (``Left`` … ``Top``) d'un membre et
    ce bord de son ensemble : la pièce est déplacée, ou sa cote change si la distance opposée
    est fixe (:func:`~freecad.menuiserie.core.furniture.edge_edit`) ; options inchangées, puis
    tout l'ensemble est relié (la pièce déplacée change la rangée des autres). Refus avant
    modification."""
    member = member_object(obj)
    furniture = furniture_of(member)
    if furniture is None:
        raise ValueError(translated(NOT_IN_FURNITURE, quoted_label(member)))
    if edge not in {item.value for item in Edge}:
        raise ValueError(translated(UNKNOWN_EDGE, {"value": quoted_value(edge)}))
    value = float(distance) if isinstance(distance, int | float) else math.nan
    if not math.isfinite(value) or isinstance(distance, bool):
        raise ValueError(translated(_INVALID_DISTANCE, {"value": quoted_value(distance)}))
    members = read_members(furniture)
    target = next(item for item in members.members if item.key == member.Name)
    with translated_errors():
        change = edge_edit(target, members.box, Edge(edge), value)
    with writing(member):
        remove_bindings(member)
        if change.prop is not None:
            setattr(member, change.prop, change.size)
        if change.shift:
            _shifted(member, change)
    relinked = read_members(furniture)
    return bind_members(relinked, relinked.objects)
