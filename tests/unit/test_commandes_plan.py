# SPDX-License-Identifier: LGPL-2.1-or-later
"""Commandes des plans cotés (issue #153, lot P-b) vérifiées sans FreeCAD : analyse statique du
module de commandes, icônes et thème de la barre d'outils."""

from __future__ import annotations

import pytest

from freecad.menuiserie import ICONS_DIR
from tests.commandes_plan import COMMANDES_PLAN
from tests.unit.aides import ROOT
from tests.unit.test_commandes_assemblages import (
    commands_of,
    init_gui_themes,
    noop,
    registered_commands,
)

COMMANDS = ROOT / "freecad" / "menuiserie" / "gui" / "commands" / "drawing.py"


def test_une_classe_par_commande() -> None:
    assert set(commands_of(COMMANDS)) == set(COMMANDES_PLAN)


@pytest.mark.parametrize("name", list(COMMANDES_PLAN))
def test_textes_traduisibles_dans_le_contexte_de_la_commande(name: str) -> None:
    attributes = commands_of(COMMANDS)[name]
    assert noop(attributes["MENU_TEXT"]) == (name, COMMANDES_PLAN[name])
    context, tool_tip = noop(attributes["TOOL_TIP"])
    assert (context, bool(tool_tip.strip())) == (name, True)


@pytest.mark.parametrize("name", list(COMMANDES_PLAN))
def test_icone_generee(name: str) -> None:
    assert (ICONS_DIR / f"{name}.svg").is_file()
    assert f'"{name}.svg"' in (ROOT / "tools" / "generer_icones.py").read_text(encoding="utf-8")


def test_commandes_enregistrees() -> None:
    assert registered_commands(COMMANDS) == sorted(COMMANDES_PLAN)


def test_commandes_dans_leur_theme() -> None:
    assert init_gui_themes()["Plans"] == tuple(COMMANDES_PLAN)
