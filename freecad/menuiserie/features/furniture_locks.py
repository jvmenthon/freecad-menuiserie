# SPDX-License-Identifier: LGPL-2.1-or-later
"""Déverrouiller des pièces puis appliquer une cote ou une épaisseur (ADR 0019, critère D4).

Une rangée bloquée par des pièces verrouillées refuse le changement (``LockedPiecesError``) ;
ces fonctions valident d'abord le changement **avec** les pièces déverrouillées (rien n'est
écrit si la rangée reste bloquée ou si le changement est refusé), puis déverrouillent, relient
tout l'ensemble et écrivent la cote. Ni transaction ni recalcul : c'est à l'appelant
(``api.py``, panneaux) de les faire, pour que le tout soit une seule annulation.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Final

from freecad.menuiserie.core.furniture import Notice
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP, TemplatedError
from freecad.menuiserie.core.text import quoted_value
from freecad.menuiserie.features.distance import is_distance
from freecad.menuiserie.features.freecad_types import DocumentObject, has_expression
from freecad.menuiserie.features.furniture import furniture_of, writing
from freecad.menuiserie.features.furniture_bindings import LockedPiecesError, rebind
from freecad.menuiserie.features.furniture_edits import thickness_notices
from freecad.menuiserie.features.furniture_members import (
    NOT_IN_FURNITURE,
    checked_furniture,
    member_object,
    planned_resize,
    quoted_label,
    write_box,
)
from freecad.menuiserie.features.furniture_relink import relink_thickness
from freecad.menuiserie.features.i18n import templated_message, translated, translated_errors

__all__ = ["refusal_of", "set_member_thickness", "unlock_and_resize", "unlock_and_set_thickness"]

_DRIVEN_THICKNESS: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "« {label} » : Thickness suit une expression ; modifiez cette expression.",
)
_INVALID_THICKNESS: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Épaisseur invalide : « {value} » (nombre fini en mm attendu)."
)


def refusal_of(error: ValueError) -> tuple[str, tuple[DocumentObject, ...]]:
    """Texte traduit d'un refus de cote ou d'épaisseur et pièces verrouillées à proposer de
    déverrouiller (vide si le refus n'en cite aucune), pour les panneaux (G2, G3)."""
    if isinstance(error, LockedPiecesError):
        return str(error), tuple(error.members)
    if isinstance(error, TemplatedError):
        return templated_message(error), ()
    return str(error), ()


def _locked_keys(pieces: Sequence[DocumentObject]) -> tuple[str, ...]:
    """Noms des membres de ``pieces`` (pièces de bois, usinées ou sous-ensembles) qui sont
    membres d'un ensemble. ``ValueError`` traduite sinon, avant toute modification."""
    keys: list[str] = []
    for piece in pieces:
        if is_distance(piece):  # « ne plus garder » : la Distance sera supprimée
            keys.append(piece.Name)
            continue
        member = member_object(piece)
        if furniture_of(member) is None:
            raise ValueError(translated(NOT_IN_FURNITURE, quoted_label(member)))
        keys.append(member.Name)
    return tuple(keys)


def _unlock(
    furniture: DocumentObject,
    pieces: Sequence[DocumentObject],
    thicknesses: Mapping[str, float] | None = None,
) -> list[Notice]:
    """Déverrouille ``pieces`` (une Distance gardée n'est plus gardée : elle est supprimée) puis
    relie tout l'ensemble (sous-ensembles compris) ; ``thicknesses`` : voir
    :func:`~.furniture_bindings.bind_members`."""
    gaps = [piece for piece in pieces if is_distance(piece)]
    members = [piece for piece in pieces if not is_distance(piece)]
    for piece in members:
        member = member_object(piece)
        if member.Locked:
            with writing(member):
                member.Locked = False
    for piece in gaps:
        piece.Document.removeObject(piece.Name)
    return rebind(furniture, thicknesses)


def unlock_and_resize(
    furniture: DocumentObject,
    pieces: Sequence[DocumentObject],
    sizes: Mapping[str, float | None],
) -> list[Notice]:
    """Déverrouille ``pieces``, relie tout l'ensemble puis écrit les cotes ``sizes``
    (``Width``, ``Depth``, ``Height`` ; ``None`` = inchangée). Le changement est contrôlé avant
    toute écriture, pièces déverrouillées : refus (``ValueError`` traduite, rien n'est modifié)
    s'il reste refusé ou si la rangée reste bloquée."""
    keys = _locked_keys(pieces)
    new, notices = planned_resize(furniture, sizes, keys)
    relinked = _unlock(furniture, pieces)
    write_box(furniture, new, sizes)
    return [*relinked, *notices]


def _checked_thickness(
    part: DocumentObject, thickness: float
) -> tuple[DocumentObject, DocumentObject, float]:
    """Membre ``part``, son ensemble et l'épaisseur ``thickness`` valide (mm) ; ``ValueError``
    traduite sinon, avant toute modification."""
    member = member_object(part)
    furniture = furniture_of(member)
    if furniture is None:
        raise ValueError(translated(NOT_IN_FURNITURE, quoted_label(member)))
    checked_furniture(furniture)
    if has_expression(member, "Thickness"):
        raise ValueError(translated(_DRIVEN_THICKNESS, quoted_label(member)))
    if isinstance(thickness, bool) or not isinstance(thickness, int | float):
        thickness = math.nan
    if not math.isfinite(thickness):
        raise ValueError(translated(_INVALID_THICKNESS, {"value": quoted_value(thickness)}))
    return member, furniture, float(thickness)


def unlock_and_set_thickness(
    part: DocumentObject, thickness: float, pieces: Sequence[DocumentObject]
) -> list[Notice]:
    """Déverrouille ``pieces``, relie tout l'ensemble de ``part`` puis écrit son épaisseur
    ``thickness`` (mm). Même contrôle préalable que :func:`unlock_and_resize`."""
    member, furniture, value = _checked_thickness(part, thickness)
    keys = _locked_keys(pieces)
    with translated_errors():
        notices = thickness_notices(furniture, member, value, unlocked=keys)
    relinked = _unlock(furniture, pieces, {member.Name: value})
    with writing(member):
        member.Thickness = value
    return [*relinked, *notices]


def set_member_thickness(part: DocumentObject, thickness: float) -> list[Notice]:
    """Écrit l'épaisseur ``thickness`` (mm) de la pièce de bois ``part``. Pour un membre d'un
    ensemble, elle est contrôlée d'abord (``check_thickness``) : refus avant toute écriture,
    :class:`LockedPiecesError` si une rangée est bloquée par des pièces verrouillées,
    ``ValueError`` traduite sinon. Tout l'ensemble est relié sur la géométrie d'avant, les termes
    figés en constante d'une pièce voisine prenant la nouvelle épaisseur (ADR 0019). Hors
    ensemble, l'épaisseur est simplement écrite. Renvoie les avertissements."""
    if furniture_of(member_object(part)) is None:
        part.Thickness = float(thickness)
        return []
    member, furniture, value = _checked_thickness(part, thickness)
    with translated_errors():
        notices = thickness_notices(furniture, member, value)
    relinked = relink_thickness(furniture, member, value)
    with writing(member):
        member.Thickness = value
    return [*relinked, *notices]
