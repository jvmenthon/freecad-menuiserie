# SPDX-License-Identifier: LGPL-2.1-or-later
"""Interface (J1c) vérifiée sans FreeCAD : imports Qt, chaînes traduisibles, formulaire.

Critère C8 : toute chaîne visible passe par ``translate()``/``QT_TRANSLATE_NOOP`` ou par les
chaînes traduisibles du ``.ui`` ; aucun import ``PySide2``/``PySide6``. Analyse statique (AST
et XML) : les modules de ``gui/`` importent ``FreeCADGui`` et ne sont pas importables ici.
"""

from __future__ import annotations

import ast
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from tests.unit.aides import ROOT, imported_modules

PACKAGE = ROOT / "freecad" / "menuiserie"
GUI = PACKAGE / "gui"
UI_FILE = GUI / "task_panels" / "wood_part.ui"
PANEL = GUI / "task_panels" / "wood_part.py"
COMMAND = GUI / "commands" / "wood_part.py"
FORBIDDEN_QT = ("PySide2", "PySide6")
# Propriétés du .ui affichées à l'utilisateur : chaînes traduisibles, non vides.
VISIBLE_PROPERTIES = {"text", "title", "toolTip", "windowTitle", "placeholderText"}
# Propriétés techniques, jamais traduites.
UNTRANSLATED_PROPERTIES = {"unit", "styleSheet"}
# Méthodes Qt qui affichent un texte : jamais appelées avec une chaîne littérale.
TEXT_SETTERS = {
    "addAction",
    "addItem",
    "setPlaceholderText",
    "setText",
    "setTitle",
    "setToolTip",
    "setWindowTitle",
}


def python_files(*folders: Path) -> list[Path]:
    return [p for folder in folders for p in sorted(folder.rglob("*.py"))]


def ui_tree() -> ET.Element:
    return ET.parse(UI_FILE).getroot()  # noqa: S314 (fichier du dépôt)


def ui_properties() -> list[tuple[str, ET.Element]]:
    """(nom de la propriété, élément ``<string>``) de chaque propriété texte du formulaire."""
    return [
        (prop.get("name", ""), string)
        for prop in ui_tree().iter("property")
        for string in prop.findall("string")
    ]


def declared_value(path: Path, name: str) -> object:
    """Valeur littérale d'une déclaration annotée (``NAME: Final = ...``), module ou classe."""
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if not isinstance(node, ast.AnnAssign) or node.value is None:
            continue
        if isinstance(node.target, ast.Name) and node.target.id == name:
            return ast.literal_eval(node.value)
    raise AssertionError(f"{name} absent de {path.name}")


