# SPDX-License-Identifier: LGPL-2.1-or-later
"""Cohérence des métadonnées du paquet (sans FreeCAD)."""

import ast
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from freecad import menuiserie

ROOT = Path(__file__).resolve().parents[2]
NS = {"p": "https://wiki.freecad.org/Package_Metadata"}


def _package_xml() -> ET.Element:
    return ET.parse(ROOT / "package.xml").getroot()  # noqa: S314 (fichier du dépôt)


def test_version_identique_partout() -> None:
    xml_version = _package_xml().findtext("p:version", namespaces=NS)
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    trouve = re.search(r'^version = "([^"]+)"$', pyproject, re.MULTILINE)
    assert trouve is not None
    toml_version = trouve.group(1)
    assert menuiserie.__version__ == xml_version == toml_version


def test_classe_du_workbench_declaree() -> None:
    classname = _package_xml().findtext("p:content/p:workbench/p:classname", namespaces=NS)
    source = (ROOT / "freecad" / "menuiserie" / "init_gui.py").read_text(encoding="utf-8")
    assert f"class {classname}(" in source


def test_icone_presente() -> None:
    icon = _package_xml().findtext("p:icon", namespaces=NS)
    assert icon is not None
    assert (ROOT / icon).is_file()
    assert Path(menuiserie.icon_path("menuiserie.svg")).is_file()


def _modules_importes(fichier: Path) -> set[str]:
    arbre = ast.parse(fichier.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Import):
            modules.update(alias.name.split(".")[0] for alias in noeud.names)
        elif isinstance(noeud, ast.ImportFrom) and noeud.module:
            modules.add(noeud.module.split(".")[0])
    return modules


@pytest.mark.parametrize(
    ("paquet", "interdits"),
    [
        ("core", {"FreeCAD", "FreeCADGui", "Part", "PySide"}),
        ("features", {"FreeCADGui", "PySide"}),
    ],
)
def test_separation_app_gui(paquet: str, interdits: set[str]) -> None:
    for fichier in (ROOT / "freecad" / "menuiserie" / paquet).rglob("*.py"):
        fautifs = _modules_importes(fichier) & interdits
        assert not fautifs, f"{fichier.relative_to(ROOT)} importe {sorted(fautifs)}"
