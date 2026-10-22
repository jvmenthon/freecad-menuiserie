# SPDX-License-Identifier: LGPL-2.1-or-later
"""Liste de débit (J2b, ADR 0012 puis 0013) : regroupement, totaux, fournitures, CSV, HTML et
numérotation des repères, en Python pur.

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

__all__ = [
    "DEFAULT_MARK_PREFIX",
    "FRENCH_CSV",
    "INTERNATIONAL_CSV",
    "NO_ADDITIONS",
    "NO_MARK_DISPLAY",
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
    "TableSection",
    "additions_remark",
    "assign_marks",
    "build_cut_list",
    "format_number",
    "group_key",
    "neutralize_formula",
    "table_sections",
    "to_csv",
    "to_html",
]
