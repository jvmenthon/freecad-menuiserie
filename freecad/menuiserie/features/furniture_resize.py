# SPDX-License-Identifier: LGPL-2.1-or-later
"""Redimensionnement d'un ensemble : contrôle des nouvelles cotes puis écriture (J4, N11).

Aucune transaction ni recalcul : c'est à l'appelant (``api.py``, panneau de l'ensemble). Séparé de
``furniture_members`` pour garder ce module court.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from typing import Final

from freecad.menuiserie.core.furniture import FurnitureBox, Notice
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.features.freecad_types import DocumentObject, expressions_of
from freecad.menuiserie.features.furniture import DIMENSIONS, writing
from freecad.menuiserie.features.furniture_bindings import read_members
from freecad.menuiserie.features.furniture_members import checked_furniture, quoted_label
from freecad.menuiserie.features.furniture_variants import resize_notices
from freecad.menuiserie.features.i18n import translated, translated_errors

__all__ = ["planned_resize", "resize", "write_box"]

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
    write_box(furniture, new, sizes)
    return notices


def write_box(
    furniture: DocumentObject, new: FurnitureBox, sizes: Mapping[str, float | None]
) -> None:
    """Écrit les cotes de ``new`` dont ``sizes`` n'est pas ``None``."""
    with writing(furniture):
        for name, value in sizes.items():
            if value is not None:
                setattr(furniture, name, getattr(new, name.lower()))
