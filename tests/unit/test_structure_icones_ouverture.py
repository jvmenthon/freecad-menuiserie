# SPDX-License-Identifier: LGPL-2.1-or-later
"""Panneau « Structure » : icônes des lignes et ouverture par défaut (ADR 0046)."""

from __future__ import annotations

import ast
import re

import pytest

from freecad.menuiserie.core.structure_autostart import should_open_by_default
from freecad.menuiserie.core.structure_icons import ICON_BY_KIND, icon_name
from freecad.menuiserie.core.structure_tree import NodeKind
from tests.unit.aides import ROOT

ICONS = ROOT / "freecad" / "menuiserie" / "resources" / "icons"
GUI = ROOT / "freecad" / "menuiserie" / "gui"


def test_chaque_genre_de_ligne_a_une_icone_qui_existe() -> None:
    assert set(ICON_BY_KIND) == set(NodeKind)
    for kind in NodeKind:
        assert icon_name(kind).endswith(".svg")
        assert (ICONS / icon_name(kind)).is_file(), kind


def test_les_icones_ajoutees_viennent_du_generateur() -> None:
    generator = (ROOT / "tools" / "generer_icones.py").read_text(encoding="utf-8")
    for name in ("Menuiserie_Repeat.svg", "Menuiserie_Other.svg"):
        assert f'"{name}"' in generator
    names = set(ICON_BY_KIND.values())
    assert {
        "Menuiserie_Furniture.svg",
        "Menuiserie_WoodPart.svg",
        "Menuiserie_CutList.svg",
    } <= names


def test_genre_sans_entree_n_a_pas_d_icone() -> None:
    class Unknown:
        pass

    assert icon_name(Unknown()) == ""  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("closed", "exists", "expected"),
    [(False, False, True), (True, False, False), (False, True, False), (True, True, False)],
)
def test_ouverture_par_defaut(closed: bool, exists: bool, expected: bool) -> None:
    assert should_open_by_default(closed_by_user=closed, exists=exists) is expected


def test_l_icone_est_posee_et_chargee_sans_erreur() -> None:
    source = (GUI / "structure_tree_widget.py").read_text(encoding="utf-8")
    assert "setIcon(0," in source
    loader = (GUI / "structure_icons.py").read_text(encoding="utf-8")
    assert "is_file()" in loader and "QtGui.QIcon()" in loader  # repli sans icône
    assert re.search(r"from PySide import", loader) and "PySide6" not in loader


def test_un_seul_chemin_d_ouverture_et_reglage_hors_du_document() -> None:
    panel = (GUI / "structure_panel.py").read_text(encoding="utf-8")
    command = (GUI / "commands" / "structure.py").read_text(encoding="utf-8")
    assert "show_panel()" in command
    assert panel.count("def show_panel") == 1 and "show_panel(activate=False)" in panel
    prefs = (GUI / "structure_preferences.py").read_text(encoding="utf-8")
    assert "App.ParamGet" in prefs and "ActiveDocument" not in prefs
    init = (ROOT / "freecad" / "menuiserie" / "init_gui.py").read_text(encoding="utf-8")
    assert "open_by_default_later" in init
    ast.parse(panel)
