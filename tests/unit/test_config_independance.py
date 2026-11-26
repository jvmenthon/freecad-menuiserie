# SPDX-License-Identifier: LGPL-2.1-or-later
"""Indépendance du paquet ``kit`` vis-à-vis de l'atelier, de FreeCAD et de Qt (ADR 0069)."""

from __future__ import annotations

from pathlib import Path

from tests.unit.aides import ROOT, imported_modules

KIT = ROOT / "freecad" / "menuiserie" / "kit"
QT_PAGES = frozenset({"page.py", "page_rows.py"})  # seuls modules qui parlent à Qt


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


def test_seule_la_page_importe_qt_par_la_couche_pyside() -> None:
    """Qt n'est importé que par ``page.py`` et ``page_rows.py``, et par ``PySide`` (couche de
    compatibilité de FreeCAD), jamais ``PySide2`` ni ``PySide6`` (CONTRIBUTING, règle 5)."""
    for path in sorted(KIT.rglob("*.py")):
        roots = _roots(path)
        assert not roots & {"PySide2", "PySide6"}, path.name
        assert ("PySide" in roots) == (path.name in QT_PAGES), path.name
