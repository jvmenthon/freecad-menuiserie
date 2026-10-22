# SPDX-License-Identifier: LGPL-2.1-or-later
"""Aides des tests d'intégration de la liste de débit (J2c) : pièces, liens, lecture de la
feuille. Module d'aide (importé seulement avec FreeCAD)."""

from __future__ import annotations

from typing import Any

import pytest

App = pytest.importorskip("FreeCAD")
api = pytest.importorskip("freecad.menuiserie.api")

COLUMNS = "ABCDEFGHIJKLMNO"
LAST_ROW = 80
SHEET_NAME = "MenuiserieCutList"


def part(doc: Any, mark: str, size: tuple[float, float, float] = (800, 200, 22)) -> Any:
    """Pièce de chêne de repère ``mark``, recalculée."""
    obj = api.make_wood_part(*size, "chene", mark=mark, doc=doc)
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
    """Quantité par repère."""
    return {line.mark: line.quantity for line in cut_list.lines}


def kinds(cut_list: Any) -> list[str]:
    """Natures des avertissements de la liste."""
    return [notice.kind.value for notice in cut_list.warnings]


def line_of(cut_list: Any, mark: str) -> Any:
    """Ligne de repère ``mark`` (la seule)."""
    [line] = [line for line in cut_list.lines if line.mark == mark]
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
