# SPDX-License-Identifier: LGPL-2.1-or-later
"""Liaisons refaites quand la composition d'un ensemble change (ADR 0019, point 6).

Une épaisseur, un réglage ou le retrait d'une pièce change la rangée des autres membres : tout
l'ensemble est relié, dans la transaction en cours, d'après la géométrie d'avant le changement
(cohérente), pour qu'après le recalcul aucune pièce ne se chevauche et qu'aucune expression ne
vise une pièce absente.
"""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import replace

from freecad.menuiserie.core.furniture import Notice
from freecad.menuiserie.features.distance import distance_furniture, remove_touching
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.furniture import furniture_of
from freecad.menuiserie.features.furniture_bindings import (
    bind_members,
    notice_messages,
    read_members,
    report,
)
from freecad.menuiserie.features.furniture_variants import with_thickness

__all__ = ["distance_removed", "member_removed", "relink_remaining", "relink_thickness"]


def relink_thickness(
    furniture: DocumentObject, obj: DocumentObject, thickness: float, previous: float | None = None
) -> list[Notice]:
    """Relie tout l'ensemble pour que ``obj`` prenne l'épaisseur ``thickness`` : les liaisons sont
    calculées sur la géométrie d'avant (cohérente), les termes figés en constante d'une autre
    pièce prenant la nouvelle épaisseur. ``previous`` : épaisseur d'avant, si ``obj`` porte déjà
    la nouvelle (saisie de l'éditeur de propriétés)."""
    members = read_members(furniture)
    if previous is not None:
        members = with_thickness(members, obj.Name, previous)
    return bind_members(members, members.objects, {obj.Name: thickness})


def relink_remaining(
    furniture: DocumentObject, removed: Collection[str] = (), ignoring: Collection[str] = ()
) -> list[Notice]:
    """Relie les membres de ``furniture`` sans ceux de nom ``removed`` (pièces supprimées ou
    retirées) et sans les Distances de nom ``ignoring`` : leurs voisines ne citent plus leur
    épaisseur ni leur valeur. Les Distances gardées qui touchent une pièce de ``removed`` sont
    supprimées avec elle (F6)."""
    remove_touching(furniture.Document, removed)
    members = read_members(furniture, ignoring=ignoring)
    kept = tuple(m for m in members.members if m.key not in removed)
    objects = {name: obj for name, obj in members.objects.items() if name not in removed}
    return bind_members(replace(members, members=kept, objects=objects), objects)


def member_removed(obj: DocumentObject) -> None:
    """Pièce membre supprimée (``unsetupObject``) : ses voisines sont reliées sans elle, dans la
    transaction de la suppression. Sans effet hors ensemble, pendant une annulation ou une
    restauration."""
    furniture = furniture_of(obj)
    if furniture is None or "Restore" in furniture.State or obj.Document.Transacting:
        return
    try:
        report(notice_messages(relink_remaining(furniture, {obj.Name})))
    except (
        ValueError
    ) as error:  # cote ou libellé illisible, cycle : liaisons laissées telles quelles
        report([str(error)])


def distance_removed(obj: DocumentObject) -> None:
    """Distance supprimée (``unsetupObject``) : l'ensemble est relié sans elle, dans la transaction
    de la suppression ; les pièces ne bougent pas (F6). Sans effet si ses pièces ne sont plus
    dans un même ensemble, pendant une annulation ou une restauration."""
    furniture = distance_furniture(obj)
    if furniture is None or "Restore" in furniture.State or obj.Document.Transacting:
        return
    try:
        report(notice_messages(relink_remaining(furniture, (), {obj.Name})))
    except (
        ValueError
    ) as error:  # cote ou libellé illisible, cycle : liaisons laissées telles quelles
        report([str(error)])
