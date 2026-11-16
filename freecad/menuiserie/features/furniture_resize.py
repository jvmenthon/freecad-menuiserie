# SPDX-License-Identifier: LGPL-2.1-or-later
"""Cotes d'un ensemble : contrôle, puis écriture (panneau, API, poignées de la vue 3D).

Ni transaction ni recalcul : c'est à l'appelant de les faire.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from typing import Final

from freecad.menuiserie.core.furniture import (
    FurnitureBox,
    Notice,
    follow_rules,
    followed_thicknesses,
)
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.features.freecad_types import DocumentObject, expressions_of
from freecad.menuiserie.features.furniture import DIMENSIONS, writing
from freecad.menuiserie.features.furniture_bindings import bind_members, read_members
from freecad.menuiserie.features.furniture_checks import checked_furniture, quoted_label
from freecad.menuiserie.features.furniture_variants import resize_notices
from freecad.menuiserie.features.i18n import translated, translated_errors

__all__ = ["follow_layers", "planned_resize", "resize", "write_box"]

_DRIVEN_DIMENSION: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "« {label} » : {property} suit une expression ; modifiez cette expression ou l'ensemble "
    "qui la pilote.",
)


def planned_resize(
    furniture: DocumentObject, sizes: Mapping[str, float | None], unlocked: Collection[str] = ()
) -> tuple[FurnitureBox, list[Notice]]:
    """Contrôle (``check_resize``, sous-ensembles compris) des cotes ``sizes`` (``Width``,
    ``Depth``, ``Height`` ; ``None`` = inchangée) : nouvelles cotes et avertissements. Rien n'est
    écrit. ``unlocked`` : clés des pièces à considérer comme déverrouillées."""
    checked_furniture(furniture)
    old = read_members(furniture).box
    changed = {name: value for name, value in sizes.items() if value is not None}
    driven = sorted(set(changed) & set(expressions_of(furniture)))
    if driven:
        params = {**quoted_label(furniture), "property": driven[0]}
        raise ValueError(translated(_DRIVEN_DIMENSION, params))
    values = [changed.get(name, getattr(old, name.lower())) for name in DIMENSIONS]
    with translated_errors():
        new = FurnitureBox(*values)
        return new, resize_notices(furniture, old, new, unlocked)


def resize(furniture: DocumentObject, sizes: Mapping[str, float | None]) -> list[Notice]:
    """Contrôle (:func:`planned_resize`) puis écrit les cotes ``sizes``. Refus avant toute
    écriture (:class:`LockedPiecesError` si une rangée est bloquée par des pièces verrouillées)."""
    new, notices = planned_resize(furniture, sizes)
    return [*write_box(furniture, new, sizes), *notices]


def follow_layers(furniture: DocumentObject, old: FurnitureBox, new: FurnitureBox) -> list[Notice]:
    """Pièces à plat qui remplissent seules une cote de ``furniture`` (une couche ou plusieurs
    empilées, ADR 0062) : quand cette cote passe de ``old`` à ``new``, elles se partagent la
    différence au prorata de leur épaisseur. Tout l'ensemble est relié sur la géométrie d'avant
    avec les nouvelles épaisseurs (comme une épaisseur saisie, ADR 0019), puis elles sont
    écrites. Sans effet s'il n'y en a pas ; renvoie les avertissements de la liaison."""
    members = read_members(furniture, box=old)
    rules, _ = follow_rules(old, members.members)
    thicknesses = followed_thicknesses(old, new, members.members, rules)
    if not thicknesses:
        return []
    notices = bind_members(members, members.objects, thicknesses)
    for key, value in thicknesses.items():
        piece = members.objects[key]
        with writing(piece):
            piece.Thickness = value
    return notices


def write_box(
    furniture: DocumentObject,
    new: FurnitureBox,
    sizes: Mapping[str, float | None],
    *,
    follow: bool = True,
) -> list[Notice]:
    """Écrit les cotes de ``new`` dont ``sizes`` n'est pas ``None``, après avoir fait suivre les
    épaisseurs des pièces à plat qui remplissent seules une cote (:func:`follow_layers`, sauf
    ``follow`` faux : pas d'une poignée, les épaisseurs suivent au relâchement) ; renvoie les
    avertissements de cette liaison."""
    if not follow:
        _write_sizes(furniture, new, sizes)
        return []
    old = read_members(furniture).box
    values = [
        getattr(new, name.lower()) if sizes.get(name) is not None else getattr(old, name.lower())
        for name in DIMENSIONS
    ]
    notices = follow_layers(furniture, old, FurnitureBox(*values))
    _write_sizes(furniture, new, sizes)
    return notices


def _write_sizes(
    furniture: DocumentObject, new: FurnitureBox, sizes: Mapping[str, float | None]
) -> None:
    with writing(furniture):
        for name, value in sizes.items():
            if value is not None:
                setattr(furniture, name, getattr(new, name.lower()))
