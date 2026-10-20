# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fixtures des tests d'intégration : bibliothèque isolée, documents, vue rapport.

Aucun test ne dépend du fichier de matériaux de l'utilisateur de la machine : le paramètre
``UserLibraryPath`` pointe vers un fichier temporaire, absent sauf si un test l'installe.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

PARAM_PATH = "User parameter:BaseApp/Preferences/Mod/Menuiserie"
PARAM_NAME = "UserLibraryPath"


def _freecad() -> Any:
    return pytest.importorskip("FreeCAD")


def _library_module() -> ModuleType:
    module: ModuleType = pytest.importorskip("freecad.menuiserie.features.library")
    return module


@dataclass
class BibliothequeTemporaire:
    """Fichier utilisateur de matériaux écrit par le test dans un dossier temporaire."""

    path: Path

    def installer(self, *materials: dict[str, object]) -> Path:
        """Écrit les matériaux (format 1) et relit la bibliothèque."""
        content = {"format": 1, "materials": list(materials)}
        self.path.write_text(json.dumps(content, ensure_ascii=False), encoding="utf-8")
        _library_module().reload_library()
        return self.path

    def retirer(self) -> None:
        """Supprime le fichier (bibliothèque intégrée seule) et relit la bibliothèque."""
        self.path.unlink(missing_ok=True)
        _library_module().reload_library()


@pytest.fixture(autouse=True)
def bibliotheque_temporaire(tmp_path: Path) -> Iterator[BibliothequeTemporaire]:
    """Pointe ``UserLibraryPath`` vers un fichier temporaire, puis restaure tout à la fin."""
    parameters = _freecad().ParamGet(PARAM_PATH)
    previous = parameters.GetString(PARAM_NAME, "")
    folder = tmp_path / "bibliotheque"
    folder.mkdir()
    temporary = BibliothequeTemporaire(folder / "materiaux.json")
    parameters.SetString(PARAM_NAME, str(temporary.path))
    _library_module().reload_library()
    yield temporary
    if previous:
        parameters.SetString(PARAM_NAME, previous)
    else:
        parameters.RemString(PARAM_NAME)
    _library_module().reload_library()


@dataclass
class VueRapport:
    """Messages écrits dans la vue rapport pendant le test, par gravité."""

    messages: list[tuple[str, str]] = field(default_factory=list)

    def de_niveau(self, level: str) -> list[str]:
        return [text for kind, text in self.messages if kind == level]


@pytest.fixture
def vue_rapport(monkeypatch: pytest.MonkeyPatch) -> VueRapport:
    """Capture ``PrintError``, ``PrintWarning`` et ``PrintLog`` de la console FreeCAD."""
    console = _freecad().Console
    report = VueRapport()
    for level in ("Error", "Warning", "Log"):

        def write(text: str, level: str = level) -> None:
            report.messages.append((level, text))

        monkeypatch.setattr(console, f"Print{level}", write)
    return report


@pytest.fixture
def document() -> Iterator[Any]:
    """Document neuf, fermé à la fin du test (ainsi que ses réouvertures)."""
    app = _freecad()
    doc = app.newDocument("TestPieceDeBois")
    name = doc.Name
    yield doc
    for opened in list(app.listDocuments()):
        if opened == name or opened.startswith(name):
            app.closeDocument(opened)


@pytest.fixture
def rouvrir(tmp_path: Path) -> Callable[[Any], Any]:
    """Fonction qui enregistre un document, le ferme et le rouvre."""
    app = _freecad()

    def reopen(doc: Any) -> Any:
        path = tmp_path / f"{doc.Name}.FCStd"
        doc.saveAs(str(path))
        app.closeDocument(doc.Name)
        return app.openDocument(str(path))

    return reopen
