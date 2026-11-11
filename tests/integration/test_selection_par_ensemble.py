# SPDX-License-Identifier: LGPL-2.1-or-later
"""Chaîne d'ensembles d'une pièce pour la sélection dans la vue 3D (ADR 0047) : non-régression."""

from __future__ import annotations

from typing import Any

import pytest

from tests.integration.bureau import build_parts
from tests.integration.test_ensemble_membres import caisson

pytestmark = pytest.mark.integration

api = pytest.importorskip("freecad.menuiserie.api")
chain = pytest.importorskip("freecad.menuiserie.features.selection_chain")
container = pytest.importorskip("freecad.menuiserie.features.furniture_container")
rules = pytest.importorskip("freecad.menuiserie.core.selection_chain")


def names(objects: list[Any]) -> list[str]:
    return [obj.Name for obj in objects]


def meuble(document: Any) -> tuple[Any, Any, Any, dict[str, Any]]:
    """Bureau qui contient le sous-ensemble Caisson : (bureau, caisson, plateau, pièces du
    caisson)."""
    bureau = build_parts(document)
    sub, parts = caisson(document)
    furniture, _ = api.make_furniture(
        [*(bureau.parts[mark] for mark in ("P", "JG", "JD")), sub], label="Bureau"
    )
    return furniture, sub, bureau.parts["P"], parts


def test_piece_libre_sans_chaine(document: Any) -> None:
    piece = api.make_wood_part(500, 300, 18, "chene", doc=document)
    document.recompute()
    assert chain.chain_of(piece) == []


def test_chaine_d_une_piece_et_de_sa_piece_usinee(document: Any) -> None:
    furniture, sub, plateau, parts = meuble(document)
    assert names(chain.chain_of(plateau)) == [furniture.Name, plateau.Name]
    bottom = parts["CB"]
    expected = [furniture.Name, sub.Name, bottom.Name]
    assert names(chain.chain_of(bottom)) == expected
    machined = api.machined_part_of(bottom)
    if machined is not None:  # la pièce visible est l'usinée : même chaîne (brute en dernier)
        assert names(chain.chain_of(machined)) == expected
    assert names(chain.chain_of(sub)) == [furniture.Name, sub.Name]
    assert chain.chain_of(furniture) == []  # ensemble de plus haut niveau


def test_normalise_std_part_et_piece_usinee(document: Any) -> None:
    furniture, sub, _, parts = meuble(document)
    assert chain.normalized(container.std_part_of(furniture)) == furniture
    assert chain.normalized(container.std_part_of(sub)) == sub
    machined = api.machined_part_of(parts["CG"])
    if machined is not None:
        assert chain.normalized(machined) == parts["CG"]


def test_parcours_complet_descente_et_remontee(document: Any) -> None:
    """Clic, double-clics jusqu'à la pièce, double-clic de plus (panneau), remontée."""
    furniture, sub, _, parts = meuble(document)
    keys = names(chain.chain_of(parts["CB"]))
    current = rules.click_target(keys, None)
    assert current == furniture.Name
    current = rules.double_click_target(keys, current)
    assert current == sub.Name
    assert rules.click_target(keys, current) == sub.Name  # clic simple dans le tiroir : inchangé
    current = rules.double_click_target(keys, current)
    assert current == parts["CB"].Name
    assert rules.double_click_target(keys, current) is None  # panneau de la pièce
    up = rules.up_target(names(chain.chain_of(parts["CB"])))
    assert up == sub.Name
    assert rules.up_target(names(chain.chain_of(sub))) == furniture.Name


# --- Cas limites : lecture seule, enregistrement, annulation, suppression ---------------------


def etat(document: Any) -> list[tuple[str, tuple[str, ...]]]:
    return sorted((obj.Name, tuple(obj.PropertiesList)) for obj in document.Objects)


def test_la_chaine_n_ecrit_rien_dans_le_document(document: Any) -> None:
    """ADR 0007 : aucun objet, propriété ni transaction ; la chaîne est une simple lecture."""
    furniture, sub, plateau, parts = meuble(document)
    avant = etat(document)
    undo_avant = document.UndoCount
    for obj in (furniture, sub, plateau, parts["CB"]):
        chain.chain_of(obj)
        chain.normalized(obj)
    assert etat(document) == avant
    assert document.UndoCount == undo_avant


def test_chaine_apres_enregistrement_et_reouverture(document: Any, rouvrir: Any) -> None:
    furniture, sub, _, parts = meuble(document)
    attendu = {
        parts["CB"].Name: [furniture.Name, sub.Name, parts["CB"].Name],
        sub.Name: [furniture.Name, sub.Name],
    }
    rouvert = rouvrir(document)
    for name, expected in attendu.items():
        assert names(chain.chain_of(rouvert.getObject(name))) == expected
    assert chain.chain_of(rouvert.getObject(furniture.Name)) == []


def test_chaine_apres_annulation_et_retablissement_du_regroupement(document: Any) -> None:
    bureau = build_parts(document)
    pieces = [bureau.parts[mark] for mark in ("P", "JG", "JD")]
    document.openTransaction("Regrouper")
    furniture, _ = api.make_furniture(pieces, label="Bureau")
    document.commitTransaction()
    assert names(chain.chain_of(pieces[0])) == [furniture.Name, pieces[0].Name]
    name, piece_name = furniture.Name, pieces[0].Name
    document.undo()
    assert chain.chain_of(document.getObject(piece_name)) == []  # pièce redevenue libre
    document.redo()
    assert names(chain.chain_of(document.getObject(piece_name))) == [name, piece_name]


def test_chaine_apres_suppression_du_sous_ensemble_et_de_la_piece(document: Any) -> None:
    furniture, sub, _, parts = meuble(document)
    bottom_name = parts["CB"].Name
    document.openTransaction("Supprimer")
    document.removeObject(parts["CG"].Name)
    document.commitTransaction()
    # Les autres membres gardent leur chaîne.
    assert names(chain.chain_of(document.getObject(bottom_name))) == [
        furniture.Name,
        sub.Name,
        bottom_name,
    ]
    document.undo()
    assert document.getObject(parts["CG"].Name) is not None


def test_chaine_sans_cycle_ni_doublon(document: Any) -> None:
    furniture, sub, _, parts = meuble(document)
    keys = names(chain.chain_of(parts["CB"]))
    assert len(keys) == len(set(keys))
    assert keys[0] == furniture.Name
    assert chain.chain_of(furniture) == []
    assert rules.double_click_target(keys, furniture.Name) == sub.Name
    assert rules.up_target(names(chain.chain_of(furniture))) is None
