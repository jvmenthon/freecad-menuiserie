# SPDX-License-Identifier: LGPL-2.1-or-later
"""Cotes d'un ensemble recalées sur l'enveloppe de ses membres (ADR 0049, ADR 0065).

La boîte d'un ensemble devient exactement la boîte qui enveloppe ses membres (pièces et
sous-ensembles, rotation comprise), sans marge : elle grandit ou rétrécit (jv, 2026-11-11 : « la
boîte doit toujours être de la taille de l'ensemble » ; 2026-11-17 : « les boîtes doivent toujours
être recalculées », sous-ensembles compris). Rien ne bouge dans le document : l'appelant relie
ensuite les membres d'après la géométrie actuelle
(:func:`~freecad.menuiserie.features.furniture_reframe.relink_framed`).

Ensemble de plus haut niveau : ``Origin`` et cotes sont écrits. Sous-ensemble (ADR 0065) : son
``Origin`` reste nul (sa position est portée par le ``Placement`` de son Std Part, ADR 0038) ; le
Std Part avance du coin bas de l'enveloppe et ses membres reculent d'autant dans son repère, donc
rien ne bouge dans la vue. Un ensemble n'est pas recalé quand une formule autre qu'une liaison de
l'atelier pilote son ``Origin`` ou une cote, ou les lit (répétition « Suivre le
redimensionnement », formule de l'utilisateur sur un membre), ni un sous-ensemble dont un membre
est placé par une telle formule : le recaler ferait bouger ce qui en dépend.
"""

from __future__ import annotations

import re
from typing import Final

import FreeCAD as App

from freecad.menuiserie.core.geometry import Box, Vec3
from freecad.menuiserie.features.freecad_types import DocumentObject, expressions_of
from freecad.menuiserie.features.furniture import furniture_of, is_furniture, writing
from freecad.menuiserie.features.furniture_bindings import members_of, workshop_expressions
from freecad.menuiserie.features.furniture_container import (
    carried_furniture,
    member_expressions,
    std_part_of,
)
from freecad.menuiserie.features.furniture_drag_state import (
    furniture_box,
    write_sizes,
    write_std_placement,
)
from freecad.menuiserie.features.furniture_enclosing import corner_box, corners_of
from freecad.menuiserie.features.raw_placement import write_placement

__all__ = ["frame_of", "member_envelope", "overflows", "reframe", "restore_frame"]

TOLERANCE_MM: Final = 1e-6
_FRAME_PROPERTIES: Final = ("Origin", "Width", "Depth", "Height")

frame_of = furniture_box  # boîte actuelle (``Origin`` et cotes), pour la remettre en cas de refus


def member_envelope(furniture: DocumentObject) -> Box | None:
    """Boîte qui enveloppe les membres de ``furniture``, dans le repère de son Std Part (celui où
    se lit ``Origin``) ; ``None`` sans membre."""
    return corner_box([point for obj in members_of(furniture) for point in corners_of(obj)])


def _reads_frame(furniture: DocumentObject) -> re.Pattern[str]:
    """Référence à ``Origin`` ou à une cote de ``furniture`` dans une expression (par nom ou par
    ``<<libellé>>``)."""
    names = "|".join((re.escape(furniture.Name), re.escape(f"<<{furniture.Label}>>")))
    return re.compile(rf"(?<![\w.])(?:{names})\.(?:{'|'.join(_FRAME_PROPERTIES)})\b")


def _workshop_texts(obj: DocumentObject, furniture: DocumentObject) -> set[str]:
    """Textes des liaisons de l'atelier portées par ``obj`` (un membre de ``furniture`` ou le Std
    Part d'un sous-ensemble membre) ; vide pour tout autre objet."""
    owner = carried_furniture(obj) or obj
    if furniture_of(owner) != furniture:
        return set()
    return set(workshop_expressions(owner).values())


def _driven(furniture: DocumentObject) -> bool:
    """Vrai si une formule autre qu'une liaison de l'atelier pilote ``Origin`` ou une cote de
    ``furniture``, ou les lit depuis un objet qui en dépend."""
    workshop = workshop_expressions(furniture)
    if any(
        path.split(".")[0] in _FRAME_PROPERTIES and path not in workshop
        for path in expressions_of(furniture)
    ):
        return True
    reads = _reads_frame(furniture)
    for obj in furniture.InList:
        mine = _workshop_texts(obj, furniture)
        if any(text not in mine and reads.search(text) for text in expressions_of(obj).values()):
            return True
    return False


