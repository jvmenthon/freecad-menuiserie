# SPDX-License-Identifier: LGPL-2.1-or-later
"""Sortie d'objets de leur ensemble : liaisons et propriétés de membre (J4b', ADR 0046).

Ni transaction ni recalcul : c'est à l'appelant (``api.py``, commandes, panneau « Structure »).
"""

from __future__ import annotations

from collections.abc import Sequence

from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.furniture import (
    MEMBER_PROPERTIES,
    furniture_of,
    has_member_properties,
    writing,
)
from freecad.menuiserie.features.furniture_bindings import remove_bindings
from freecad.menuiserie.features.furniture_checks import (
    NOT_IN_FURNITURE,
    member_object,
    quoted_label,
)
from freecad.menuiserie.features.furniture_entry import leave
from freecad.menuiserie.features.furniture_relink import relink_remaining
from freecad.menuiserie.features.i18n import translated

__all__ = ["NOT_IN_FURNITURE", "detach_members", "remove_members"]


def detach_members(
    objects: Sequence[DocumentObject], *, keep_properties: bool = False
) -> list[DocumentObject]:
    """Première moitié de :func:`remove_members` : les liaisons de l'atelier et les propriétés de
    membre de ``objects`` sont supprimées, les voisines reliées sans eux ; ils ne sortent pas de
    leur Std Part. Avec ``keep_properties``, les propriétés de membre restent (état d'orphelin,
    comme après la suppression de l'ensemble) et seul le lien ``Furniture`` est remis à zéro :
    FreeCAD 1.1 ne rétablit pas, à l'annulation, une propriété dynamique retirée puis recréée dans
    la même transaction, d'où cette voie pour changer d'ensemble ou sortir depuis le panneau
    « Structure ». Renvoie ceux qui avaient un ensemble. ``ValueError`` traduite, avant toute
    modification, pour un objet qui n'est membre d'aucun ensemble."""
    targets = {member.Name: member for member in map(member_object, objects)}
    for member in targets.values():
        if not has_member_properties(member):
            raise ValueError(translated(NOT_IN_FURNITURE, quoted_label(member)))
    furnitures = {f.Name: f for f in (furniture_of(m) for m in targets.values()) if f is not None}
    owned = [member for member in targets.values() if furniture_of(member) is not None]
    for member in targets.values():
        with writing(member):
            remove_bindings(member)
            if keep_properties:
                member.Furniture = None
                member.FurnitureBindings = {}
                continue
            for spec in MEMBER_PROPERTIES:
                if spec.name in member.PropertiesList:
                    member.removeProperty(spec.name)
    for furniture in furnitures.values():  # les voisines ne citent plus les pièces retirées
        relink_remaining(furniture, set(targets))
    return owned


def remove_members(
    objects: Sequence[DocumentObject], *, keep_properties: bool = False
) -> list[str]:
    """Retire ``objects`` de leur ensemble : les liaisons de l'atelier et les propriétés de membre
    sont supprimées (gardées avec ``keep_properties``, :func:`detach_members`), puis ils sortent
    du Std Part de l'ensemble sans bouger (E2) ; la géométrie ne change pas. Un orphelin
    (ensemble supprimé) est accepté. Les pièces qui restent sont reliées sans elles. Renvoie les
    avertissements traduits (pièce assemblée à une pièce qui reste : elle garde son Std Part)."""
    return leave(detach_members(objects, keep_properties=keep_properties))
