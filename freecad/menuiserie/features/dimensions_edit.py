# SPDX-License-Identifier: LGPL-2.1-or-later
"""Édition des épaisseurs et formats personnels : textes et listes de l'éditeur (ADR 0028, 0069).

Sans Qt : la fenêtre (``gui/dimensions_dialog.py``) n'est que l'habillage de ces fonctions, testées
seules. Les textes passent par une fonction de traduction injectée (``translate_text`` par défaut).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.user_dimensions import DEFAULT_SHEETS, UserDimensions
from freecad.menuiserie.features.i18n import format_text, translate_text
from freecad.menuiserie.kit.config.import_model import ImportRow
from freecad.menuiserie.kit.config.page_model import Translate

__all__ = [
    "DIMENSIONS_KEY",
    "ROW_GROUP",
    "ROW_LABEL",
    "ROW_TIP",
    "TEXTS",
    "Entry",
    "builtin_thicknesses",
    "describe",
    "format_mm",
    "format_sheet",
    "import_row",
    "sheet_entries",
    "summary",
    "thickness_entries",
]

DIMENSIONS_KEY: Final = "dimensions"  # clé de la ligne d'aperçu, comme la section du fichier

ROW_GROUP: Final = QT_TRANSLATE_NOOP("Menuiserie", "Épaisseurs et formats")
ROW_LABEL: Final = QT_TRANSLATE_NOOP("Menuiserie", "Épaisseurs et formats personnels")
ROW_TIP: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Ajoutés à ceux de l'atelier. « Rétablir tout » ne les modifie pas."
)
_ONE_THICKNESS: Final = QT_TRANSLATE_NOOP("Menuiserie", "{count} épaisseur")
_MANY_THICKNESSES: Final = QT_TRANSLATE_NOOP("Menuiserie", "{count} épaisseurs")
_ONE_SHEET: Final = QT_TRANSLATE_NOOP("Menuiserie", "{count} format")
_MANY_SHEETS: Final = QT_TRANSLATE_NOOP("Menuiserie", "{count} formats")
_NONE: Final = QT_TRANSLATE_NOOP("Menuiserie", "aucune valeur personnelle")
_NOTHING: Final = QT_TRANSLATE_NOOP("Menuiserie", "aucune")
TEXTS: Final = (
    ROW_GROUP,
    ROW_LABEL,
    ROW_TIP,
    _ONE_THICKNESS,
    _MANY_THICKNESSES,
    _ONE_SHEET,
    _MANY_SHEETS,
    _NONE,
    _NOTHING,
)
_MAX_NAMES: Final = 6  # valeurs citées dans une ligne de l'aperçu


@dataclass(frozen=True)
class Entry:
    """Ligne d'une liste de l'éditeur : texte affiché, valeur (épaisseur ou format) et nature
    (``personal`` : supprimable ; sinon valeur intégrée de l'atelier, en gris)."""

    text: str
    value: float | tuple[float, float]
    personal: bool


def format_mm(value: float) -> str:
    """Longueur en mm sans zéros inutiles (« 19 », « 12,5 »)."""
    return f"{value:g}".replace(".", ",")


def format_sheet(length: float, width: float) -> str:
    """Format « L x l » en mm."""
    return f"{format_mm(length)} x {format_mm(width)}"


def _count(count: int, one: str, many: str, translate: Translate) -> str:
    return format_text(translate(one if count < 2 else many), count=count)


def summary(dimensions: UserDimensions, translate: Translate = translate_text) -> str:
    """« 3 épaisseurs, 1 format » ; « aucune valeur personnelle » si rien n'est personnel."""
    if not dimensions.thicknesses and not dimensions.sheets:
        return translate(_NONE)
    thicknesses = _count(len(dimensions.thicknesses), _ONE_THICKNESS, _MANY_THICKNESSES, translate)
    sheets = _count(len(dimensions.sheets), _ONE_SHEET, _MANY_SHEETS, translate)
    return f"{thicknesses}, {sheets}"


def _listed(names: Sequence[str]) -> str:
    shown = ", ".join(names[:_MAX_NAMES])
    return f"{shown}, …" if len(names) > _MAX_NAMES else shown


def describe(dimensions: UserDimensions, translate: Translate = translate_text) -> str:
    """Valeurs d'une ligne de l'aperçu : « 15, 27 mm ; 2800 x 2070 mm », « aucune » si vide."""
    parts: list[str] = []
    if dimensions.thicknesses:
        parts.append(_listed([format_mm(value) for value in dimensions.thicknesses]) + " mm")
    if dimensions.sheets:
        parts.append(_listed([format_sheet(*sheet) for sheet in dimensions.sheets]) + " mm")
    return " ; ".join(parts) if parts else translate(_NOTHING)


def import_row(
    current: UserDimensions, imported: UserDimensions, translate: Translate = translate_text
) -> ImportRow | None:
    """Ligne « Épaisseurs et formats personnels » de l'aperçu ; ``None`` si le fichier ne change
    rien."""
    if imported == current:
        return None
    return ImportRow(
        DIMENSIONS_KEY,
        translate(ROW_GROUP),
        translate(ROW_LABEL),
        describe(current, translate),
        describe(imported, translate),
        imported,
    )


def builtin_thicknesses(library: Sequence[Sequence[float]]) -> tuple[float, ...]:
    """Épaisseurs intégrées : celles des matériaux de la bibliothèque (``library`` : épaisseurs
    de chaque matériau), triées et sans doublon."""
    return tuple(sorted({value for thicknesses in library for value in thicknesses}))


def thickness_entries(builtin: Sequence[float], dimensions: UserDimensions) -> list[Entry]:
    """Épaisseurs de l'éditeur : les intégrées, puis les personnelles."""
    return [
        *(Entry(format_mm(value), value, False) for value in builtin),
        *(Entry(format_mm(value), value, True) for value in dimensions.thicknesses),
    ]


def sheet_entries(dimensions: UserDimensions) -> list[Entry]:
    """Formats de l'éditeur : ceux du commerce, puis les personnels."""
    return [
        *(Entry(format_sheet(*sheet), sheet, False) for sheet in DEFAULT_SHEETS),
        *(Entry(format_sheet(*sheet), sheet, True) for sheet in dimensions.sheets),
    ]
