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

__all__ = [
    "DEFAULT_FORMAT",
    "PAGE_FORMATS",
    "SCALES",
    "Orientation",
    "OverallLayout",
    "PageSize",
    "Spot",
    "overall_layout",
    "page_size",
    "pick_template",
    "scale_text",
]
