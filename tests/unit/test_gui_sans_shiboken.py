# SPDX-License-Identifier: LGPL-2.1-or-later
"""``gui/`` n'importe jamais shiboken (ADR 0023, règle FreeCAD n°5) : seule la couche de
compatibilité ``from PySide import …`` est permise, pour rester compatible avec Qt 5."""

from __future__ import annotations

import ast
from pathlib import Path

from tests.unit.aides import ROOT

GUI = ROOT / "freecad" / "menuiserie" / "gui"
FORBIDDEN = ("shiboken", "PySide2", "PySide6")


def imported_modules(path: Path) -> list[str]:
    """Modules importés par le fichier (``import x``, ``from x import …``)."""
    found: list[str] = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None and node.level == 0:
            found.append(node.module)
    return found


def test_gui_n_importe_ni_shiboken_ni_pyside_versionne() -> None:
    files = sorted(GUI.rglob("*.py"))
    assert files
    offenders = [
        f"{path.relative_to(ROOT)} : {module}"
        for path in files
        for module in imported_modules(path)
        if module.split(".")[0].startswith(FORBIDDEN)
    ]
    assert offenders == []


def test_la_detection_attrape_un_import_direct(tmp_path: Path) -> None:
    sample = tmp_path / "mauvais.py"
    sample.write_text(
        "import shiboken6\nfrom shiboken6 import isValid\nfrom PySide import QtCore\n"
    )
    assert imported_modules(sample) == ["shiboken6", "shiboken6", "PySide"]


def test_l_arbre_detruit_est_detecte_par_son_signal() -> None:
    """``shiboken6.isValid`` est remplacé par un drapeau baissé par ``destroyed``."""
    source = (GUI / "structure_sync.py").read_text(encoding="utf-8")
    assert "tree.destroyed.connect(" in source
    assert "isValid" not in source
