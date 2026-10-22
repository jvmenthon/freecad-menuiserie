# SPDX-License-Identifier: LGPL-2.1-or-later
"""Liste de débit dans une feuille de calcul standard (J2c et J2f, S1 à S3, S6, S7, V3, ADR 0013).

``Spreadsheet::Sheet`` sans proxy, retrouvée par la propriété booléenne masquée
``MenuiserieCutList`` : un document ouvert sans l'atelier garde une feuille ordinaire. La feuille
est réécrite par l'objet ``CutList`` (:mod:`.cutlist_object`) à chaque recalcul ; les colonnes
de l'atelier sont A à O, les cellules de l'utilisateur à partir de P sont conservées. Aucune
formule : tout texte est écrit en littéral (préfixe ``'`` de FreeCAD), les nombres sont déjà
convertis.
"""

from __future__ import annotations

import re
import string
from collections.abc import Iterable, Sequence
from datetime import datetime
from typing import Final

from freecad.menuiserie.core.cutlist import INTERNATIONAL_CSV, CutList, TableSection, table_sections
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.features.freecad_types import HIDDEN, Document, DocumentObject
from freecad.menuiserie.features.i18n import translate_text, translated

__all__ = [
    "DATE_FORMAT",
    "MARKER",
    "SHEET_NAME",
    "TITLE",
    "create_sheet",
    "find_sheet",
    "is_workshop_sheet",
    "rewrite_sheet",
    "scope_text",
]

SHEET_NAME: Final = "MenuiserieCutList"
MARKER: Final = "MenuiserieCutList"
SHEET_TYPE: Final = "Spreadsheet::Sheet"
LAST_COLUMN: Final = "O"  # colonnes de l'atelier : A à O ; P et au-delà appartiennent au menuisier
COLUMNS: Final = string.ascii_uppercase[: string.ascii_uppercase.index(LAST_COLUMN) + 1]
WIDTHS: Final = (70, 40, 90, 90, 90, 90, 90, 90, 150, 70, 120, 110, 80, 80, 300)
DATE_FORMAT: Final = "%Y-%m-%d %H:%M"
_CELL: Final = re.compile(r"([A-Z]+)([0-9]+)$")
_CONTROL: Final = re.compile(r"[\x00-\x1f\x7f]")
_FALLBACK_ROWS: Final = 2000  # balayage si la feuille ne sait pas lister ses cellules utilisées

TITLE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Liste de débit")
_MARKER_TOOLTIP: Final = QT_TRANSLATE_NOOP(
    "App::Property", "Feuille écrite par la commande « Liste de débit » de l'atelier Menuiserie."
)
_DATE_LINE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Calculée le {date} ; mise à jour automatiquement à chaque recalcul du document.",
)
_WHOLE_DOCUMENT: Final = QT_TRANSLATE_NOOP("Menuiserie", "Tout le document")
_SELECTION_ONE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Sélection : 1 objet")
_SELECTION_MANY: Final = QT_TRANSLATE_NOOP("Menuiserie", "Sélection : {count} objets")
_WARNINGS_TITLE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Avertissements")


def find_sheet(doc: Document) -> DocumentObject | None:
    """Feuille de la liste de débit du document (marquée par ``MenuiserieCutList``, même
    renommée), ``None`` s'il n'y en a pas."""
    for obj in doc.Objects:
        if obj.TypeId == SHEET_TYPE and getattr(obj, MARKER, False) is True:
            return obj
    return None


def is_workshop_sheet(obj: object, doc: Document) -> bool:
    """Vrai si ``obj`` est une feuille de la liste de débit **de** ``doc`` : type
    ``Spreadsheet::Sheet``, marque ``MenuiserieCutList`` vraie, même document. Un document
    hostile peut lier ``Sheet`` à n'importe quel objet, d'un autre document ou non."""
    return (
        getattr(obj, "TypeId", None) == SHEET_TYPE
        and getattr(obj, MARKER, False) is True
        and getattr(obj, "Document", None) == doc
    )


def create_sheet(doc: Document) -> DocumentObject:
    sheet = doc.addObject(SHEET_TYPE, SHEET_NAME)
    sheet.addProperty("App::PropertyBool", MARKER, "Menuiserie", _MARKER_TOOLTIP)
    setattr(sheet, MARKER, True)
    sheet.setEditorMode(MARKER, HIDDEN)
    sheet.Label = translated(TITLE)
    return sheet


def _column_of(address: str) -> int:
    """Rang (A = 1) de la colonne d'une adresse de cellule ; 0 si l'adresse est illisible."""
    match = _CELL.match(address)
    if match is None:
        return 0
    rank = 0
    for letter in match.group(1):
        rank = rank * 26 + ord(letter) - ord("A") + 1
    return rank


