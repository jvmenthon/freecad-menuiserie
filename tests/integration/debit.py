# SPDX-License-Identifier: LGPL-2.1-or-later
"""Aides des tests d'intégration de la liste de débit (J2c) : pièces, liens, lecture de la
feuille. Module d'aide (importé seulement avec FreeCAD)."""

from __future__ import annotations

import zlib
from typing import Any

import pytest

App = pytest.importorskip("FreeCAD")
api = pytest.importorskip("freecad.menuiserie.api")

COLUMNS = "ABCDEFGHIJKLMNO"
LAST_ROW = 80
SHEET_NAME = "MenuiserieCutList"


def default_size(mark: str) -> tuple[float, float, float]:
    """Cotes par défaut propres au repère : deux repères différents ne se regroupent pas (C1')."""
    return (1000.0 + zlib.crc32(mark.encode()) % 1000, 200.0, 22.0)


def part(doc: Any, mark: str, size: tuple[float, float, float] | None = None) -> Any:
    """Pièce de chêne de repère ``mark`` (cotes propres au repère par défaut), recalculée."""
    obj = api.make_wood_part(*(size or default_size(mark)), "chene", mark=mark, doc=doc)
    doc.recompute()
    return obj


def link(doc: Any, target: Any, count: int = 0, name: str = "Lien") -> Any:
    """``App::Link`` vers ``target`` ; tableau de ``count`` liens si ``count`` > 0."""
    obj = doc.addObject("App::Link", name)
    obj.LinkedObject = target
    if count:
        if "ElementCount" not in obj.PropertiesList:
            obj.addProperty("App::PropertyInteger", "ElementCount", "Link", "")
        obj.ElementCount = count
    doc.recompute()
    return obj


def quantities(cut_list: Any) -> dict[str, int]:
    """Quantité par ligne, clé = repères affichés (« M1, M2 » pour une ligne regroupée)."""
    return {line.display_mark: line.quantity for line in cut_list.lines}


def marks_of(cut_list: Any) -> set[str]:
    """Tous les repères cités par les lignes."""
    return {mark for line in cut_list.lines for mark in line.marks}


def has_mark_in(line: Any, marks: set[str]) -> bool:
    """La ligne cite au moins un des repères ``marks``."""
    return bool(set(line.marks) & marks)


def kinds(cut_list: Any) -> list[str]:
    """Natures des avertissements de la liste."""
    return [notice.kind.value for notice in cut_list.warnings]


def line_of(cut_list: Any, mark: str) -> Any:
    """Ligne qui porte le repère ``mark`` (la seule)."""
    [line] = [line for line in cut_list.lines if mark in line.marks]
    return line


def text(sheet: Any, address: str) -> str:
    """Contenu d'une cellule, sans l'apostrophe des textes littéraux."""
    content = str(sheet.getContents(address))
    return content[1:] if content.startswith("'") else content


def table(sheet: Any, rows: int = LAST_ROW) -> list[list[str]]:
    """Cellules A à O des lignes 1 à ``rows`` (texte vide si la cellule est vide)."""
    return [[text(sheet, f"{column}{row}") for column in COLUMNS] for row in range(1, rows + 1)]


def column(sheet: Any, letter: str = "A", rows: int = LAST_ROW) -> list[str]:
    """Contenus d'une colonne, ligne 1 à ``rows``."""
    return [text(sheet, f"{letter}{row}") for row in range(1, rows + 1)]


def row_of(sheet: Any, label: str, letter: str = "A") -> int:
    """Numéro (à partir de 1) de la première ligne dont la colonne ``letter`` vaut ``label``."""
    return column(sheet, letter).index(label) + 1


def sheets(doc: Any) -> list[Any]:
    """Feuilles de calcul du document."""
    return [obj for obj in doc.Objects if obj.TypeId == "Spreadsheet::Sheet"]
