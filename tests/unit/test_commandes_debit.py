# SPDX-License-Identifier: LGPL-2.1-or-later
"""Commandes de la liste de débit (J2d, critères G1 à G3) vérifiées sans FreeCAD : analyse
statique du module de commandes (il importe ``FreeCADGui``) et nom d'export proposé (logique
pure de ``features/cutlist_export.py``, sur FreeCAD simulé)."""

from __future__ import annotations

import ast
from collections.abc import Iterator
from pathlib import Path

import pytest

from freecad.menuiserie import ICONS_DIR
from tests.commandes_debit import COMMANDES_DEBIT
from tests.unit.aides import ROOT
from tests.unit.aides_debit_document import World, simulated_world
from tests.unit.test_commandes_assemblages import commands_of, noop, registered_commands, tree

PACKAGE = ROOT / "freecad" / "menuiserie"
COMMANDS = PACKAGE / "gui" / "commands" / "cutlist.py"
SOURCE = COMMANDS.read_text(encoding="utf-8")


@pytest.fixture
def world(monkeypatch: pytest.MonkeyPatch) -> Iterator[World]:
    with simulated_world(monkeypatch) as simulated:
        yield simulated


def test_une_classe_par_commande() -> None:
    assert set(commands_of(COMMANDS)) == set(COMMANDES_DEBIT)


@pytest.mark.parametrize("name", list(COMMANDES_DEBIT))
def test_textes_traduisibles_dans_le_contexte_de_la_commande(name: str) -> None:
    attributes = commands_of(COMMANDS)[name]
    assert noop(attributes["MENU_TEXT"]) == (name, COMMANDES_DEBIT[name])
    context, tool_tip = noop(attributes["TOOL_TIP"])
    assert (context, bool(tool_tip.strip())) == (name, True)


@pytest.mark.parametrize("name", list(COMMANDES_DEBIT))
def test_icone_generee(name: str) -> None:
    assert (ICONS_DIR / f"{name}.svg").is_file()
    assert f'"{name}.svg"' in (ROOT / "tools" / "generer_icones.py").read_text(encoding="utf-8")


def test_commandes_enregistrees() -> None:
    assert registered_commands(COMMANDS) == sorted(COMMANDES_DEBIT)


def test_commandes_dans_la_barre_et_le_menu_apres_les_ensembles() -> None:
    """Complétées après les assemblages et les ensembles (``commands += (…)``), dans l'ordre."""
    added = [
        ast.literal_eval(node.value)
        for node in ast.walk(tree(PACKAGE / "init_gui.py"))
        if isinstance(node, ast.AugAssign)
        and isinstance(node.target, ast.Name)
        and node.target.id == "commands"
    ]
    assert added[-1] == tuple(COMMANDES_DEBIT)


def test_les_commandes_ne_modifient_pas_la_selection() -> None:
    """G3 : la sélection est seulement lue."""
    for forbidden in ("addSelection", "clearSelection", "removeSelection", "setSelection"):
        assert forbidden not in SOURCE


def test_refus_affiche_comme_les_assemblages() -> None:
    """G2 : un refus de l'api passe par la fonction commune de refus visible."""
    assert "report_refusal" in SOURCE
    assert "QFileDialog.getSaveFileName" in SOURCE


# --- Nom et dossier proposés ---------------------------------------------------------------


def test_nom_propose(world: World) -> None:
    export = world.features.cutlist_export
    assert export.proposed_file_name("Bureau") == "Bureau - liste de débit.csv"


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ('Table: 2/3 "salon"?', "Table_ 2_3 _salon__ - liste de débit.csv"),
        ("  Étagère…  ", "Étagère… - liste de débit.csv"),
        ("Cuisine.", "Cuisine - liste de débit.csv"),
        ("a\nb\x00c", "a_b_c - liste de débit.csv"),
        ("", "Document - liste de débit.csv"),
        ("...", "Document - liste de débit.csv"),
    ],
)
def test_nom_propose_sans_caractere_interdit(world: World, label: str, expected: str) -> None:
    assert world.features.cutlist_export.proposed_file_name(label) == expected


def test_dossier_propose_a_cote_du_document(world: World, tmp_path: Path) -> None:
    export = world.features.cutlist_export
    document = tmp_path / "ateliers" / "bureau.FCStd"
    proposed = export.proposed_path("bureau", str(document), home=tmp_path / "home")
    assert proposed == tmp_path / "ateliers" / "bureau - liste de débit.csv"


def test_dossier_personnel_si_le_document_n_est_pas_enregistre(
    world: World, tmp_path: Path
) -> None:
    export = world.features.cutlist_export
    assert export.proposed_path("Sans nom", "", home=tmp_path) == (
        tmp_path / "Sans nom - liste de débit.csv"
    )


@pytest.mark.parametrize(
    ("chosen", "expected"),
    [
        ("dossier/debit", "dossier/debit.csv"),
        ("dossier/debit.csv", "dossier/debit.csv"),
        ("a.txt", "a.txt"),
    ],
)
def test_extension_csv_ajoutee_si_absente(world: World, chosen: str, expected: str) -> None:
    """Qt n'ajoute pas l'extension : sans extension saisie, « .csv » ; une autre extension est
    gardée (et refusée ensuite par ``validated_path``)."""
    assert world.features.cutlist_export.with_csv_suffix(chosen) == expected
