# SPDX-License-Identifier: LGPL-2.1-or-later
"""Indépendance du paquet ``kit`` vis-à-vis de l'atelier, de FreeCAD et de Qt (ADR 0069)."""

from __future__ import annotations

import ast
from pathlib import Path

from tests.unit.aides import ROOT, imported_modules

KIT = ROOT / "freecad" / "menuiserie" / "kit"
QT_PAGES = frozenset(  # seuls modules qui parlent à Qt
    {
        "page.py",
        "page_rows.py",
        "page_extra.py",
        "page_exchange.py",
        "page_dialogs.py",
        "page_import.py",
    }
)


def _roots(path: Path) -> set[str]:
    return {module.split(".")[0] for module in imported_modules(path)}


def test_kit_n_importe_ni_l_atelier_ni_freecad() -> None:
    """``kit/`` se copie dans un autre atelier : aucun import de Menuiserie hors de ``kit``, ni de
    FreeCAD (ADR 0069)."""
    forbidden = {"FreeCAD", "FreeCADGui", "Part", "pivy"}
    files = sorted(KIT.rglob("*.py"))
    assert files
    for path in files:
        assert not _roots(path) & forbidden, path.name
        own = [m for m in imported_modules(path) if m.startswith("freecad.menuiserie")]
        assert all(m.startswith("freecad.menuiserie.kit") for m in own), (path.name, own)


def test_seules_les_pages_importent_qt_par_la_couche_pyside() -> None:
    """Qt n'est importé que par les modules ``page*`` (``QT_PAGES``), et par ``PySide`` (couche de
    compatibilité de FreeCAD), jamais ``PySide2`` ni ``PySide6`` (CONTRIBUTING, règle 5)."""
    for path in sorted(KIT.rglob("*.py")):
        roots = _roots(path)
        assert not roots & {"PySide2", "PySide6"}, path.name
        assert ("PySide" in roots) == (path.name in QT_PAGES), path.name


def test_pages_sans_lambda() -> None:
    """Pas de lambda dans la page (Semgrep ``return-in-init`` sur les ``__init__``) : méthodes
    liées, ``partial`` ou fonctions nommées."""
    for name in sorted(QT_PAGES):
        tree = ast.parse((KIT / "config" / name).read_text(encoding="utf-8"))
        lambdas = [node.lineno for node in ast.walk(tree) if isinstance(node, ast.Lambda)]
        assert not lambdas, (name, lambdas)
