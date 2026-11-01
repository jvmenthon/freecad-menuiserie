# SPDX-License-Identifier: LGPL-2.1-or-later
"""Épaisseur d'une pièce assemblée modifiée : les pièces posées sur sa face haute la suivent
(#133). Pièce porteuse de la mortaise = ``host`` ; montant = ``guest``, tenon en bas."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
api = pytest.importorskip("freecad.menuiserie.api")
base = pytest.importorskip("freecad.menuiserie.features.joints.base")


def stand_on(guest: Any, x: float, z: float) -> None:
    """Montant dressé (longueur selon +Z) dont le bout est en (x, 0, z)."""
    guest.Placement = App.Placement(App.Vector(x, 0, z), App.Rotation(App.Vector(0, 1, 0), -90))


@pytest.fixture
def pieces(document: Any) -> Iterator[tuple[Any, Any, Any]]:
    host = api.make_wood_part(600, 100, 30, doc=document)
    guest = api.make_wood_part(400, 100, 30, doc=document)
    stand_on(guest, 300, 30)
    document.recompute()
    joint = api.make_mortise_tenon(host, guest)
    yield host, guest, joint


def assert_joint_holds(document: Any, joint: Any) -> None:
    document.recompute()
    assert "Invalid" not in joint.State
    assert base.plan_for(joint)  # le plan d'usinage existe : les pièces se touchent


def test_epaisseur_reduite_le_montant_suit(document: Any, pieces: tuple[Any, Any, Any]) -> None:
    host, guest, joint = pieces
    host.Thickness = 22
    assert guest.Placement.Base.z == pytest.approx(22)
    assert_joint_holds(document, joint)


def test_epaisseur_augmentee_le_montant_suit(document: Any, pieces: tuple[Any, Any, Any]) -> None:
    host, guest, joint = pieces
    host.Thickness = 40
    assert guest.Placement.Base.z == pytest.approx(40)
    assert_joint_holds(document, joint)


def test_montant_pilote_par_expression_reste_en_place(
    document: Any, pieces: tuple[Any, Any, Any]
) -> None:
    host, guest, _joint = pieces
    guest.setExpression("Placement.Base.z", "30 mm")
    document.recompute()
    host.Thickness = 22
    assert guest.Placement.Base.z == pytest.approx(30)
