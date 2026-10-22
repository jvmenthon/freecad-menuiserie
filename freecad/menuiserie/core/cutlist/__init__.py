# SPDX-License-Identifier: LGPL-2.1-or-later
"""Liste de débit (J2b, ADR 0012 puis 0013) : regroupement, totaux, fournitures, CSV, HTML et
numérotation des repères et miniatures isométriques, en Python pur.

Ce module est une façade : il ré-exporte l'API publique des sous-modules et ne contient aucune
logique. Enchaînement : ``CutEntry`` (une pièce brute vue) → ``build_cut_list`` → ``CutList`` →
``to_csv`` / ``to_html``. Les avertissements sont des ``core.notice.Notice`` de nature
``CutNoticeKind``.
"""

from __future__ import annotations

from freecad.menuiserie.core.cutlist._build import CutList, GroupKey, build_cut_list, group_key
from freecad.menuiserie.core.cutlist._csv import (
    FRENCH_CSV,
    INTERNATIONAL_CSV,
    CsvDialect,
    TableSection,
    additions_remark,
    format_number,
    neutralize_formula,
    table_sections,
    to_csv,
)
from freecad.menuiserie.core.cutlist._html import to_html
from freecad.menuiserie.core.cutlist._marks import DEFAULT_MARK_PREFIX, assign_marks
from freecad.menuiserie.core.cutlist._model import (
    NO_ADDITIONS,
    NO_MARK_DISPLAY,
    CutEntry,
    CutLine,
    CutNoticeKind,
    Hardware,
    HardwareKind,
    InvalidCutEntryError,
    MaterialTotal,
)
from freecad.menuiserie.core.cutlist._thumbnail import (
    DEFAULT_COLOR,
    THUMBNAIL_HEIGHT,
    THUMBNAIL_WIDTH,
    Point2,
    Point3,
    ThumbFace,
    box_faces,
    isometric,
    svg_data_uri,
    thumbnail_svg,
)

__all__ = [
    "DEFAULT_COLOR",
    "DEFAULT_MARK_PREFIX",
    "FRENCH_CSV",
    "INTERNATIONAL_CSV",
    "NO_ADDITIONS",
    "NO_MARK_DISPLAY",
    "THUMBNAIL_HEIGHT",
    "THUMBNAIL_WIDTH",
    "CsvDialect",
    "CutEntry",
    "CutLine",
    "CutList",
    "CutNoticeKind",
    "GroupKey",
    "Hardware",
    "HardwareKind",
    "InvalidCutEntryError",
    "MaterialTotal",
    "Point2",
    "Point3",
    "TableSection",
    "ThumbFace",
    "additions_remark",
    "assign_marks",
    "box_faces",
    "build_cut_list",
    "format_number",
    "group_key",
    "isometric",
    "neutralize_formula",
    "svg_data_uri",
    "table_sections",
    "thumbnail_svg",
    "to_csv",
    "to_html",
]
