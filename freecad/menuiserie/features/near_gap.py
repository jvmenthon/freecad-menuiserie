# SPDX-License-Identifier: LGPL-2.1-or-later
"""Rapprocher deux pièces proches qui ne se touchent pas, avant de les assembler (ADR 0039).

:func:`closing_options` dit si deux pièces sont proches (écart de :data:`~.near_gap.NEAR_GAP_MM`
au plus, sur un seul axe) et ce qu'on peut faire : **déplacer** une pièce jusqu'au contact
(``MOVE``) ou **agrandir** une pièce jusqu'au contact (``GROW``). :func:`close_gap` l'exécute par
``features/part_drag`` (déplacement et poignée de taille de la souris) : un membre d'ensemble est
relié ensuite, une formule de l'utilisateur ou une cote qui ne se tire pas rend l'option
indisponible. La pièce qui bouge ou grandit est l'invitée, à défaut l'hôte. Aucun import de
``FreeCADGui`` ; la transaction est celle de l'appelant.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

import FreeCAD as App

from freecad.menuiserie.core.geometry import ANGLE_TOLERANCE, Vec3
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.near_gap import NearGap, near_gap
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.features.joints.base import placed_blank
from freecad.menuiserie.features.machined_part import blank_of
from freecad.menuiserie.features.part_drag import (
    SIZE_PROPS,
    begin_drag,
    drag_limits,
    end_drag,
    move_part,
    resize_part,
)

__all__ = ["GROW", "MOVE", "Closing", "close_gap", "closing_options"]

MOVE: Final = "move"
GROW: Final = "grow"

_UNAVAILABLE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Ces pièces ne peuvent pas être rapprochées de cette façon."
)


@dataclass(frozen=True)
class Closing:
    """Écart (mm) entre deux pièces proches et façons de le combler : ``MOVE`` et/ou ``GROW`` →
    nom de la pièce qui bouge ou grandit (vide si aucune ne le peut : cotes pilotées par des
    formules…)."""

    distance: float
    options: dict[str, str]


def _gap_of(reference: DocumentObject, piece: DocumentObject) -> NearGap | None:
    """Écart de la brute ``piece`` à la brute ``reference`` (``None`` si pas proches)."""
    return near_gap(placed_blank(reference), placed_blank(piece))


def _move_delta(reference: DocumentObject, piece: DocumentObject, gap: NearGap) -> Vec3:
    """Déplacement (repère de ``piece``) qui amène ``piece`` au contact de ``reference``."""
    toward = [0.0, 0.0, 0.0]
    toward[gap.axis] = -gap.side * gap.distance
    world = reference.Placement.Rotation.multVec(App.Vector(*toward))
    local = piece.Placement.Rotation.inverted().multVec(world)
    return Vec3(local.x, local.y, local.z)


def _can_move(reference: DocumentObject, piece: DocumentObject, gap: NearGap) -> bool:
    delta = _move_delta(reference, piece, gap)
    fixed = drag_limits(piece).fixed_axes
    return not any(abs(delta.component(axis)) > ANGLE_TOLERANCE for axis in fixed)


def _can_grow(piece: DocumentObject, gap: NearGap) -> bool:
    return gap.b_axis in drag_limits(piece).resizable_axes


def _pieces(
    host: DocumentObject, guest: DocumentObject
) -> list[tuple[DocumentObject, DocumentObject]]:
    """(pièce qui agit, pièce de référence) : l'invitée d'abord, puis l'hôte."""
    blanks = blank_of(host), blank_of(guest)
    return [(blanks[1], blanks[0]), (blanks[0], blanks[1])]


def _actor(
    host: DocumentObject, guest: DocumentObject, how: str
) -> tuple[DocumentObject, DocumentObject, NearGap]:
    """(pièce, référence, écart) de la première pièce qui peut ``how`` ; ``ValueError``
    traduite si aucune."""
    for piece, reference in _pieces(host, guest):
        gap = _gap_of(reference, piece)
        if gap is None:
            break
        allowed = _can_move(reference, piece, gap) if how == MOVE else _can_grow(piece, gap)
        if allowed:
            return piece, reference, gap
    raise ValueError(translated(_UNAVAILABLE))


def closing_options(host: DocumentObject, guest: DocumentObject) -> Closing | None:
    """Écart et façons de le combler si ``host`` et ``guest`` (pièces brutes ou usinées) sont
    proches sans se toucher, ``None`` sinon (en contact, chevauchées, loin, en biais)."""
    first = _pieces(host, guest)[0]
    gap = _gap_of(first[1], first[0])
    if gap is None:
        return None
    options = {}
    for how in (MOVE, GROW):
        try:
            piece = _actor(host, guest, how)[0]
        except ValueError:
            continue
        options[how] = str(piece.Label)
    return Closing(gap.distance, options)


def close_gap(host: DocumentObject, guest: DocumentObject, how: str) -> list[str]:
    """Comble l'écart entre ``host`` et ``guest`` : ``how`` vaut ``MOVE`` (une pièce se déplace
    jusqu'au contact) ou ``GROW`` (une pièce s'agrandit jusqu'au contact). Recalcule le document
    et renvoie les avertissements de ``end_drag`` ; ``ValueError`` traduite si l'option n'est pas
    permise ou si l'ensemble refuse le changement (la pièce revient)."""
    if how not in (MOVE, GROW):
        raise ValueError(translated(_UNAVAILABLE))
    piece, reference, gap = _actor(host, guest, how)
    memento = begin_drag(piece)
    if how == MOVE:
        move_part(memento, _move_delta(reference, piece, gap))
        return end_drag(memento)
    prop = SIZE_PROPS[gap.b_axis]
    shift = Vec3.of([-gap.distance if gap.b_low and i == gap.b_axis else 0.0 for i in range(3)])
    resize_part(memento, prop, getattr(piece, prop).Value + gap.distance, shift)
    return end_drag(memento)
