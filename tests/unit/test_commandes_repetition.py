# SPDX-License-Identifier: LGPL-2.1-or-later
"""Commandes, ViewProvider et panneau de la répétition (lot R-c, ADR 0043) vérifiés sans FreeCAD,
par analyse statique : les modules de ``gui/`` importent ``FreeCADGui``."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from freecad.menuiserie import ICONS_DIR
from tests.commandes_repetition import COMMANDES_REPETITION
from tests.unit.aides import ROOT, imported_modules
from tests.unit.test_commandes_assemblages import (
    class_attributes,
    commands_of,
    init_gui_themes,
    module_constants,
    noop,
    registered_commands,
)

GUI = ROOT / "freecad" / "menuiserie" / "gui"
COMMANDS = GUI / "commands" / "repeat.py"
PANEL = GUI / "task_panels" / "repeat.py"
ROWS = GUI / "task_panels" / "repeat_rows.py"  # lignes X, Y, Z (ADR 0045)
VIEW_PROVIDER = GUI / "view_providers" / "repeat.py"
MODULES = (COMMANDS, PANEL, VIEW_PROVIDER)
FIELDS = (
    "spacing",
    "count",
    "step",
    "span",
    "reverse",
    "copyJoints",
    "followResize",
    "summaryLabel",
    "warningLabel",
    "errorLabel",
)


def repeat_commands() -> dict[str, dict[str, ast.expr]]:
    """Attributs des commandes de la répétition, par nom de commande (``NAME``)."""
    return commands_of(COMMANDS)


def test_une_classe_par_commande() -> None:
    assert set(repeat_commands()) == set(COMMANDES_REPETITION)


@pytest.mark.parametrize("name", list(COMMANDES_REPETITION))
def test_textes_et_transaction(name: str) -> None:
    """Textes traduisibles dans le contexte de la commande, une entrée d'annulation."""
    attributes = repeat_commands()[name]
    label, transaction = COMMANDES_REPETITION[name]
    assert noop(attributes["MENU_TEXT"]) == (name, label)
    context, tool_tip = noop(attributes["TOOL_TIP"])
    assert (context, bool(tool_tip.strip())) == (name, True)
    assert noop(attributes["TRANSACTION"]) == ("Menuiserie", transaction)


@pytest.mark.parametrize("name", [*COMMANDES_REPETITION, "Menuiserie_RepeatObject"])
def test_icone_generee(name: str) -> None:
    """Icône ``<commande>.svg`` produite par ``tools/generer_icones.py`` (la correspondance des
    fichiers est vérifiée par ``test_icones.py``)."""
    assert (ICONS_DIR / f"{name}.svg").is_file()
    assert f'"{name}.svg"' in (ROOT / "tools" / "generer_icones.py").read_text(encoding="utf-8")


def test_toutes_les_commandes_enregistrees() -> None:
    assert registered_commands(COMMANDS) == sorted(COMMANDES_REPETITION)


def test_commandes_dans_la_barre_et_le_menu() -> None:
    """Un thème « Répétition » : une barre d'outils et le menu de l'atelier, dans l'ordre."""
    assert init_gui_themes()["Répétition"] == tuple(COMMANDES_REPETITION)


def test_icone_de_l_objet_dans_l_arbre() -> None:
    assert module_constants(VIEW_PROVIDER)["ICON"] == "Menuiserie_RepeatObject.svg"


def test_view_provider_au_chemin_fige_et_pose_par_le_panneau() -> None:
    """Chemin enregistré dans les documents (ADR 0003) ; ``_api/repeat.py`` ne touche pas à
    l'interface : le panneau et la commande « Modifier la répétition » posent le ViewProvider."""
    assert "ViewProviderRepeat" in class_attributes(VIEW_PROVIDER)
    assert "freecad.menuiserie.gui.view_providers.repeat" in imported_modules(PANEL)
    assert "freecad.menuiserie.gui.view_providers.repeat" in imported_modules(COMMANDS)


def test_double_clic_sur_la_repetition_seulement() -> None:
    """Le ViewProvider ouvre « Modifier la répétition » ; une copie garde le ViewProvider de la
    pièce de bois (aucune surcharge de ``ViewProviderWoodPart``)."""
    text = VIEW_PROVIDER.read_text(encoding="utf-8")
    assert "start_editing" in text
    assert "import ViewProviderWoodPart" not in text


@pytest.mark.parametrize("path", MODULES, ids=lambda p: p.name)
def test_aucun_observateur_global(path: Path) -> None:
    """Ni observateur global ni préférence ; la surveillance du document est celle du socle des
    panneaux (retirée à la fermeture)."""
    text = path.read_text(encoding="utf-8")
    for forbidden in ("addDocumentObserver", "Selection.addObserver", "ParamGet"):
        assert forbidden not in text, f"{path.name} : {forbidden}"


def test_panneau_par_l_api_dans_la_transaction_du_panneau() -> None:
    """Le panneau n'écrit rien lui-même : ``make_repeat`` puis ``edit_repeat``, dans la
    transaction qu'il n'ouvre pas (``transaction=False``)."""
    calls = {
        node.func.attr: [kw.arg for kw in node.keywords]
        for node in ast.walk(ast.parse(PANEL.read_text(encoding="utf-8")))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in {"make_repeat", "edit_repeat"}
    }
    assert calls == {
        "make_repeat": ["transaction", "stops"],
        "edit_repeat": ["transaction", "stops"],
    }


@pytest.mark.parametrize("name", FIELDS)
def test_champs_du_panneau(name: str) -> None:
    text = PANEL.read_text(encoding="utf-8") + ROWS.read_text(encoding="utf-8")
    assert f'"{name}"' in text or f'f"{name}{{' in text


def test_saisie_appliquee_en_fin_de_frappe() -> None:
    """CONTRIBUTING, « Entrées utilisateur » 3 : le nombre est en ``setKeyboardTracking(False)``
    et les champs de cote viennent de ``quantity_field`` (même réglage)."""
    text = ROWS.read_text(encoding="utf-8")
    assert "setKeyboardTracking(False)" in text
    assert text.count("quantity_field(") == 2
    furniture_widgets = (GUI / "task_panels" / "furniture_widgets.py").read_text(encoding="utf-8")
    assert "field.setKeyboardTracking(False)" in furniture_widgets


def test_ok_grise_et_refus_sans_exception() -> None:
    """« OK » grisé (``set_ok_enabled``) tant que la saisie est refusée ; les refus de l'api sont
    attrapés (jamais d'exception dans la boucle d'événements Qt)."""
    text = PANEL.read_text(encoding="utf-8")
    assert "set_ok_enabled(" in text
    assert "except (TypeError, ValueError, KeyError)" in text


def test_suivi_du_redimensionnement_grise_hors_ensemble() -> None:
    text = PANEL.read_text(encoding="utf-8")
    assert "furniture_of(" in text
    assert "FOLLOW_DISABLED_TIP" in text
