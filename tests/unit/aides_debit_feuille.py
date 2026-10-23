# SPDX-License-Identifier: LGPL-2.1-or-later
"""Feuille et objet ``CutList`` simulés pour les tests unitaires de la liste de débit (J2c, J2f).

Le vrai document (graphe de dépendances, annulation, réouverture) est vérifié par
``tests/integration/test_liste_de_debit*.py``.
"""

from __future__ import annotations

import re
from typing import Any

from tests.unit.aides_debit_document import Obj

ADDRESS = re.compile(r"([A-Z]+)([0-9]+)$")
MODE_NAMES = {0: [], 1: ["ReadOnly"], 2: ["Hidden"]}  # comme ``getEditorMode``
EMPTY_VALUES: dict[str, Any] = {
    "App::PropertyLink": None,
    "App::PropertyLinkList": [],
    "App::PropertyLinkListHidden": [],
    "App::PropertyInteger": 0,
}


class FakeSheet(Obj):
    """Feuille simulée : contenus, styles, alignements et largeurs enregistrés."""

    def __init__(self, name: str = "MenuiserieCutList") -> None:
        super().__init__(name, "Spreadsheet::Sheet")
        self.cells: dict[str, str] = {}
        self.styles: dict[str, str] = {}
        self.alignments: dict[str, str] = {}
        self.widths: dict[str, int] = {}
        self.modes: dict[str, int] = {}
        self.recomputed = 0

    def addProperty(self, kind: str, name: str, group: str, doc: str) -> None:
        assert kind == "App::PropertyBool"
        assert (group, bool(doc)) == ("Menuiserie", True)
        self.props[name] = False

    def __setattr__(self, name: str, value: Any) -> None:
        if name in ("MenuiserieCutList", "Label") and "props" in self.__dict__:
            self.props[name] = value
        else:
            super().__setattr__(name, value)

    def setEditorMode(self, name: str, mode: int) -> None:
        self.modes[name] = mode

    def set(self, address: str, content: str) -> None:
        self.cells[address] = content

    def clear(self, address: str) -> None:
        self.cells.pop(address, None)
        self.styles.pop(address, None)
        self.alignments.pop(address, None)

    def getUsedCells(self) -> list[str]:
        return sorted(self.cells)

    def setStyle(self, address: str, style: str) -> None:
        self.styles[address] = style

    def setAlignment(self, address: str, alignment: str) -> None:
        self.alignments[address] = alignment

    def setColumnWidth(self, column: str, width: int) -> None:
        self.widths[column] = width

    def recompute(self) -> None:
        self.recomputed += 1

    def purgeTouched(self) -> None:
        """Marque « Touched » effacée (sans effet sur le double)."""


class FakeFeature(Obj):
    """``App::FeaturePython`` simulé : propriétés ajoutées par ``addProperty``, modes d'édition."""

    def __init__(self, name: str) -> None:
        super().__init__(name, "App::FeaturePython")
        self.modes: dict[str, int] = {}
        self.types: dict[str, str] = {}
        self.purged = 0

    def addProperty(self, kind: str, name: str, group: str, doc: str) -> None:
        assert group and doc
        self.types[name] = kind
        empty = EMPTY_VALUES[kind]
        self.props[name] = [] if isinstance(empty, list) else empty

    def __setattr__(self, name: str, value: Any) -> None:
        if "props" in self.__dict__ and name in self.props:
            self.props[name] = value
        else:
            super().__setattr__(name, value)

    def getEditorMode(self, name: str) -> list[str]:
        return MODE_NAMES[self.modes.get(name, 0)]

    def setEditorMode(self, name: str, mode: int) -> None:
        self.modes[name] = mode

    def purgeTouched(self) -> None:
        self.purged += 1


class SheetDoc:
    """Document simulé qui crée feuille et objet ``CutList`` et note les transactions."""

    def __init__(self, *objects: Obj) -> None:
        self.Objects = list(objects)
        for obj in objects:
            obj.Document = self
        self.log: list[str] = []
        self.Transacting = False

    def addObject(self, type_id: str, name: str) -> Any:
        assert type_id in ("Spreadsheet::Sheet", "App::FeaturePython")
        self.log.append(f"add {name}")
        created = FakeSheet(name) if type_id == "Spreadsheet::Sheet" else FakeFeature(name)
        created.Document = self
        self.Objects.append(created)
        return created

    def openTransaction(self, name: str) -> None:
        self.log.append(f"open {name}")

    def commitTransaction(self) -> None:
        self.log.append("commit")

    def abortTransaction(self) -> None:
        self.log.append("abort")

    def getObject(self, name: str) -> Any:
        return next((obj for obj in self.Objects if obj.Name == name), None)

    def recompute(self) -> int:
        self.log.append("recompute")
        return 0
