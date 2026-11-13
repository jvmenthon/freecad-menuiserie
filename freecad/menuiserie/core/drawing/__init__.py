# SPDX-License-Identifier: LGPL-2.1-or-later
"""Plans cotés : mise en page et choix du gabarit, sans FreeCAD (issue #153, ADR 0053)."""

from __future__ import annotations

from freecad.menuiserie.core.drawing._details import chain_segments, slant_angle
from freecad.menuiserie.core.drawing._joint_notes import (
    NoteLine,
    bevel_line,
    joint_note_lines,
    machining_name,
)
from freecad.menuiserie.core.drawing._layout import (
    CHAR_WIDTH_RATIO,
    DEFAULT_FORMAT,
    PAGE_FORMATS,
    SCALES,
    Orientation,
    OverallLayout,
    PageSize,
    Spot,
    corner_iso_layout,
    exploded_offset,
    notes_band,
    notes_layout,
    overall_layout,
    page_size,
    scale_text,
    single_view_layout,
)
from freecad.menuiserie.core.drawing._machining import (
    CONTINUATION,
    MAX_NOTE_LINES,
    NAMES,
    Machining,
    MachiningItem,
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
    "CHAR_WIDTH_RATIO",
    "CONTINUATION",
    "DEFAULT_FORMAT",
    "MAX_FIELD_LENGTH",
    "MAX_NOTE_LINES",
    "NAMES",
    "PAGE_FORMATS",
    "SCALES",
    "TEMPLATE_FILES",
    "Machining",
    "MachiningItem",
    "MachiningKind",
    "NoteLine",
    "Orientation",
    "OverallLayout",
    "PageSize",
    "Spot",
    "TitleFields",
    "bevel_line",
    "capped",
    "chain_segments",
    "clean_field",
    "corner_iso_layout",
    "exploded_offset",
    "joint_note_lines",
    "machining_lines",
    "machining_name",
    "machinings",
    "notes_band",
    "notes_layout",
    "overall_layout",
    "page_size",
    "pick_template",
    "placeholder_keys",
    "scale_text",
    "single_view_layout",
    "slant_angle",
    "template_file_name",
    "template_svg",
    "title_block_texts",
]
