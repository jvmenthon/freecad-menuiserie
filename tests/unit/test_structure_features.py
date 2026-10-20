# SPDX-License-Identifier: LGPL-2.1-or-later
"""Structure de ``features/`` après le découpage de ``wood_part.py`` (issue #11).

Analyse statique des sources (sans FreeCAD) : modules courts, alias de type et modes
d'édition définis une seule fois, ``translated`` dans ``features/i18n.py``.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tests.unit.aides import ROOT, imported_modules

PACKAGE = ROOT / "freecad" / "menuiserie"
FEATURES = PACKAGE / "features"
MAX_MODULE_LINES = 400
# Nom partagé → seul module (relatif au paquet) autorisé à le définir.
SHARED_NAMES = {
    "DocumentObject": "features/freecad_types.py",
    "Document": "features/freecad_types.py",
    "EDITABLE": "features/freecad_types.py",
    "READ_ONLY": "features/freecad_types.py",
    "HIDDEN": "features/freecad_types.py",
    "translated": "features/i18n.py",
}
FORBIDDEN_COPIES = {"_EDITABLE", "_READ_ONLY", "_HIDDEN"}


def package_files() -> list[Path]:
    return sorted(path for path in PACKAGE.rglob("*.py") if "__pycache__" not in path.parts)


def top_level_names(path: Path) -> set[str]:
    """Noms définis au niveau du module : affectations, fonctions et classes."""
    names: set[str] = set()
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            names.update(t.id for t in node.targets if isinstance(t, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


@pytest.mark.parametrize("path", sorted(FEATURES.glob("*.py")), ids=lambda p: p.name)
def test_modules_de_features_courts(path: Path) -> None:
    lines = len(path.read_text(encoding="utf-8").splitlines())
    assert lines <= MAX_MODULE_LINES, f"{path.name} : {lines} lignes"


@pytest.mark.parametrize("path", package_files(), ids=lambda p: str(p.relative_to(PACKAGE)))
def test_noms_partages_definis_une_seule_fois(path: Path) -> None:
    relative = path.relative_to(PACKAGE).as_posix()
    defined = top_level_names(path)
    copies = sorted(n for n, owner in SHARED_NAMES.items() if n in defined and owner != relative)
    assert copies == [], f"{relative} redéfinit {copies}"
    assert defined.isdisjoint(FORBIDDEN_COPIES), f"{relative} redéfinit un mode d'édition"


@pytest.mark.parametrize("name", sorted(SHARED_NAMES))
def test_nom_partage_defini_par_son_module(name: str) -> None:
    assert name in top_level_names(PACKAGE / SHARED_NAMES[name])


def test_wood_part_s_appuie_sur_le_schema_et_la_restauration() -> None:
    modules = imported_modules(FEATURES / "wood_part.py")
    assert "freecad.menuiserie.features.wood_part_schema" in modules
    assert "freecad.menuiserie.features.wood_part_restore" in modules
