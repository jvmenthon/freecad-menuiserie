# SPDX-License-Identifier: LGPL-2.1-or-later
"""Cohérence des métadonnées du paquet (sans FreeCAD)."""

import ast
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from freecad import menuiserie
from tests.unit.aides import ROOT, imported_modules

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
        fautifs = sorted(m for m in imported_modules(fichier) if _est_interdit(m, interdits))
        assert not fautifs, f"{fichier.relative_to(ROOT)} importe {fautifs}"


def test_detection_des_imports_relatifs(tmp_path: Path) -> None:
    fichier = tmp_path / "freecad" / "menuiserie" / "features" / "exemple.py"
    fichier.parent.mkdir(parents=True)
    fichier.write_text("from ..gui import commandes\nfrom . import autre\n", encoding="utf-8")
    modules = imported_modules(fichier, root=tmp_path)
    assert "freecad.menuiserie.gui.commandes" in modules
    assert "freecad.menuiserie.features.autre" in modules


API = PAQUET / "api.py"
GUI_MODULES = {"FreeCADGui", "freecad.menuiserie.gui"}


def _imports_gui(node: ast.AST) -> bool:
    if isinstance(node, ast.Import):
        return any(_est_interdit(alias.name, GUI_MODULES) for alias in node.names)
    if isinstance(node, ast.ImportFrom):
        return _est_interdit(node.module or "", GUI_MODULES)
    return False


def _is_gui_up_test(node: ast.AST) -> bool:
    return isinstance(node, ast.If) and ast.unparse(node.test) == "App.GuiUp"


def test_api_importe_gui_seulement_si_l_interface_est_chargee() -> None:
    tree = ast.parse(API.read_text(encoding="utf-8"))
    guarded = {
        id(child)
        for node in ast.walk(tree)
        if _is_gui_up_test(node)
        for child in ast.walk(node)
        if _imports_gui(child)
    }
    gui_imports = [node for node in ast.walk(tree) if _imports_gui(node)]
    assert gui_imports, "api.py doit attacher le ViewProvider quand l'interface est chargée"
    assert all(id(node) in guarded for node in gui_imports)


@pytest.mark.parametrize(
    "fichier",
    [PAQUET / "__init__.py", *sorted((PAQUET / "features").rglob("*.py"))],
    ids=lambda chemin: chemin.name,
)
def test_api_importe_par_personne_dans_les_couches_basses(fichier: Path) -> None:
    assert "freecad.menuiserie.api" not in imported_modules(fichier)
