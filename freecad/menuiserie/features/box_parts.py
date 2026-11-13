# SPDX-License-Identifier: LGPL-2.1-or-later
"""Pièces qui sont des boîtes : seules à recevoir un profil d'arête (issue #5, ADR 0029).

Une pièce de bois (``WoodPart``) est une boîte par construction. Une pièce en bois à forme
dessinée (``ShapedPart``) l'est quand son solide remplit exactement son encombrement (un
rectangle extrudé, par exemple) : ses arêtes sont alors celles d'une boîte et ses codes
(``"Z+Y-"``) désignent les mêmes arêtes. Une autre forme est refusée avec un message clair.
"""

from __future__ import annotations

from typing import Final

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.text import quoted_value
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.features.shaped_part import base_shape_of, is_shaped_part
from freecad.menuiserie.features.wood_part import is_wood_part

__all__ = ["box_part_refusal", "is_box_part"]

_FILL: Final = 1e-6  # le volume du solide égale celui de son encombrement, à ce rapport près
_SHAPED: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "« {label} » est une pièce en bois à forme dessinée qui n'est pas une simple boîte : les "
    "profils d'arête ne s'appliquent qu'aux boîtes.",
)
_NOT_A_WOOD_PART: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "« {label} » n'est pas une pièce de bois : elle ne peut pas recevoir de profil."
)


def is_box_part(obj: object) -> bool:
    """Vrai pour une pièce de bois, ou une pièce en bois dont le solide est une boîte."""
    if is_wood_part(obj):
        return True
    if not is_shaped_part(obj):
        return False
    shape = base_shape_of(obj)
    if shape.isNull() or len(shape.Solids) != 1:
        return False
    box = shape.BoundBox
    enclosing = box.XLength * box.YLength * box.ZLength
    return bool(enclosing > 0 and abs(shape.Volume - enclosing) <= _FILL * enclosing)


def box_part_refusal(part: DocumentObject) -> str | None:
    """Message traduit qui dit pourquoi ``part`` ne peut pas recevoir de profil, ``None`` si elle
    le peut."""
    if is_box_part(part):
        return None
    label = quoted_value(part.Label)
    key = _SHAPED if is_shaped_part(part) else _NOT_A_WOOD_PART
    return translated(key, {"label": label})
