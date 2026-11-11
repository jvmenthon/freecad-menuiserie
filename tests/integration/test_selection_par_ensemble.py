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
