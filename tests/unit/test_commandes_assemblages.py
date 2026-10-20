# SPDX-License-Identifier: LGPL-2.1-or-later
"""Commandes et ViewProviders des assemblages (J3d) vérifiés sans FreeCAD, par analyse statique.

Critère C1 : quatre commandes ``Menuiserie_<type>`` enregistrées par l'atelier (barre d'outils
et menu), chacune avec son icône existante, des textes traduisibles dans le contexte de la
commande et une fabrique de l'api ; C6 : une icône par type d'assemblage ; E7 : textes
traduisibles. Les modules de ``gui/`` importent ``FreeCADGui`` et ne sont pas importables ici.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from freecad.menuiserie import ICONS_DIR
from freecad.menuiserie.core.joints import JointKind
from tests.unit.aides import ROOT

PACKAGE = ROOT / "freecad" / "menuiserie"
COMMANDS = PACKAGE / "gui" / "commands" / "joints.py"
VIEW_PROVIDERS = PACKAGE / "gui" / "view_providers"
# Commande : (libellé, fabrique de l'api). Les noms suivent ``Menuiserie_<JointKind.value>``.
EXPECTED = {
    "Menuiserie_MortiseTenon": ("Tenon-mortaise", "make_mortise_tenon"),
    "Menuiserie_TongueGroove": ("Rainure-languette", "make_tongue_groove"),
    "Menuiserie_Rabbet": ("Feuillure", "make_rabbet"),
    "Menuiserie_Dowels": ("Tourillons", "make_dowels"),
}


def tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def class_attributes(path: Path) -> dict[str, dict[str, ast.expr]]:
    """Attributs de classe affectés (``NOM = valeur``) de chaque classe du module."""
    return {
        node.name: {
            target.id: item.value
            for item in node.body
            if isinstance(item, ast.Assign)
            for target in item.targets
            if isinstance(target, ast.Name)
        }
        for node in tree(path).body
        if isinstance(node, ast.ClassDef)
    }


def module_constants(path: Path) -> dict[str, object]:
    """Constantes littérales annotées du module (``NOM: Final = "…"``)."""
    return {
        node.target.id: ast.literal_eval(node.value)
        for node in tree(path).body
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and isinstance(node.value, ast.Constant)
    }


def joint_commands() -> dict[str, dict[str, ast.expr]]:
    """Attributs des sous-classes de ``JointCommand``, par nom de commande (``NAME``)."""
    constants = module_constants(COMMANDS)
    commands = {}
    for attributes in class_attributes(COMMANDS).values():
        name = attributes.get("NAME")
        if isinstance(name, ast.Name):
            commands[str(constants[name.id])] = attributes
    return commands


def noop(value: ast.expr) -> tuple[str, str]:
    """(contexte, texte) d'un appel ``QT_TRANSLATE_NOOP`` littéral."""
    assert isinstance(value, ast.Call)
    assert isinstance(value.func, ast.Name)
    assert value.func.id == "QT_TRANSLATE_NOOP"
    context, text = (ast.literal_eval(arg) for arg in value.args)
    return context, text


def init_gui_commands() -> tuple[str, ...]:
    for node in ast.walk(tree(PACKAGE / "init_gui.py")):
        if isinstance(node, ast.AnnAssign) and getattr(node.target, "id", "") == "commands":
            assert node.value is not None
            value: tuple[str, ...] = ast.literal_eval(node.value)
            return value
    raise AssertionError("commands absent de init_gui.py")


def api_functions() -> set[str]:
    return {
        node.name for node in tree(PACKAGE / "api.py").body if isinstance(node, ast.FunctionDef)
    }


def test_une_commande_par_type() -> None:
    assert set(joint_commands()) == set(EXPECTED)


def test_noms_des_commandes_selon_les_types() -> None:
    """Types de J3b (et J3c une fois fusionné) : ``Menuiserie_<JointKind.value>``."""
    assert {f"Menuiserie_{kind.value}" for kind in JointKind} <= set(EXPECTED)


def test_commandes_dans_la_barre_et_le_menu() -> None:
    assert init_gui_commands() == ("Menuiserie_WoodPart", *EXPECTED)


@pytest.mark.parametrize("name", list(EXPECTED))
def test_icone_existante(name: str) -> None:
    """Icône de la commande et de l'assemblage dans l'arbre (``Menuiserie_<type>.svg``)."""
    assert (ICONS_DIR / f"{name}.svg").is_file()


@pytest.mark.parametrize("name", list(EXPECTED))
def test_textes_traduisibles_dans_le_contexte_de_la_commande(name: str) -> None:
    attributes = joint_commands()[name]
    label, _factory = EXPECTED[name]
    assert noop(attributes["MENU_TEXT"]) == (name, label)
    context, tool_tip = noop(attributes["TOOL_TIP"])
    assert context == name
    assert tool_tip.strip()
    assert noop(attributes["TRANSACTION"])[0] == "Menuiserie"


def test_transaction_du_tenon_mortaise() -> None:
    """C2 : entrée d'annulation « Créer un assemblage tenon-mortaise »."""
    transaction = joint_commands()["Menuiserie_MortiseTenon"]["TRANSACTION"]
    assert noop(transaction)[1] == "Créer un assemblage tenon-mortaise"


@pytest.mark.parametrize("name", list(EXPECTED))
def test_fabrique_nommee(name: str) -> None:
    assert ast.literal_eval(joint_commands()[name]["FACTORY"]) == EXPECTED[name][1]


def test_fabrique_du_tenon_mortaise_dans_l_api() -> None:
    """Les autres fabriques arrivent en J3c ; leur commande reste inactive d'ici là."""
    assert "make_mortise_tenon" in api_functions()


@pytest.mark.parametrize(
    ("module", "classe"),
    [("machined_part", "ViewProviderMachinedPart"), ("joint", "ViewProviderJoint")],
)
def test_view_providers_aux_chemins_figes(module: str, classe: str) -> None:
    """Chemins enregistrés dans les documents (ADR 0003)."""
    assert classe in class_attributes(VIEW_PROVIDERS / f"{module}.py")


def test_view_providers_poses_par_l_api() -> None:
    """L'api pose les ViewProviders des assemblages et des pièces usinées, sous ``GuiUp``."""
    imported = {
        node.module
        for node in ast.walk(tree(PACKAGE / "api.py"))
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert {
        "freecad.menuiserie.gui.view_providers.joint",
        "freecad.menuiserie.gui.view_providers.machined_part",
    } <= imported
