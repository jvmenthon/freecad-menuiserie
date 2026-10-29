# SPDX-License-Identifier: LGPL-2.1-or-later
"""Forme de base d'une pièce brute, point de départ de sa pièce usinée (ADR 0006, ADR 0020).

Pièce de bois : sa boîte (``Length`` x ``Width`` x ``Thickness``). Pièce en bois : sa forme
dessinée. Dans les deux cas dans le repère de la pièce (``Placement`` défait).
"""

from __future__ import annotations

from typing import Any, Final

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.text import quoted_value
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.features.shaped_part import base_shape_of, is_shaped_part
from freecad.menuiserie.features.solids import box_shape
from freecad.menuiserie.features.wood_part_record import dimensions_of

__all__ = ["blank_shape", "box_of"]

_NO_SHAPE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Pièce en bois « {label} » sans forme : recalculez le document."
)


def box_of(blank: DocumentObject) -> Any:
    """Boîte d'encombrement de la brute ``blank`` (ses cotes), dans son repère ;
    ``InvalidDimensionsError`` si une cote est invalide."""
    return box_shape(dimensions_of(blank))


def blank_shape(blank: DocumentObject) -> Any:
    """Forme de base de la pièce usinée de ``blank`` : sa boîte, ou sa forme dessinée pour une
    pièce en bois. ``ValueError`` traduite si la pièce en bois n'a pas (encore) de forme."""
    if not is_shaped_part(blank):
        return box_of(blank)
    shape = base_shape_of(blank)
    if shape.isNull():
        raise ValueError(translated(_NO_SHAPE, {"label": quoted_value(blank.Label)}))
    return shape
