# SPDX-License-Identifier: LGPL-2.1-or-later
"""Commande « Aligner deux faces » (AL-c, ADR 0054) vérifiée sans FreeCAD, par analyse statique."""

from __future__ import annotations

import ast

from freecad.menuiserie import ICONS_DIR
from tests.unit.aides import ROOT
from tests.unit.test_commandes_assemblages import (
    commands_of,
    init_gui_commands,
    noop,
    registered_commands,
)
from tests.unit.test_structure_gui import literal_text_calls

PACKAGE = ROOT / "freecad" / "menuiserie"
COMMAND = PACKAGE / "gui" / "commands" / "align.py"
INIT_GUI = PACKAGE / "init_gui.py"
NAME = "Menuiserie_AlignFaces"


def test_textes_et_transaction() -> None:
    attributes = commands_of(COMMAND)[NAME]
    assert noop(attributes["MENU_TEXT"]) == (NAME, "Aligner deux faces")
    context, tool_tip = noop(attributes["TOOL_TIP"])
    assert (context, bool(tool_tip.strip())) == (NAME, True)
    assert noop(attributes["TRANSACTION"]) == ("Menuiserie", "Aligner deux faces")


def test_aucun_texte_en_dur() -> None:
    assert literal_text_calls(COMMAND) == []
    assert literal_text_calls(PACKAGE / "features" / "part_align.py") == []


def test_icone_generee_et_declaree() -> None:
    icon = ICONS_DIR / f"{NAME}.svg"
    assert icon.is_file() and icon.read_text(encoding="utf-8").lstrip().startswith(
        ("<?xml", "<svg")
    )
    assert f'"{NAME}.svg"' in (ROOT / "tools" / "generer_icones.py").read_text(encoding="utf-8")


def test_commande_enregistree_une_fois_et_dans_la_barre() -> None:
    assert registered_commands(COMMAND) == [NAME]
    assert init_gui_commands().count(NAME) == 1
    source = INIT_GUI.read_text(encoding="utf-8")
    assert "align.register()" in source


def test_prerequis_traduit_pour_la_commande_inactive() -> None:
    attributes = commands_of(COMMAND)[NAME]
    assert isinstance(attributes["PREREQUISITE"], ast.Attribute)
    hints = (PACKAGE / "gui" / "commands" / "hints.py").read_text(encoding="utf-8")
    assert "ALIGN_FACES" in hints


def test_menu_contextuel_ajoute_l_entree_seulement_pour_deux_faces() -> None:
    tree = ast.parse(INIT_GUI.read_text(encoding="utf-8"))
    method = next(
        item
        for node in tree.body
        if isinstance(node, ast.ClassDef)
        for item in node.body
        if isinstance(item, ast.FunctionDef) and item.name == "ContextMenu"
    )
    source = ast.unparse(method)
    assert "align.selected_faces()" in source
    assert "appendContextMenu('', [align.COMMAND_NAME])" in source
    # l'entrée de la distance reste proposée pour toute paire d'éléments
    assert "appendContextMenu('', [distance.COMMAND_NAME])" in source


def test_annulation_et_refus_dans_la_commande() -> None:
    """Une seule transaction ``refusable_transaction`` ; l'annulation du choix des assemblages
    devient un refus ``ValueError`` traduit (ni exception brute, ni modification)."""
    source = COMMAND.read_text(encoding="utf-8")
    assert "with refusable_transaction(doc, self.TRANSACTION):" in source
    assert "except DragCancelledError" in source
    assert "raise ValueError(translated(_CANCELLED))" in source
    assert "joint_choice.choose" in source
    assert "Gui.Control.activeDialog()" in source


def test_pas_de_commande_orpheline_dans_l_api_publique() -> None:
    source = (PACKAGE / "api.py").read_text(encoding="utf-8")
    assert source.count('"align_faces"') == 1
