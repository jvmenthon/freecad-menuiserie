# SPDX-License-Identifier: LGPL-2.1-or-later
"""Issue #221 : l'infobulle d'une commande qui attend une sélection dit son prérequis.

Contrôles statiques (sans FreeCAD) des modules de commandes ; l'infobulle affichée est vérifiée
par ``tests/gui`` (``verifier_commandes_d_assemblage_enregistrees``).
"""

import ast
from pathlib import Path

import pytest

from freecad.menuiserie.gui.commands import hints

COMMANDS = Path(__file__).resolve().parents[2] / "freecad" / "menuiserie" / "gui" / "commands"
# Modules dont toutes les commandes attendent une sélection, sur la base TransactionCommand.
MODULES = ("joints.py", "furniture.py", "repeat.py", "distance.py")


def _classes(module: str) -> dict[str, ast.ClassDef]:
    tree = ast.parse((COMMANDS / module).read_text(encoding="utf-8"))
    return {node.name: node for node in tree.body if isinstance(node, ast.ClassDef)}


def _assigns(node: ast.ClassDef, name: str) -> bool:
    return any(
        isinstance(item, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == name for target in item.targets)
        for item in node.body
    )


def _has_prerequisite(node: ast.ClassDef, classes: dict[str, ast.ClassDef]) -> bool:
    """Vrai si la classe, ou une de ses classes de base du module, fixe ``PREREQUISITE``."""
    names = [base.id for base in node.bases if isinstance(base, ast.Name)]
    bases = [classes[name] for name in names if name in classes]
    return _assigns(node, "PREREQUISITE") or any(_has_prerequisite(b, classes) for b in bases)


def _hint_names() -> list[str]:
    return [
        name for name, value in vars(hints).items() if isinstance(value, str) and name.isupper()
    ]


@pytest.mark.parametrize("name", _hint_names())
def test_prerequis_est_un_etat_pas_un_ordre(name: str) -> None:
    """Chaque phrase suit « Prérequis : » : elle décrit la sélection attendue (« … sélectionné »),
    sans ordre ni mention d'un bouton grisé, et vaut que la commande soit active ou non."""
    text = getattr(hints, name)
    assert "sélectionné" in text, name
    assert text.endswith("."), name
    assert text[0].islower(), name
    for forbidden in ("sélectionnez", "relancez", "indisponible", "grisé"):
        assert forbidden not in text.lower(), f"{name} : {forbidden}"


@pytest.mark.parametrize("module", MODULES)
def test_chaque_commande_a_son_prerequis(module: str) -> None:
    """Toute classe qui déclare sa transaction dans ces modules a un prérequis, le sien ou celui
    de sa classe de base."""
    classes = _classes(module)
    commands = {name: node for name, node in classes.items() if _assigns(node, "TRANSACTION")}
    assert commands, module
    for name, node in commands.items():
        assert _has_prerequisite(node, classes), f"{module} : {name}"


def test_infobulle_composee_par_le_socle() -> None:
    """Le socle et « Convertir en pièce en bois » (hors socle) composent l'infobulle par
    ``tool_tip`` : une seule mise en forme de la ligne « Prérequis : … »."""
    for module in ("base.py", "shaped_part.py"):
        source = (COMMANDS / module).read_text(encoding="utf-8")
        assert '"ToolTip": tool_tip(' in source, module
    assert "Prérequis : {prerequisite}" in (COMMANDS / "base.py").read_text(encoding="utf-8")
