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

from dataclasses import replace
from typing import Final

from freecad.menuiserie.core.furniture import (
    BlockedRowError,
    Edge,
    FurnitureBox,
    FurnitureError,
    InteriorMode,
    Member,
    Notice,
    bindings_for,
    check_thickness,
    follow_rules,
)
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.features.freecad_types import DocumentObject, has_expression
from freecad.menuiserie.features.furniture import (
    MEMBER_OPTIONS,
    follows_user_changes,
    furniture_of,
    option_name,
)
from freecad.menuiserie.features.furniture_bindings import (
    MemberSet,
    bind_members,
    joined_pairs,
    locked_error,
    notice_messages,
    read_members,
    report,
    resize_notices,
    with_locks,
    with_thickness,
)
from freecad.menuiserie.features.i18n import templated_message, translated

__all__ = ["member_option_changed", "report_resize", "thickness_changed", "thickness_notices"]

_RELINK: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Les liaisons des autres pièces de l'ensemble ne tiennent pas compte de ce réglage : "
    "utilisez « Relier les pièces ».",
)


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
        raise locked_error(error, members.objects) from error
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
    try:
        old = float(previous[0])  # type: ignore[arg-type]
        new = float(obj.Thickness.Value)
        if old != new:
            report(notice_messages(thickness_notices(furniture, obj, new, previous=old)))
    except FurnitureError as error:
        report([templated_message(error)])
    except ValueError as error:
        report([str(error)])


def _with_option(member: Member, prop: str, value: object) -> Member:
    """``member`` avec le réglage ``prop`` à ``value`` (mode, option « fixe » ou verrou)."""
    if prop == "PositionMode":
        try:
            return replace(member, mode=InteriorMode(value))
        except ValueError:  # valeur d'une version plus récente : la pièce ne bouge pas
            return replace(member, mode=InteriorMode.STAY)
    if prop == "Locked":
        return replace(member, locked=bool(value))
    edge = next(edge for edge in Edge if option_name(edge) == prop)
    fixed = member.fixed or frozenset()
    return replace(member, fixed=fixed | {edge} if value else fixed - {edge})


def _others_bindings(members: MemberSet, key: str) -> frozenset[tuple[str, str, str]]:
    """Liaisons (clé, propriété, expression) de tous les membres sauf ``key``."""
    others = {member.key for member in members.members if member.key != key}
    rules, _ = follow_rules(members.box, members.members, others)
    bindings, _ = bindings_for(
        str(members.furniture.Label),
        members.members,
        rules,
        keys=others,
        nested=furniture_of(members.furniture) is not None,
    )
    return frozenset((b.key, b.prop, b.expression) for b in bindings)


def _others_stale(members: MemberSet, obj: DocumentObject, prop: str, before: object) -> bool:
    """Vrai si le réglage ``prop`` de ``obj`` (``before`` : sa valeur d'avant) change la rangée
    d'autres membres : leurs liaisons ne seraient plus celles que l'atelier poserait."""
    earlier = replace(
        members,
        members=tuple(
            _with_option(m, prop, before) if m.key == obj.Name else m for m in members.members
        ),
    )
    return _others_bindings(members, obj.Name) != _others_bindings(earlier, obj.Name)


def member_option_changed(
    obj: DocumentObject, prop: str, previous: tuple[object] | None = None
) -> None:
    """Réglage changé par l'utilisateur (éditeur de propriétés, script) : recalcule et écrit les
    seules liaisons de ``obj``, dans la transaction en cours ; avertit si les liaisons d'autres
    membres sont à refaire (« Relier les pièces »). ``previous`` : ``(valeur d'avant,)``."""
    if prop not in MEMBER_OPTIONS:
        return
    furniture = furniture_of(obj)
    if furniture is None or not follows_user_changes(obj):  # ni recalcul, ni annulation
        return
    try:
        members = read_members(furniture)
        messages = list(notice_messages(bind_members(members, [obj.Name])))
        if previous is not None and _others_stale(members, obj, prop, previous[0]):
            messages.append(translated(_RELINK))
        report(messages)
    except ValueError as error:  # libellé ou cote illisible : liaisons laissées telles quelles
        report([str(error)])
