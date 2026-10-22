# SPDX-License-Identifier: LGPL-2.1-or-later
"""Commandes, ViewProvider et panneau de l'ensemble (J4c, critères P1, P2, P6) vérifiés sans
FreeCAD, par analyse statique : les modules de ``gui/`` importent ``FreeCADGui``."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from freecad.menuiserie import ICONS_DIR
from tests.commandes_ensembles import COMMANDES_ENSEMBLE
from tests.unit.aides import ROOT, imported_modules
from tests.unit.test_commandes_assemblages import (
    class_attributes,
    commands_of,
    noop,
    registered_commands,
)

GUI = ROOT / "freecad" / "menuiserie" / "gui"
COMMANDS = GUI / "commands" / "furniture.py"
MODULES = (
    COMMANDS,
    GUI / "view_providers" / "furniture.py",
    GUI / "task_panels" / "furniture.py",
    GUI / "task_panels" / "furniture_widgets.py",
)


def furniture_commands() -> dict[str, dict[str, ast.expr]]:
    """Attributs des commandes de l'ensemble, par nom de commande (``NAME``)."""
    return commands_of(COMMANDS)


def test_une_classe_par_commande() -> None:
    assert set(furniture_commands()) == set(COMMANDES_ENSEMBLE)


@pytest.mark.parametrize("name", list(COMMANDES_ENSEMBLE))
def test_textes_et_transaction(name: str) -> None:
    """P1 : textes traduisibles dans le contexte de la commande, une entrée d'annulation."""
    attributes = furniture_commands()[name]
    label, transaction = COMMANDES_ENSEMBLE[name]
    assert noop(attributes["MENU_TEXT"]) == (name, label)
    context, tool_tip = noop(attributes["TOOL_TIP"])
    assert (context, bool(tool_tip.strip())) == (name, True)
    assert noop(attributes["TRANSACTION"]) == ("Menuiserie", transaction)


@pytest.mark.parametrize("name", list(COMMANDES_ENSEMBLE))
def test_icone_generee(name: str) -> None:
    """P1 : icône ``<commande>.svg`` produite par ``tools/generer_icones.py``."""
    assert (ICONS_DIR / f"{name}.svg").is_file()
    assert f'"{name}.svg"' in (ROOT / "tools" / "generer_icones.py").read_text(encoding="utf-8")


def test_toutes_les_commandes_enregistrees() -> None:
    assert registered_commands(COMMANDS) == sorted(COMMANDES_ENSEMBLE)


def test_view_provider_au_chemin_fige_et_pose_par_l_api() -> None:
    """P2 : chemin enregistré dans les documents (ADR 0003), posé par ``make_furniture``."""
    assert "ViewProviderFurniture" in class_attributes(GUI / "view_providers" / "furniture.py")
    api = ROOT / "freecad" / "menuiserie" / "api.py"
    assert "freecad.menuiserie.gui.view_providers.furniture" in imported_modules(api)


@pytest.mark.parametrize("path", MODULES, ids=lambda p: p.name)
def test_aucun_observateur_global(path: Path) -> None:
    """P6 : ni observateur global ni préférence ; la surveillance du document est celle du
    socle des panneaux (retirée à la fermeture)."""
    text = path.read_text(encoding="utf-8")
    for forbidden in ("addDocumentObserver", "Selection.addObserver", "ParamGet"):
        assert forbidden not in text, f"{path.name} : {forbidden}"
