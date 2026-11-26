# SPDX-License-Identifier: LGPL-2.1-or-later
"""Page « Menuiserie » des préférences (ADR 0069) : textes déclarés à la traduction, inscription
dans l'interface. La page Qt elle-même est jouée dans FreeCAD (``tests/qtest``)."""

from __future__ import annotations

import ast

from freecad.menuiserie.kit.config.page_model import PAGE_TEXTS
from tests.unit.aides import ROOT, imported_modules

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


def _function(name: str, owner: str | None = None) -> ast.FunctionDef:
    tree = ast.parse(INIT_GUI.read_text(encoding="utf-8"))
    nodes: list[ast.stmt] = tree.body
    if owner is not None:
        nodes = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == owner).body
    return next(n for n in nodes if isinstance(n, ast.FunctionDef) and n.name == name)


def test_enregistrement_de_la_page_n_empeche_pas_l_atelier() -> None:
    """Icônes, traductions et page sont inscrites dans un ``try`` qui avertit : l'atelier reste
    enregistré si l'un d'eux échoue."""
    register = _function("register_preferences")
    (attempt,) = (n for n in register.body if isinstance(n, ast.Try))
    body = ast.unparse(ast.Module(attempt.body, []))
    for call in ("Gui.addLanguagePath", "Gui.addIconPath", "Gui.addPreferencePage"):
        assert call in body
    assert "PrintWarning" in ast.unparse(ast.Module(attempt.handlers[0].body, []))
    source = INIT_GUI.read_text(encoding="utf-8")
    assert source.index("Gui.addWorkbench(") < source.index("\nregister_preferences()")


def test_page_de_repli_si_la_vraie_page_echoue() -> None:
    """La construction de la page est essayée ; sinon l'erreur est journalisée et une page de
    repli (``PySide`` seul) prend sa place."""
    init = _function("__init__", "MenuiseriePreferences")
    (attempt,) = (n for n in init.body if isinstance(n, ast.Try))
    handler = ast.unparse(ast.Module(attempt.handlers[0].body, []))
    assert "PrintError" in handler
    assert "FallbackPage" in handler
    fallback = PACKAGE / "gui" / "preferences_fallback.py"
    roots = {m.split(".")[0] for m in imported_modules(fallback)} - {"__future__"}
    assert roots == {"PySide"}