def restore_frame(furniture: DocumentObject, frame: Box) -> None:
    """Écrit ``Origin`` et les cotes de ``frame`` (boîte lue par :func:`frame_of`)."""
    with writing(furniture):
        furniture.Origin = App.Vector(frame.min.x, frame.min.y, frame.min.z)
        write_sizes(furniture, frame)


def _placed_by_formula(member: DocumentObject) -> bool:
    """Vrai si une formule autre qu'une liaison de l'atelier place ``member`` (copie d'une
    répétition, formule de l'utilisateur)."""
    workshop = workshop_expressions(member)
    return any(
        path.split(".")[0] == "Placement" and path not in workshop
        for path in member_expressions(member)
    )


def _movable(furniture: DocumentObject) -> bool:
    """Vrai si le contenu du sous-ensemble ``furniture`` peut être décalé dans son Std Part : ni
    son Std Part ni un de ses membres n'est placé par une formule autre qu'une liaison de
    l'atelier (le recalcul défairait le décalage)."""
    if std_part_of(furniture) is None:
        return False
    return not any(_placed_by_formula(obj) for obj in (furniture, *members_of(furniture)))


def _frames(furniture: DocumentObject) -> tuple[Box, Box] | None:
    """Boîte actuelle de ``furniture`` et enveloppe de ses membres ; ``None`` pour un ensemble
    qu'on ne recale pas : piloté ou lu par une formule, sans membre, sous-ensemble dont le
    contenu ne peut pas être décalé."""
    if _driven(furniture):
        return None
    if furniture_of(furniture) is not None and not _movable(furniture):
        return None
    envelope = member_envelope(furniture)
    return None if envelope is None else (frame_of(furniture), envelope)


def _same(first: Box, second: Box) -> bool:
    return all(
        abs(first.lo(i) - second.lo(i)) <= TOLERANCE_MM
        and abs(first.hi(i) - second.hi(i)) <= TOLERANCE_MM
        for i in range(3)
    )


def reframe(furniture: DocumentObject) -> bool:
    """Recale ``Origin`` et les cotes de ``furniture`` sur l'enveloppe de ses membres, sans
    recalcul ni liaison (l'appelant relie ensuite les membres). Faux, sans rien écrire, pour un
    ensemble qu'on ne recale pas (:func:`_frames`) ou déjà à l'enveloppe."""
    frames = _frames(furniture)
    if frames is None or _same(*frames):
        return False
    envelope = frames[1]
    if furniture_of(furniture) is not None:  # sous-ensemble : Origin nul, le Std Part avance
        _shift_contents(furniture, envelope.min)
        envelope = Box(Vec3(0.0, 0.0, 0.0), envelope.max - envelope.min)
    restore_frame(furniture, envelope)
    return True


def _shift_contents(furniture: DocumentObject, offset: Vec3) -> None:
    """Std Part du sous-ensemble ``furniture`` avancé de ``offset`` (repère du Std Part) et ses
    membres reculés d'autant : rien ne bouge dans la vue."""
    part = std_part_of(furniture)
    if part is None or max(abs(offset.x), abs(offset.y), abs(offset.z)) <= TOLERANCE_MM:
        return
    back = App.Vector(-offset.x, -offset.y, -offset.z)
    for member in members_of(furniture):
        if is_furniture(member):
            inner = std_part_of(member)
            if inner is not None:
                write_std_placement(inner, _moved(inner.Placement, back))
        elif "Placement" in member.PropertiesList:  # membre sans position : rien à décaler
            write_placement(member, _moved(member.Placement, back))
    start = App.Placement(part.Placement)
    ahead = start.Rotation.multVec(App.Vector(offset.x, offset.y, offset.z))
    write_std_placement(part, App.Placement(start.Base + ahead, start.Rotation))


def _moved(placement: App.Placement, shift: App.Vector) -> App.Placement:
    return App.Placement(placement.Base + shift, placement.Rotation)


def overflows(furniture: DocumentObject) -> bool:
    """Vrai si un membre de ``furniture`` dépasse de sa boîte actuelle (au-delà de
    :data:`TOLERANCE_MM`)."""
    envelope = member_envelope(furniture)
    if envelope is None:
        return False
    frame = frame_of(furniture)
    return any(
        envelope.lo(i) < frame.lo(i) - TOLERANCE_MM or envelope.hi(i) > frame.hi(i) + TOLERANCE_MM
        for i in range(3)
    )
