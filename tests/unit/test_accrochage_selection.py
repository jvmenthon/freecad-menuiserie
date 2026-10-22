# SPDX-License-Identifier: LGPL-2.1-or-later
"""Accrochage à la sélection (J6d) : parties vérifiables sans FreeCAD (analyse statique).

La lecture des formes et de la sélection tourne dans ``tests/integration`` et ``tests/gui``.
Ici : la commande lit la sélection avant d'ouvrir la transaction, rien n'est modifié ni observé
dans la sélection de l'utilisateur, le formulaire porte les widgets de l'accrochage.
"""

from __future__ import annotations

import ast
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from tests.unit.aides import ROOT

PACKAGE = ROOT / "freecad" / "menuiserie"
COMMAND = PACKAGE / "gui" / "commands" / "wood_part.py"
PANEL = PACKAGE / "gui" / "task_panels" / "wood_part.py"
UI_FILE = PACKAGE / "gui" / "task_panels" / "wood_part.ui"
SELECTION_FILES = [
    PACKAGE / "gui" / "selection.py",
    COMMAND,
    PANEL,
    PACKAGE / "features" / "picked.py",
    PACKAGE / "features" / "snap_geometry.py",
    PACKAGE / "features" / "snap_targets.py",
    PACKAGE / "features" / "placement.py",
]
# Appels qui modifieraient ou observeraient la sélection de l'utilisateur (T8, ADR 0007).
FORBIDDEN_CALLS = {
    "addObserver",
    "addSelection",
    "addSelectionGate",
    "clearSelection",
    "removeObserver",
    "removeSelection",
    "removeSelectionGate",
    "setPreselection",
    "setSelectionStyle",
}


def called_names(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    ]


def activated_calls() -> list[str]:
    """Noms des fonctions appelées par ``Activated``, dans l'ordre du source."""
    tree = ast.parse(COMMAND.read_text(encoding="utf-8"))
    method = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "Activated"
    )
    calls = [node for node in ast.walk(method) if isinstance(node, ast.Call)]
    calls.sort(key=lambda node: (node.lineno, node.col_offset))
    return [
        node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", "")
        for node in calls
    ]


@pytest.mark.parametrize("path", SELECTION_FILES, ids=lambda p: p.name)
def test_la_selection_n_est_ni_modifiee_ni_observee(path: Path) -> None:
    assert FORBIDDEN_CALLS.isdisjoint(called_names(path))


def test_la_commande_lit_la_selection_avant_d_ouvrir_la_transaction() -> None:
    calls = activated_calls()
    assert calls.index("picked_elements") < calls.index("openTransaction")
    assert calls.index("read_targets") < calls.index("openTransaction")
    assert calls.index("openTransaction") < calls.index("make_wood_part")
    assert calls.index("make_wood_part") < calls.index("add_to_container")
    assert calls.index("add_to_container") < calls.index("show_panel")


def test_le_panneau_recoit_la_session_d_accrochage() -> None:
    assert "session" in COMMAND.read_text(encoding="utf-8").split("show_panel(")[-1]


def ui_widgets() -> dict[str, ET.Element]:
    root = ET.parse(UI_FILE).getroot()  # noqa: S314 (fichier du dépôt)
    return {w.get("name", ""): w for w in root.iter("widget")}


def test_le_formulaire_porte_les_widgets_de_l_accrochage() -> None:
    widgets = ui_widgets()
    assert widgets["snapLabel"].get("class") == "QLabel"
    assert widgets["snapNotices"].get("class") == "QLabel"
    check = widgets["furnitureCheck"]
    assert check.get("class") == "QCheckBox"
    values = {p.get("name"): p[0].text for p in check.findall("property")}
    assert values["checked"] == "true"  # Q3 : cochée par défaut
    assert values["visible"] == "false"  # visible seulement si un ensemble est touché


def test_les_widgets_de_l_accrochage_sont_dans_le_groupe_position() -> None:
    root = ET.parse(UI_FILE).getroot()  # noqa: S314 (fichier du dépôt)
    group = next(w for w in root.iter("widget") if w.get("name") == "positionGroup")
    names = {w.get("name") for w in group.iter("widget")}
    assert {"snapLabel", "snapNotices", "furnitureCheck", "rotateXButton"} <= names


def test_l_ordre_des_widgets_du_groupe_position() -> None:
    """Ligne « Contre », notices, boutons, puis case de l'ensemble (ordre des dispositions)."""
    root = ET.parse(UI_FILE).getroot()  # noqa: S314 (fichier du dépôt)
    group = next(w for w in root.iter("widget") if w.get("name") == "positionGroup")
    order = [w.get("name") for w in group.iter("widget")]
    assert order.index("snapLabel") < order.index("snapNotices") < order.index("rotateXButton")
    assert order.index("rotateZButton") < order.index("furnitureCheck")
