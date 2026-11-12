# SPDX-License-Identifier: LGPL-2.1-or-later
"""Plans cotés : mise en page et choix du gabarit, sans FreeCAD (issue #153, ADR 0053)."""

from __future__ import annotations

from freecad.menuiserie.core.drawing._layout import (
    DEFAULT_FORMAT,
    PAGE_FORMATS,
    SCALES,
    Orientation,
    OverallLayout,
    PageSize,
    Spot,
    overall_layout,
    page_size,
    scale_text,
)
from freecad.menuiserie.core.drawing._template import pick_template
from freecad.menuiserie.core.drawing._title import (
    MAX_FIELD_LENGTH,
    TitleFields,
    clean_field,
    title_block_texts,
)

__all__ = [
    "DEFAULT_FORMAT",
    "MAX_FIELD_LENGTH",
    "PAGE_FORMATS",
    "SCALES",
    "Orientation",
    "OverallLayout",
    "PageSize",
    "Spot",
    "TitleFields",
    "clean_field",
    "overall_layout",
    "page_size",
    "pick_template",
    "scale_text",
    "title_block_texts",
]
