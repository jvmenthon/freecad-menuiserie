# SPDX-License-Identifier: LGPL-2.1-or-later
"""Liste de débit (J2b, ADR 0012) : regroupement, totaux, fournitures et CSV, en Python pur.

Ce module est une façade : il ré-exporte l'API publique des sous-modules et ne contient aucune
logique. Enchaînement : ``CutEntry`` (une pièce brute vue) → ``build_cut_list`` → ``CutList`` →
``to_csv``. Les avertissements sont des ``core.notice.Notice`` de nature ``CutNoticeKind``.
"""

from __future__ import annotations

from freecad.menuiserie.core.cutlist._build import CutList, build_cut_list
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
    "FRENCH_CSV",
    "INTERNATIONAL_CSV",
    "NO_ADDITIONS",
    "NO_MARK_DISPLAY",
    "CsvDialect",
    "CutEntry",
    "CutLine",
    "CutList",
    "CutNoticeKind",
    "Hardware",
    "HardwareKind",
    "InvalidCutEntryError",
    "MaterialTotal",
    "TableSection",
    "additions_remark",
    "build_cut_list",
    "format_number",
    "neutralize_formula",
    "table_sections",
    "to_csv",
]