def literal_text_calls(path: Path) -> list[str]:
    """Appels d'une méthode d'affichage dont le texte (1er argument) est une chaîne littérale."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [
        f"{path.name}:{node.lineno} {node.func.attr}"
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in TEXT_SETTERS
        and any(
            isinstance(a, ast.Constant) and isinstance(a.value, str) and a.value
            for a in node.args[:1]
        )
    ]


def form_attributes(path: Path) -> set[str]:
    """Widgets lus sur le formulaire (``form.x`` ou ``self.form.x``), hors méthodes ``set…``."""
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if not isinstance(node, ast.Attribute) or node.attr.startswith("set"):
            continue
        owner = node.value
        if (isinstance(owner, ast.Name) and owner.id == "form") or (
            isinstance(owner, ast.Attribute) and owner.attr == "form"
        ):
            names.add(node.attr)
    return names


def length_field_widgets(path: Path) -> set[str]:
    """Noms de widgets déclarés par ``LengthField("…", …)``."""
    return {
        str(node.args[0].value)
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "LengthField"
        and isinstance(node.args[0], ast.Constant)
    }


# --- Imports Qt --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "path", python_files(PACKAGE, ROOT / "tests", ROOT / "tools"), ids=lambda p: p.name
)
def test_qt_par_la_couche_de_freecad(path: Path) -> None:
    modules = imported_modules(path)
    fautifs = sorted(m for m in modules if m.split(".")[0] in FORBIDDEN_QT)
    assert fautifs == [], f"{path.relative_to(ROOT)} importe {fautifs}"


def test_detection_d_un_import_pyside6(tmp_path: Path) -> None:
    path = tmp_path / "exemple.py"
    path.write_text("from PySide6 import QtWidgets\nimport PySide2.QtCore\n", encoding="utf-8")
    assert {"PySide6", "PySide2.QtCore"} <= imported_modules(path, tmp_path)


# --- Chaînes traduisibles ----------------------------------------------------------------


def test_chaines_visibles_du_formulaire_traduisibles() -> None:
    visibles = [(n, s) for n, s in ui_properties() if n in VISIBLE_PROPERTIES]
    assert visibles
    for name, string in visibles:
        assert string.get("notr") != "true", f"{name} : {string.text!r} non traduisible"
        assert (string.text or "").strip(), f"{name} vide"


def test_proprietes_techniques_non_traduites() -> None:
    for name, string in ui_properties():
        if name in UNTRANSLATED_PROPERTIES:
            assert string.get("notr") == "true", f"{name} : {string.text!r} serait traduite"


@pytest.mark.parametrize("path", python_files(GUI), ids=lambda p: p.name)
def test_aucun_texte_affiche_en_dur(path: Path) -> None:
    assert literal_text_calls(path) == []


def test_detection_d_un_texte_en_dur(tmp_path: Path) -> None:
    path = tmp_path / "exemple.py"
    path.write_text('label.setText("Bonjour")\ncombo.addItem(translated(X), "id")\n')
    assert literal_text_calls(path) == ["exemple.py:1 setText"]


def test_commande_traduite_dans_son_contexte() -> None:
    """lupdate et FreeCAD traduisent libellé et infobulle avec le nom de la commande."""
    name = declared_value(COMMAND, "COMMAND_NAME")
    contexts = {
        node.args[0].value
        for node in ast.walk(ast.parse(COMMAND.read_text(encoding="utf-8")))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "QT_TRANSLATE_NOOP"
        and isinstance(node.args[0], ast.Constant)
    }
    assert contexts == {name, "Menuiserie"}


# --- Formulaire et enregistrement --------------------------------------------------------


def test_widgets_utilises_presents_dans_le_formulaire() -> None:
    names = {widget.get("name") for widget in ui_tree().iter("widget")}
    used = form_attributes(PANEL) | length_field_widgets(PANEL)
    assert len(used) > 10
    assert used <= names, sorted(used - names)


def test_champs_de_cote_en_mm() -> None:
    spin_boxes = [w for w in ui_tree().iter("widget") if w.get("class") == "Gui::QuantitySpinBox"]
    assert {w.get("name") for w in spin_boxes} == length_field_widgets(PANEL)
    for widget in spin_boxes:
        units = [
            p.findtext("string") for p in widget.findall("property") if p.get("name") == "unit"
        ]
        assert units == ["mm"], widget.get("name")


def test_avertissement_d_epaisseur_en_texte_brut() -> None:
    """L'avertissement n'interprète pas de balisage (texte traduit affiché tel quel)."""
    label = next(w for w in ui_tree().iter("widget") if w.get("name") == "thicknessWarning")
    formats = [
        p.findtext("enum") for p in label.findall("property") if p.get("name") == "textFormat"
    ]
    assert formats == ["Qt::PlainText"]


def test_commande_enregistree_par_l_atelier() -> None:
    """Pièce de bois en tête ; les commandes d'assemblage suivent (test_commandes_assemblages)."""
    commands = declared_value(PACKAGE / "init_gui.py", "commands")
    assert isinstance(commands, tuple)
    assert commands[0] == declared_value(COMMAND, "COMMAND_NAME")


def test_atelier_charge_les_commandes_a_l_activation() -> None:
    """Chargement léger : la commande n'est importée que dans ``Initialize``."""
    tree = ast.parse((PACKAGE / "init_gui.py").read_text(encoding="utf-8"))
    top_level = {
        node.module for node in tree.body if isinstance(node, ast.ImportFrom) and node.module
    }
    assert not any(m.startswith("freecad.menuiserie.gui") for m in top_level)
    assert "freecad.menuiserie.gui.commands" in imported_modules(PACKAGE / "init_gui.py")
