# SPDX-License-Identifier: LGPL-2.1-or-later
"""Structure de ``core/`` après la reprise de J1a (critères R3 et R4)."""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from freecad.menuiserie.core import materials, part_model
from tests.unit.aides import ROOT, imported_modules, imported_names

PACKAGE = ROOT / "freecad" / "menuiserie"
MATERIALS_PACKAGE = PACKAGE / "core" / "materials"
PRIVATE_MODULES = (
    "freecad.menuiserie.core._validation",
    "freecad.menuiserie.core.materials._",
    "freecad.menuiserie.core.joints._",
    "freecad.menuiserie.core.furniture._",
)
CORE_PACKAGE = PACKAGE / "core"
# core/ est pur (critère M11 de J3) : ni FreeCAD ni Qt.
FORBIDDEN_IN_CORE = ("FreeCAD", "FreeCADGui", "Part", "PySide", "PySide2", "PySide6", "shiboken")
MAX_MODULE_LINES = 400

# API publique figée de la façade (critère R4), par sous-module d'origine : un retrait ou un
# ajout se décide en revue.
PUBLIC_API_BY_MODULE: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("_issues", ("MAX_ISSUES", "MAX_LISTED_KEYS", "LibraryFormatError", "LibraryIssue")),
    ("_issues", ("Severity",)),
    ("_merge", ("load_library", "merge_materials")),
    ("_messages", ("BUILTIN_SOURCE",)),
    ("_model", ("MAX_DENSITY", "MAX_ID_LENGTH", "MAX_NAME_LENGTH", "MAX_THICKNESSES")),
    ("_model", ("MAX_THICKNESS_MM", "MIN_DENSITY", "MAX_TEXTURE_PATH_LENGTH")),
    ("_model", ("MIN_TEXTURE_SIZE_MM", "MAX_TEXTURE_SIZE_MM", "TEXTURE_EXTENSIONS")),
    ("_model", ("Material", "MaterialKind", "MaterialLibrary", "Texture", "UnknownMaterialError")),
    ("_model", ("is_inside_folder",)),
    ("_parser", ("FORMAT_VERSION", "MAX_MATERIALS", "parse_materials")),
    ("_reader", ("MAX_FILE_BYTES", "read_materials_file")),
)
PUBLIC_API = sorted(name for _, names in PUBLIC_API_BY_MODULE for name in names)


def python_files(*folders: Path) -> list[Path]:
    return [path for folder in folders for path in sorted(folder.rglob("*.py"))]


def private_names(path: Path) -> list[str]:
    return sorted(name for name in imported_names(path) if name.startswith("_"))


def private_modules(path: Path, root: Path = ROOT) -> list[str]:
    modules = imported_modules(path, root)
    return sorted(m for m in modules if any(m.startswith(p) for p in PRIVATE_MODULES))


def may_import_private_modules(path: Path) -> bool:
    """Seuls ``core/`` et les tests unitaires (qui testent les aides) importent ces modules."""
    return path.is_relative_to(PACKAGE / "core") or path.is_relative_to(ROOT / "tests" / "unit")


# --- R3 : aides privées ------------------------------------------------------------------


@pytest.mark.parametrize("path", python_files(PACKAGE, ROOT / "tests"), ids=str)
def test_aucun_nom_prive_importe(path: Path) -> None:
    assert private_names(path) == [], f"{path.relative_to(ROOT)} importe des noms privés"


@pytest.mark.parametrize("path", python_files(PACKAGE, ROOT / "tests"), ids=str)
def test_modules_prives_reserves_a_core(path: Path) -> None:
    if may_import_private_modules(path):
        return
    assert private_modules(path) == [], f"{path.relative_to(ROOT)} importe un module privé"


def test_detection_des_imports_prives(tmp_path: Path) -> None:
    path = tmp_path / "freecad" / "menuiserie" / "features" / "exemple.py"
    path.parent.mkdir(parents=True)
    path.write_text(
        "from freecad.menuiserie.core.materials import _parser\n"
        "from ..core._validation import nfc\n"
        "from freecad.menuiserie.core.part_model import _exact_text\n",
        encoding="utf-8",
    )
    assert private_names(path) == ["_exact_text", "_parser"]
    assert private_modules(path, tmp_path) == [
        "freecad.menuiserie.core._validation",
        "freecad.menuiserie.core._validation.nfc",
        "freecad.menuiserie.core.materials._parser",
    ]
    assert not may_import_private_modules(path)


@pytest.mark.parametrize("name", ["quoted_value", "to_finite_float"])
def test_aides_plus_exposees(name: str) -> None:
    assert not hasattr(materials, name)
    assert name not in materials.__all__
    assert name not in part_model.__all__


# --- R4 : paquet core/materials/ ---------------------------------------------------------


def test_materials_est_un_paquet() -> None:
    assert not (PACKAGE / "core" / "materials.py").exists()
    assert Path(materials.__file__) == MATERIALS_PACKAGE / "__init__.py"


def test_api_publique_figee() -> None:
    assert sorted(materials.__all__) == PUBLIC_API


@pytest.mark.parametrize(
    ("module", "name"), [(module, name) for module, names in PUBLIC_API_BY_MODULE for name in names]
)
def test_nom_public_reexporte(module: str, name: str) -> None:
    origin = importlib.import_module(f"freecad.menuiserie.core.materials.{module}")
    assert getattr(materials, name) is getattr(origin, name)


@pytest.mark.parametrize("path", python_files(MATERIALS_PACKAGE), ids=lambda p: p.name)
def test_modules_du_paquet_courts(path: Path) -> None:
    lines = len(path.read_text(encoding="utf-8").splitlines())
    assert lines <= MAX_MODULE_LINES, f"{path.name} : {lines} lignes"


def test_part_model_reexporte_les_bornes() -> None:
    assert part_model.MIN_DIMENSION_MM == 0.1
    assert part_model.MAX_DIMENSION_MM == 20_000.0
    assert {"MIN_DIMENSION_MM", "MAX_DIMENSION_MM"} <= set(part_model.__all__)


# --- M11 (J3a) : core/ pur et modules courts ----------------------------------------------


@pytest.mark.parametrize("path", python_files(CORE_PACKAGE), ids=lambda p: p.name)
def test_core_n_importe_ni_freecad_ni_qt(path: Path) -> None:
    roots = {module.split(".")[0] for module in imported_modules(path)}
    assert roots.isdisjoint(FORBIDDEN_IN_CORE), f"{path.relative_to(ROOT)} : {sorted(roots)}"


@pytest.mark.parametrize("path", python_files(CORE_PACKAGE), ids=lambda p: p.name)
def test_modules_de_core_courts(path: Path) -> None:
    lines = len(path.read_text(encoding="utf-8").splitlines())
    assert lines <= MAX_MODULE_LINES, f"{path.name} : {lines} lignes"


def test_modules_prives_des_assemblages_reserves_a_core(tmp_path: Path) -> None:
    path = tmp_path / "freecad" / "menuiserie" / "features" / "exemple.py"
    path.parent.mkdir(parents=True)
    path.write_text("from freecad.menuiserie.core.joints._base import mm_round\n", encoding="utf-8")
    assert private_modules(path, tmp_path) == [
        "freecad.menuiserie.core.joints._base",
        "freecad.menuiserie.core.joints._base.mm_round",
    ]
