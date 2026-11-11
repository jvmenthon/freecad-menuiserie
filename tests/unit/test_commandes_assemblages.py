# SPDX-License-Identifier: LGPL-2.1-or-later
"""Commandes et ViewProviders des assemblages (J3d) vérifiés sans FreeCAD, par analyse statique.

Critère C1 : une commande par type, ``Menuiserie_<type>`` enregistrées par l'atelier (barre d'outils
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
from tests.commandes_assemblages import COMMANDES_ASSEMBLAGE
from tests.commandes_ensembles import COMMANDES_ENSEMBLE
from tests.unit.aides import ROOT

PACKAGE = ROOT / "freecad" / "menuiserie"
COMMANDS = PACKAGE / "gui" / "commands" / "joints.py"
VIEW_PROVIDERS = PACKAGE / "gui" / "view_providers"


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
    return commands_of(COMMANDS)


def commands_of(path: Path) -> dict[str, dict[str, ast.expr]]:
    """Attributs des classes de commande du module ``path``, par nom de commande (``NAME``,
    constante du module)."""
    constants = module_constants(path)
    commands = {}
    for attributes in class_attributes(path).values():
        name = attributes.get("NAME")
        if isinstance(name, ast.Name):
            commands[str(constants[name.id])] = attributes
    return commands


def _called_name(func: ast.expr) -> str:
    """Nom appelé : attribut (``Gui.addCommand``) ou fonction (``add_command``)."""
    if isinstance(func, ast.Attribute):
        return func.attr
    return func.id if isinstance(func, ast.Name) else ""


def registered_commands(path: Path) -> list[str]:
    """Noms des commandes passées à ``Gui.addCommand(NOM, …)`` ou à ``add_command(NOM, …)``
    (socle des commandes, issue #221) dans le module ``path`` (``NOM`` constante du module)."""
    constants = module_constants(path)
    return sorted(
        str(constants[node.args[0].id])
        for node in ast.walk(tree(path))
        if isinstance(node, ast.Call)
        and _called_name(node.func) in {"addCommand", "add_command"}
        and isinstance(node.args[0], ast.Name)
    )


def noop(value: ast.expr) -> tuple[str, str]:
    """(contexte, texte) d'un appel ``QT_TRANSLATE_NOOP`` littéral."""
    assert isinstance(value, ast.Call)
    assert isinstance(value.func, ast.Name)
    assert value.func.id == "QT_TRANSLATE_NOOP"
    context, text = (ast.literal_eval(arg) for arg in value.args)
    return context, text


def init_gui_themes() -> dict[str, tuple[str, ...]]:
    """Commandes de l'atelier par thème (``themes`` de ``init_gui.py``), dans l'ordre."""
    for node in ast.walk(tree(PACKAGE / "init_gui.py")):
        if isinstance(node, ast.AnnAssign) and getattr(node.target, "id", "") == "themes":
            assert isinstance(node.value, ast.Tuple)
            themes: dict[str, tuple[str, ...]] = {}
            for entry in node.value.elts:
                assert isinstance(entry, ast.Tuple)
                title, names = entry.elts
                assert isinstance(title, ast.Call)
                themes[ast.literal_eval(title.args[1])] = ast.literal_eval(names)
            return themes
    raise AssertionError("themes absent de init_gui.py")


def init_gui_commands() -> tuple[str, ...]:
    return tuple(name for names in init_gui_themes().values() for name in names)


def api_functions() -> set[str]:
    return {
        node.name
        for node in tree(PACKAGE / "_api" / "joints.py").body
        if isinstance(node, ast.FunctionDef)
    }


def test_une_commande_par_type() -> None:
    assert set(joint_commands()) == set(COMMANDES_ASSEMBLAGE)


def test_noms_des_commandes_selon_les_types() -> None:
    """Types de J3b (et J3c une fois fusionné) : ``Menuiserie_<JointKind.value>``."""
    assert {f"Menuiserie_{kind.value}" for kind in JointKind} <= set(COMMANDES_ASSEMBLAGE)


def test_commandes_dans_la_barre_et_le_menu() -> None:
    """Seule vérification de l'ensemble des commandes de l'atelier (revue J3d, S6) : chacune est
    dans un thème et un seul ; assemblages et quincaillerie sont séparés."""
    names = init_gui_commands()
    assert len(names) == len(set(names))
    assert {"Menuiserie_WoodPart", *COMMANDES_ASSEMBLAGE, *COMMANDES_ENSEMBLE} <= set(names)
    themes = init_gui_themes()
    assert set(COMMANDES_ASSEMBLAGE) <= set(themes["Assemblages"] + themes["Quincaillerie"])
    assert set(COMMANDES_ENSEMBLE) <= set(themes["Ensembles"])
    assert "Menuiserie_WoodPart" in themes["Pièces"]


@pytest.mark.parametrize("name", list(COMMANDES_ASSEMBLAGE))
def test_icone_existante(name: str) -> None:
    """Icône de la commande et de l'assemblage dans l'arbre (``Menuiserie_<type>.svg``)."""
    assert (ICONS_DIR / f"{name}.svg").is_file()


@pytest.mark.parametrize("name", list(COMMANDES_ASSEMBLAGE))
def test_textes_traduisibles_dans_le_contexte_de_la_commande(name: str) -> None:
    attributes = joint_commands()[name]
    label, _factory = COMMANDES_ASSEMBLAGE[name]
    assert noop(attributes["MENU_TEXT"]) == (name, label)
    context, tool_tip = noop(attributes["TOOL_TIP"])
    assert context == name
    assert tool_tip.strip()
    assert noop(attributes["TRANSACTION"])[0] == "Menuiserie"


@pytest.mark.parametrize(
    ("name", "text"),
    [
        ("Menuiserie_MortiseTenon", "Créer un assemblage tenon-mortaise"),
        ("Menuiserie_HalfLap", "Créer un assemblage à mi-bois"),
        ("Menuiserie_Dovetail", "Créer un assemblage à queue d'aronde"),
        ("Menuiserie_Miter", "Créer un assemblage d'onglet"),
    ],
)
def test_transaction_de_la_commande(name: str, text: str) -> None:
    """C2 de J3, B4, D6 et A5 de J4 : entrée d'annulation « Créer un assemblage … »."""
    assert noop(joint_commands()[name]["TRANSACTION"])[1] == text


@pytest.mark.parametrize("name", list(COMMANDES_ASSEMBLAGE))
def test_fabrique_de_l_api_referencee(name: str) -> None:
    """``FACTORY = api.make_…`` : référence directe, vérifiée à l'import (revue J3d, S2)."""
    factory = joint_commands()[name]["FACTORY"]
    assert isinstance(factory, ast.Attribute)
    assert isinstance(factory.value, ast.Name)
    assert (factory.value.id, factory.attr) == ("api", COMMANDES_ASSEMBLAGE[name][1])
    assert factory.attr in api_functions()


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
        for node in ast.walk(tree(PACKAGE / "_api" / "joints.py"))
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert {
        "freecad.menuiserie.gui.view_providers.joint",
        "freecad.menuiserie.gui.view_providers.machined_part",
    } <= imported
