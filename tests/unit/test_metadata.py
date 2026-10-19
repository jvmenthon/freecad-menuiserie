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


PAQUET = ROOT / "freecad" / "menuiserie"
QT_ET_GUI = {"FreeCADGui", "PySide", "PySide2", "PySide6", "pivy"}


def _modules_importes(fichier: Path, racine: Path = ROOT) -> set[str]:
    """Modules importés par un fichier, imports relatifs résolus en chemin absolu."""
    paquet_du_fichier = ".".join(fichier.parent.relative_to(racine).parts)
    modules: set[str] = set()
    for noeud in ast.walk(ast.parse(fichier.read_text(encoding="utf-8"))):
        if isinstance(noeud, ast.Import):
            modules.update(alias.name for alias in noeud.names)
        elif isinstance(noeud, ast.ImportFrom):
            if noeud.level:
                base = paquet_du_fichier.rsplit(".", noeud.level - 1)[0]
                module = f"{base}.{noeud.module}" if noeud.module else base
            else:
                module = noeud.module or ""
            modules.add(module)
            modules.update(f"{module}.{alias.name}" for alias in noeud.names)
    return modules


def _est_interdit(module: str, interdits: set[str]) -> bool:
    return any(module == i or module.startswith(f"{i}.") for i in interdits)


@pytest.mark.parametrize(
    ("couche", "interdits"),
    [
        (
            "core",
            {
                "FreeCAD",
                "Part",
                *QT_ET_GUI,
                "freecad.menuiserie.features",
                "freecad.menuiserie.gui",
            },
        ),
        ("features", {*QT_ET_GUI, "freecad.menuiserie.gui"}),
    ],
)
def test_separation_app_gui(couche: str, interdits: set[str]) -> None:
    fichiers = list((PAQUET / couche).rglob("*.py"))
    assert fichiers, f"aucun fichier Python trouvé dans {couche}/"
    for fichier in fichiers:
        fautifs = sorted(m for m in _modules_importes(fichier) if _est_interdit(m, interdits))
        assert not fautifs, f"{fichier.relative_to(ROOT)} importe {fautifs}"


def test_detection_des_imports_relatifs(tmp_path: Path) -> None:
    fichier = tmp_path / "freecad" / "menuiserie" / "features" / "exemple.py"
    fichier.parent.mkdir(parents=True)
    fichier.write_text("from ..gui import commandes\nfrom . import autre\n", encoding="utf-8")
    modules = _modules_importes(fichier, racine=tmp_path)
    assert "freecad.menuiserie.gui.commandes" in modules
    assert "freecad.menuiserie.features.autre" in modules
