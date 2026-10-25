# SPDX-License-Identifier: LGPL-2.1-or-later
"""Saisies de l'utilisateur dans l'éditeur de propriétés : cotes, options, épaisseur d'un membre.

Une saisie est toujours appliquée (règle Q4 de J4) ; l'atelier écrit les seules liaisons du
membre modifié, dans la transaction en cours, et avertit dans la vue rapport quand la saisie
casse une pièce ou un assemblage, tombe dans une rangée bloquée par des pièces verrouillées
(ADR 0019), ou laisse des liaisons d'autres membres à refaire (« Relier les pièces »).
Appelé par ``onChanged`` de l'ensemble et de la pièce de bois ; sans effet pendant une
restauration, une annulation, un recalcul ou une écriture de l'atelier.
"""

from __future__ import annotations

from freecad.menuiserie.core.furniture import (
    BlockedRowError,
    FurnitureBox,
    FurnitureError,
    Notice,
    check_thickness,
)
from freecad.menuiserie.features.freecad_types import DocumentObject, has_expression
from freecad.menuiserie.features.furniture import (
    MEMBER_OPTIONS,
    follows_user_changes,
    furniture_of,
    take_previous,
)
from freecad.menuiserie.features.furniture_bindings import (
    bind_members,
    joined_pairs,
    locked_error,
    notice_messages,
    read_members,
    report,
)
from freecad.menuiserie.features.furniture_relink import relink_thickness
from freecad.menuiserie.features.furniture_variants import (
    resize_notices,
    with_locks,
    with_thickness,
)
from freecad.menuiserie.features.i18n import templated_message

__all__ = [
    "member_changed",
    "member_option_changed",
    "report_resize",
    "thickness_changed",
    "thickness_notices",
]


def report_resize(furniture: DocumentObject, old: FurnitureBox, new: FurnitureBox) -> None:
    """Cote saisie dans l'éditeur de propriétés : elle est appliquée (Q4) ; avertissements
    pour les formules de l'utilisateur, pour une pièce ou un assemblage cassé et pour une rangée
    bloquée par des pièces verrouillées."""
    try:
        report(notice_messages(resize_notices(furniture, old, new)))
    except FurnitureError as error:
        report([templated_message(error)])
    except ValueError as error:  # membre illisible, rangée bloquée : message déjà traduit
        report([str(error)])


def thickness_notices(
    furniture: DocumentObject,
    obj: DocumentObject,
    thickness: float,
    *,
    previous: float | None = None,
    unlocked: tuple[str, ...] = (),
) -> list[Notice]:
    """Contrôle (``check_thickness``) d'une épaisseur ``thickness`` pour la pièce ``obj`` de
    ``furniture``, avant toute écriture. ``previous`` : épaisseur d'avant, si ``obj`` porte déjà
    la nouvelle (saisie de l'éditeur) ; ``unlocked`` : clés des pièces à considérer comme
    déverrouillées. :class:`FurnitureError` si l'épaisseur est refusée,
    :class:`LockedPiecesError` si la rangée est bloquée par des pièces verrouillées."""
    members = with_locks(read_members(furniture), unlocked, False)
    if previous is not None:
        members = with_thickness(members, obj.Name, previous)
    try:
        found = check_thickness(
            members.box, members.members, obj.Name, thickness, joined_pairs(members)
        )
    except BlockedRowError as error:
        raise locked_error(error, members.named) from error
    return list(found)


def thickness_changed(obj: DocumentObject, previous: tuple[object] | None) -> None:
    """Épaisseur saisie dans l'éditeur de propriétés pour un membre d'ensemble : elle est
    appliquée ; avertissements si elle casse une pièce ou un assemblage, ou si la rangée est
    bloquée. ``previous`` : ``(épaisseur d'avant,)`` lu par ``onBeforeChange``."""
    furniture = furniture_of(obj)
    if furniture is None or previous is None or has_expression(obj, "Thickness"):
        return
    if not follows_user_changes(obj):
        return
    old, new = float(previous[0]), float(obj.Thickness.Value)  # type: ignore[arg-type]
    if old == new:
        return
    messages: list[str] = []
    try:
        messages += notice_messages(thickness_notices(furniture, obj, new, previous=old))
    except FurnitureError as error:
        messages.append(templated_message(error))
    except ValueError as error:
        messages.append(str(error))
    try:  # les autres pièces suivent la nouvelle épaisseur, quelles que soient les alertes
        messages += notice_messages(relink_thickness(furniture, obj, new, old))
    except ValueError as error:
        messages.append(str(error))
    report(messages)


def member_option_changed(obj: DocumentObject, prop: str) -> None:
    """Réglage changé par l'utilisateur (éditeur de propriétés, script) : tout l'ensemble est
    relié, dans la transaction en cours (le réglage d'un membre change la rangée des autres :
    ADR 0019, point 6). Libellé ou cote illisible, cycle avec une formule de l'utilisateur :
    avertissement, liaisons laissées telles quelles."""
    if prop not in MEMBER_OPTIONS:
        return
    furniture = furniture_of(obj)
    if furniture is None or not follows_user_changes(obj):  # ni recalcul, ni annulation
        return
    try:
        members = read_members(furniture)
        report(notice_messages(bind_members(members, members.objects)))
    except ValueError as error:
        report([str(error)])


def member_changed(obj: DocumentObject, prop: str) -> None:
    """Réglage ou épaisseur d'un membre changé par l'utilisateur (``onChanged`` de la pièce)."""
    previous = take_previous(obj, prop)
    if prop == "Thickness":
        thickness_changed(obj, previous)
    else:
        member_option_changed(obj, prop)