def _used_cells(sheet: DocumentObject) -> list[str]:
    """Adresses des cellules renseignées (contenu ou style) ; à défaut de méthode pour les
    lister, balayage des colonnes de l'atelier."""
    for name in ("getUsedCells", "getNonEmptyCells"):
        method = getattr(sheet, name, None)
        if method is not None:
            return [str(address) for address in method()]
    return [f"{column}{row}" for column in COLUMNS for row in range(1, _FALLBACK_ROWS + 1)]


def _clear_workshop_columns(sheet: DocumentObject) -> None:
    """Vide les colonnes A à O ; les cellules de P et au-delà (S2) ne sont pas touchées."""
    last = _column_of(f"{LAST_COLUMN}1")
    for address in _used_cells(sheet):
        if 0 < _column_of(address) <= last:
            sheet.clear(address)


def _plain(text: str) -> str:
    return _CONTROL.sub(" ", text)


class _Writer:
    """Écrit des valeurs littérales ligne par ligne et mémorise gras et alignements."""

    def __init__(self, sheet: DocumentObject) -> None:
        self.sheet = sheet
        self.row = 1
        self._bold: list[str] = []
        self._right: list[str] = []

    def text(self, column: int, text: str, bold: bool = False) -> None:
        """Texte littéral : le préfixe ``'`` empêche toute lecture comme formule, nombre ou
        quantité (un repère « 5 mm » reste un texte)."""
        address = f"{COLUMNS[column]}{self.row}"
        self.sheet.set(address, "'" + _plain(text))
        if bold:
            self._bold.append(address)

    def number(self, column: int, text: str, bold: bool = False) -> None:
        """Nombre déjà formaté (point décimal) ; cellule laissée vide si ``text`` l'est."""
        address = f"{COLUMNS[column]}{self.row}"
        self._right.append(address)
        if text:
            self.sheet.set(address, text)
        if bold:
            self._bold.append(address)

    def line(self, cells: Iterable[str], text_columns: frozenset[int], bold: bool = False) -> None:
        """Une ligne de cellules ; les colonnes hors ``text_columns`` sont des nombres."""
        for column, cell in enumerate(cells):
            if column in text_columns:
                self.text(column, cell, bold)
            else:
                self.number(column, cell, bold)
        self.row += 1

    def skip(self) -> None:
        self.row += 1

    def apply_styles(self) -> None:
        """Gras et alignements, une cellule à la fois (adresses simples)."""
        for address in self._bold:
            self.sheet.setStyle(address, "bold")
        for address in self._right:
            self.sheet.setAlignment(address, "right")


def _write_section(writer: _Writer, section: TableSection) -> None:
    if section.title:
        writer.skip()
        writer.text(0, section.title, bold=True)
        writer.row += 1
    writer.line(section.header, section.text_columns, bold=True)
    for cells in section.rows:
        writer.line(cells, section.text_columns)


def scope_text(selection_count: int | None) -> str:
    """Portée affichée : « Tout le document » ou « Sélection : n objet(s) »."""
    if selection_count is None:
        return translated(_WHOLE_DOCUMENT)
    if selection_count == 1:
        return translated(_SELECTION_ONE)
    return translated(_SELECTION_MANY, {"count": str(selection_count)})


def _write_head(writer: _Writer, selection_count: int | None, now: datetime) -> None:
    writer.text(0, translated(TITLE), bold=True)
    writer.row += 1
    writer.text(0, translated(_DATE_LINE, {"date": now.strftime(DATE_FORMAT)}))
    writer.row += 1
    writer.text(0, scope_text(selection_count))
    writer.row += 2


def _write_warnings(writer: _Writer, messages: Sequence[str]) -> None:
    if not messages:
        return
    writer.skip()
    writer.text(0, translated(_WARNINGS_TITLE), bold=True)
    writer.row += 1
    for message in messages:
        writer.text(0, message)
        writer.row += 1


def _fill(
    sheet: DocumentObject,
    cut_list: CutList,
    messages: Sequence[str],
    selection_count: int | None,
    now: datetime,
) -> None:
    writer = _Writer(sheet)
    _write_head(writer, selection_count, now)
    for section in table_sections(cut_list, translate_text, INTERNATIONAL_CSV):
        _write_section(writer, section)
    _write_warnings(writer, messages)
    writer.apply_styles()
    for letter, width in zip(COLUMNS, WIDTHS, strict=True):
        sheet.setColumnWidth(letter, width)


def rewrite_sheet(
    sheet: DocumentObject,
    cut_list: CutList,
    messages: Sequence[str] = (),
    selection_count: int | None = None,
    now: datetime | None = None,
) -> None:
    """Réécrit les colonnes A à O de ``sheet`` d'après ``cut_list`` (celles de P et au-delà sont
    gardées), puis recalcule la feuille et efface sa marque « Touched » (``recompute()`` d'un
    objet seul la laisse). Ni transaction ni recalcul du document : appelée par l'objet
    ``CutList`` pendant le recalcul du document ou dans la transaction de ``make_cut_list``."""
    _clear_workshop_columns(sheet)
    _fill(sheet, cut_list, messages, selection_count, now or datetime.now())
    sheet.recompute()
    sheet.purgeTouched()
