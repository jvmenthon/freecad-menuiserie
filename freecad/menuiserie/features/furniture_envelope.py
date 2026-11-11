# SPDX-License-Identifier: LGPL-2.1-or-later
"""Cotes d'un ensemble recalées sur l'enveloppe de ses membres (ADR 0049).

Après un déplacement ou une rotation d'un sous-ensemble, la boîte de l'ensemble parent devient
exactement la boîte qui enveloppe ses membres (pièces et sous-ensembles, rotation comprise), sans
marge : elle grandit ou rétrécit (jv, 2026-11-11 : « la boîte doit toujours être de la taille de
l'ensemble »).
Rien ne bouge : seuls ``Origin`` et les cotes du parent sont écrits, puis ses liaisons sont
recalculées d'après la géométrie actuelle (``furniture_drag._relink``).

Seul un ensemble de plus haut niveau est recalé : la position d'un sous-ensemble est portée par le
``Placement`` de son Std Part avec un ``Origin`` nul (ADR 0038), qu'un recalage décalerait. Un
parent n'est pas recalé non plus quand une formule autre qu'une liaison de l'atelier pilote son
``Origin`` ou une cote, ou les lit (répétition « Suivre le redimensionnement », formule de
l'utilisateur sur un membre) : le recaler ferait bouger ce qui en dépend.
"""

from __future__ import annotations

import re
from typing import Final

import FreeCAD as App

from freecad.menuiserie.core.geometry import Box
from freecad.menuiserie.features.freecad_types import DocumentObject, expressions_of
from freecad.menuiserie.features.furniture import furniture_of, writing
from freecad.menuiserie.features.furniture_bindings import members_of, workshop_expressions
from freecad.menuiserie.features.furniture_container import carried_furniture
from freecad.menuiserie.features.furniture_drag_state import furniture_box, write_sizes
from freecad.menuiserie.features.furniture_enclosing import corner_box, corners_of

__all__ = ["frame_of", "member_envelope", "reframe", "restore_frame"]

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


def reframe(furniture: DocumentObject) -> bool:
    """Recale ``Origin`` et les cotes de ``furniture`` sur l'enveloppe de ses membres, sans
    recalcul ni liaison (l'appelant relie ensuite les membres). Faux, sans rien écrire, pour un
    sous-ensemble, un ensemble piloté ou lu par une formule, sans membre ou déjà à l'enveloppe."""
    if furniture_of(furniture) is not None or _driven(furniture):
        return False
    envelope = member_envelope(furniture)
    if envelope is None:
        return False
    current = frame_of(furniture)
    if all(
        abs(current.lo(i) - envelope.lo(i)) <= TOLERANCE_MM
        and abs(current.hi(i) - envelope.hi(i)) <= TOLERANCE_MM
        for i in range(3)
    ):
        return False
    restore_frame(furniture, envelope)
    return True
