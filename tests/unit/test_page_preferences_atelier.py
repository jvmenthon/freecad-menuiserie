# SPDX-License-Identifier: LGPL-2.1-or-later
"""Page « Menuiserie » des préférences (ADR 0069) : textes déclarés à la traduction, inscription
dans l'interface. La page Qt elle-même est jouée dans FreeCAD (``tests/qtest``)."""

from __future__ import annotations

import ast

from freecad.menuiserie.kit.config.page_model import PAGE_TEXTS
from tests.unit.aides import ROOT

PACKAGE = ROOT / "freecad" / "menuiserie"
PAGE = PACKAGE / "gui" / "preferences_page.py"
INIT_GUI = PACKAGE / "init_gui.py"


def _declared_texts() -> list[str]:
    """Textes du tuple ``PAGE_TEXTS`` de ``gui/preferences_page.py`` (appels à
    ``QT_TRANSLATE_NOOP``), dans l'ordre."""
    tree = ast.parse(PAGE.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and getattr(node.target, "id", "") == "PAGE_TEXTS":
            assert isinstance(node.value, ast.Tuple)
            return [ast.literal_eval(call.args[1]) for call in node.value.elts]  # type: ignore[attr-defined]
    raise AssertionError("PAGE_TEXTS absent")


def test_textes_de_la_page_generique_declares_pour_la_traduction() -> None:
    assert _declared_texts() == list(PAGE_TEXTS)


def test_page_inscrite_dans_l_interface_sans_import_lourd() -> None:
    source = INIT_GUI.read_text(encoding="utf-8")
    assert 'Gui.addPreferencePage(MenuiseriePreferences, "Menuiserie")' in source
    tree = ast.parse(source)
    top_level = {
        alias.name for node in tree.body if isinstance(node, ast.ImportFrom) for alias in node.names
    }
    assert "MenuiseriePreferencePage" not in top_level  # importée à l'ouverture de la boîte
    assert (PACKAGE / "resources" / "icons" / "preferences-menuiserie.svg").is_file()
