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
    notes_band,
    overall_layout,
    page_size,
    scale_text,
)
from freecad.menuiserie.core.drawing._machining import (
    MAX_NOTE_LINES,
    Machining,
    MachiningKind,
    capped,
    machining_lines,
    machinings,
)
from freecad.menuiserie.core.drawing._sheet import (
    TEMPLATE_FILES,
    template_file_name,
    template_svg,
)
from freecad.menuiserie.core.drawing._template import pick_template
from freecad.menuiserie.core.drawing._title import (
    MAX_FIELD_LENGTH,
    TitleFields,
    clean_field,
    placeholder_keys,
    title_block_texts,
)

__all__ = [
    "DEFAULT_FORMAT",
    "MAX_FIELD_LENGTH",
    "MAX_NOTE_LINES",
    "PAGE_FORMATS",
    "SCALES",
    "TEMPLATE_FILES",
    "Machining",
    "MachiningKind",
    "Orientation",
    "OverallLayout",
    "PageSize",
    "Spot",
    "TitleFields",
    "capped",
    "clean_field",
    "machining_lines",
    "machinings",
    "notes_band",
    "overall_layout",
    "page_size",
    "pick_template",
    "placeholder_keys",
    "scale_text",
    "template_file_name",
    "template_svg",
    "title_block_texts",
]
