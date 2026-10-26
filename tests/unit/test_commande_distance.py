# SPDX-License-Identifier: LGPL-2.1-or-later
"""Commande « Définir une distance » (DI-b, critère E1) vérifiée sans FreeCAD, par analyse
statique : les modules de ``gui/`` importent ``FreeCADGui``."""

from __future__ import annotations

import ast

from freecad.menuiserie import ICONS_DIR
from tests.unit.aides import ROOT
from tests.unit.test_commandes_assemblages import commands_of, noop, registered_commands
from tests.unit.test_structure_gui import literal_text_calls

GUI = ROOT / "freecad" / "menuiserie" / "gui"
COMMAND = GUI / "commands" / "distance.py"
PANEL = GUI / "task_panels" / "distance.py"
INIT_GUI = ROOT / "freecad" / "menuiserie" / "init_gui.py"
NAME = "Menuiserie_SetDistance"


def test_textes_et_transaction() -> None:
    """Textes traduisibles dans le contexte de la commande, une entrée d'annulation."""
    attributes = commands_of(COMMAND)[NAME]
    assert noop(attributes["MENU_TEXT"]) == (NAME, "Définir une distance")
    context, tool_tip = noop(attributes["TOOL_TIP"])
    assert (context, bool(tool_tip.strip())) == (NAME, True)
    assert noop(attributes["TRANSACTION"]) == ("Menuiserie", "Définir une distance")


def test_icone_generee() -> None:
    assert (ICONS_DIR / f"{NAME}.svg").is_file()
    assert f'"{NAME}.svg"' in (ROOT / "tools" / "generer_icones.py").read_text(encoding="utf-8")


def test_commande_enregistree_et_dans_l_atelier() -> None:
    assert registered_commands(COMMAND) == [NAME]
    assert f'"{NAME}"' in INIT_GUI.read_text(encoding="utf-8")


def test_menu_contextuel_de_l_atelier() -> None:
    """``ContextMenu(recipient)`` : seul l'atelier actif ajoute l'entrée (ADR 0007)."""
    tree = ast.parse(INIT_GUI.read_text(encoding="utf-8"))
    methods = {
        item.name: item
        for node in tree.body
        if isinstance(node, ast.ClassDef)
        for item in node.body
        if isinstance(item, ast.FunctionDef)
    }
    assert [arg.arg for arg in methods["ContextMenu"].args.args] == ["self", "recipient"]


def test_aucun_texte_en_dur_dans_le_panneau() -> None:
    assert literal_text_calls(PANEL) == []


def test_case_garder_du_panneau() -> None:
    """DI-c : la case « Garder cette distance » est cochée par défaut, grisée avec la raison du
    refus en infobulle (``keep_reason``), et « OK » garde la distance (``finish(keep=...)``) ;
    une rangée bloquée propose « Ne plus garder et appliquer »."""
    source = PANEL.read_text(encoding="utf-8")
    assert "self._keep.setChecked(True)" in source
    assert "self._move.keep_reason(" in source
    assert "self._keep.setEnabled(why is None)" in source
    assert "self._move.finish(keep=keep" in source
    assert "Ne plus garder et appliquer" in source
    assert literal_text_calls(GUI / "task_panels" / "distance_kept.py") == []


def test_vue_de_la_distance_gardee() -> None:
    """Le ViewProvider de la Distance : chemin figé (ADR 0003) et icône générée."""
    view = GUI / "view_providers" / "distance.py"
    assert "class ViewProviderDistance(PanelEditing)" in view.read_text(encoding="utf-8")
    assert (ICONS_DIR / "Menuiserie_Distance.svg").is_file()
    assert '"Menuiserie_Distance.svg"' in (ROOT / "tools" / "generer_icones.py").read_text(
        encoding="utf-8"
    )
