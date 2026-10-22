# SPDX-License-Identifier: LGPL-2.1-or-later
"""Nom d'un assemblage « {type} : {hôte} {invitée} », tenu à jour au renommage des pièces (J6,
demande de jv)."""

from __future__ import annotations

from typing import Any

import pytest

from tests.integration.types_assemblages import DOVETAIL, HALF_LAP, assemble, build

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")


def test_nom_de_l_assemblage_a_la_creation(document: Any) -> None:
    assert build(document, HALF_LAP).joint.Label == "Mi-bois : H I"


def test_changer_le_repere_renomme_l_assemblage(document: Any) -> None:
    montage = build(document, HALF_LAP)
    montage.host.Mark = "M5"
    assert montage.joint.Label == "Mi-bois : M5 I"


def test_renommer_la_piece_renomme_l_assemblage(document: Any) -> None:
    montage = build(document, HALF_LAP)
    montage.guest.Label = "T2"
    assert montage.joint.Label == "Mi-bois : H T2"


def test_deux_assemblages_des_memes_pieces_ont_des_noms_distincts(document: Any) -> None:
    montage = build(document, HALF_LAP)
    second = assemble(DOVETAIL, montage.host, montage.guest).joint
    first_twin = assemble(HALF_LAP, montage.host, montage.guest).joint
    assert second.Label == "Queue d'aronde : H I"
    assert first_twin.Label == "Mi-bois : H I (2)"
