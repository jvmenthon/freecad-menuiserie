# SPDX-License-Identifier: LGPL-2.1-or-later
"""Issue #221 : une commande qui attend une sélection reste active et dit quoi sélectionner.

Contrôles statiques (sans FreeCAD) des modules de commandes ; le comportement dans l'interface
est vérifié par ``tests/gui`` (``verifier_selection_expliquee``).
"""

import ast
from pathlib import Path

import pytest

from freecad.menuiserie.gui.commands import hints

COMMANDS = Path(__file__).resolve().parents[2] / "freecad" / "menuiserie" / "gui" / "commands"
# Modules dont toutes les commandes attendent une sélection.
MODULES = ("joints.py", "furniture.py", "repeat.py", "distance.py", "shaped_part.py")
ENDING = "puis relancez la commande."


def _tree(name: str) -> ast.Module:
    return ast.parse((COMMANDS / name).read_text(encoding="utf-8"))


def _methods(tree: ast.Module, name: str) -> list[ast.FunctionDef]:
    return [
        item
        for node in tree.body
        if isinstance(node, ast.ClassDef)
        for item in node.body
        if isinstance(item, ast.FunctionDef) and item.name == name
    ]


def _hint_names() -> list[str]:
    return [
        name for name, value in vars(hints).items() if isinstance(value, str) and name.isupper()
    ]


@pytest.mark.parametrize("name", _hint_names())
def test_phrase_de_selection_complete(name: str) -> None:
    """Chaque phrase suit le libellé de la commande (« Libellé : sélectionnez… ») et finit par
    ce qu'il reste à faire."""
    text = getattr(hints, name)
    assert text.startswith("sélectionnez d'abord "), name
    assert text.endswith(ENDING), name


@pytest.mark.parametrize("module", MODULES)
def test_activated_explique_la_selection(module: str) -> None:
    """Toute méthode ``Activated`` de ces modules explique la sélection attendue."""
    activated = _methods(_tree(module), "Activated")
    assert activated, module
    for method in activated:
        called = {
            getattr(node.func, "attr", getattr(node.func, "id", ""))
            for node in ast.walk(method)
            if isinstance(node, ast.Call)
        }
        assert "explain_selection" in called, f"{module} ligne {method.lineno}"


@pytest.mark.parametrize("module", MODULES)
def test_activation_sans_lire_la_selection(module: str) -> None:
    """``IsActive`` ne dépend plus de la sélection : aucune commande ne reste grisée sans
    explication (la sélection est examinée par ``selection_ok``)."""
    tree = _tree(module)
    assert _methods(tree, "selection_ok"), module
    for method in _methods(tree, "IsActive"):
        source = ast.unparse(method)
        assert "command_ready()" in source, f"{module} ligne {method.lineno}"
        assert "selection" not in source.split('"""')[-1].lower(), f"{module} : {source}"


def test_chaque_classe_de_commande_a_sa_phrase() -> None:
    """Toute classe qui déclare sa transaction dans ces modules a une phrase de sélection, la
    sienne ou celle de sa classe de base."""
    for module in MODULES[:-1]:
        classes = {node.name: node for node in _tree(module).body if isinstance(node, ast.ClassDef)}

        def has_hint(node: ast.ClassDef, classes: dict[str, ast.ClassDef] = classes) -> bool:
            own = any(
                isinstance(item, ast.Assign)
                and any(getattr(t, "id", "") == "SELECTION_HINT" for t in item.targets)
                for item in node.body
            )
            bases = [classes[b.id] for b in node.bases if getattr(b, "id", "") in classes]
            return own or any(has_hint(base) for base in bases)

        for name, node in classes.items():
            declares = any(
                isinstance(item, ast.Assign)
                and any(getattr(t, "id", "") == "TRANSACTION" for t in item.targets)
                for item in node.body
            )
            assert not declares or has_hint(node), f"{module} : {name}"
