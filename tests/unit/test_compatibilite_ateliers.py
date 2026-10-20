# SPDX-License-Identifier: LGPL-2.1-or-later
"""Inventaire de compatibilité avec les autres ateliers (J3b, critère O14, volet U ; ADR 0007).

Analyse statique des sources : commandes ``Menuiserie_…``, types de proxy ``Menuiserie::…``,
aucun module hors de ``freecad.menuiserie``, aucune dépendance Python d'exécution.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tests.unit.aides import ROOT

PACKAGE = ROOT / "freecad" / "menuiserie"
SOURCES = sorted(path for path in PACKAGE.rglob("*.py") if "__pycache__" not in path.parts)


def text_assignment(node: ast.AST) -> tuple[str, str] | None:
    """(nom, texte) d'une affectation ``NOM = "…"`` ou ``NOM: T = "…"`` ; ``None`` sinon."""
    target: ast.expr | None = node.target if isinstance(node, ast.AnnAssign) else None
    if isinstance(node, ast.Assign) and len(node.targets) == 1:
        target = node.targets[0]
    value = getattr(node, "value", None)
    is_text = isinstance(value, ast.Constant) and isinstance(value.value, str)
    if isinstance(target, ast.Name) and is_text:
        return target.id, str(getattr(value, "value", ""))
    return None


def string_constants(tree: ast.Module) -> dict[str, str]:
    """Constantes de module de type texte."""
    pairs = (text_assignment(node) for node in tree.body)
    return dict(pair for pair in pairs if pair is not None)


def command_names(path: Path) -> list[str]:
    """Premiers arguments des appels ``addCommand`` (littéraux ou constantes du module)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    constants = string_constants(tree)
    names = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        if node.func.attr != "addCommand" or not node.args:
            continue
        first = node.args[0]
        if isinstance(first, ast.Constant):
            names.append(str(first.value))
        else:
            names.append(constants.get(getattr(first, "id", ""), "<non résolu>"))
    return names


def proxy_types(path: Path) -> list[str]:
    """Valeurs des attributs de classe ``TYPE`` affectés à un texte."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    classes = [node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
    pairs = [text_assignment(item) for cls in classes for item in cls.body]
    return [pair[1] for pair in pairs if pair is not None and pair[0] == "TYPE"]


def test_commandes_prefixees() -> None:
    names = [name for path in SOURCES for name in command_names(path)]
    assert names, "aucune commande trouvée"
    assert [name for name in names if not name.startswith("Menuiserie_")] == []


def test_types_de_proxy_prefixes() -> None:
    types = [value for path in SOURCES for value in proxy_types(path)]
    assert {"Menuiserie::WoodPart", "Menuiserie::MachinedPart", "Menuiserie::MortiseTenon"} <= set(
        types
    )
    assert [value for value in types if not value.startswith("Menuiserie::")] == []


def test_aucun_module_hors_de_l_espace_de_noms() -> None:
    namespace = ROOT / "freecad"
    entries = {path.name for path in namespace.iterdir() if path.name != "__pycache__"}
    assert entries == {"menuiserie"}


def project_section(text: str) -> list[str]:
    """Lignes de la table ``[project]`` de ``pyproject.toml``."""
    lines = text.splitlines()
    start = lines.index("[project]") + 1
    end = next((i for i in range(start, len(lines)) if lines[i].startswith("[")), len(lines))
    return lines[start:end]


@pytest.mark.parametrize("key", ["dependencies"])
def test_aucune_dependance_d_execution(key: str) -> None:
    section = project_section((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert [line for line in section if line.replace(" ", "").startswith(f"{key}=")] == []
