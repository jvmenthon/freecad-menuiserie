# SPDX-License-Identifier: LGPL-2.1-or-later
"""Onglet entre pièces en biais (ADR 0034, lot S-b, critères M1 à M3)."""

from __future__ import annotations

import math

import pytest

from freecad.menuiserie.core.geometry import JointError, PlacedBlock
from freecad.menuiserie.core.joints import JointKind, strategy_for
from freecad.menuiserie.core.joints.miter import MiterParams
from tests.unit.aides_assemblages import placed, rotation_z
from tests.unit.aides_biais import product, rotation_x

MITER = strategy_for(JointKind.MITER)


def _frame(degrees: float, width: float = 40.0) -> tuple[PlacedBlock, PlacedBlock]:
    """Deux barres de même largeur qui se rencontrent au coin (0, 0) : l'hôte sur +X, l'invitée à
    ``degrees`` de l'hôte ; chacune dépasse le coin de 100 mm (dessinées hors tout)."""
    angle = math.radians(degrees)
    along = (math.cos(angle), math.sin(angle))
    across = (-math.sin(angle), math.cos(angle))
    # La largeur de l'invitée part du côté de l'hôte : son bord extérieur passe par le coin.
    side = -width
    base = (
        -100.0 * along[0] + side * across[0],
        -100.0 * along[1] + side * across[1],
        0.0,
    )
    host = placed((500.0, width, 20.0), rotation_z(0.0), (-100.0, 0.0, 0.0))
    guest = placed((500.0, width, 20.0), rotation_z(degrees), base)
    return host, guest


@pytest.mark.parametrize(
    ("degrees", "expected"),
    [(60.0, 60.0), (45.0, 67.5), (89.0, 45.5), (120.0, 30.0), (135.0, 22.5)],
)
def test_onglet_de_deux_largeurs_egales_coupe_a_la_bissectrice(
    degrees: float, expected: float
) -> None:
    host, guest = _frame(degrees)
    values = MITER.resolve(host, guest, MiterParams())
    assert values.host_angle == pytest.approx(expected, abs=0.01)
    assert values.guest_angle == pytest.approx(expected, abs=0.01)


@pytest.mark.parametrize("degrees", [60.0, 120.0])
def test_onglet_en_biais_les_deux_pieces_perdent_le_meme_plan(degrees: float) -> None:
    host, guest = _frame(degrees)
    plan = MITER.plan(host, guest, MiterParams())
    host_cut, guest_cut = plan.host_cuts[0], plan.guest_cuts[0]
    assert host_cut.volume() > 0 and guest_cut.volume() > 0  # type: ignore[union-attr]
    # Largeurs égales : le losange commun est partagé en deux triangles égaux.
    assert host_cut.volume() == pytest.approx(guest_cut.volume(), rel=1e-3)  # type: ignore[union-attr]
    assert not plan.guest_additions and not plan.host_additions


def test_onglet_en_biais_refuse_une_rotation_hors_de_l_arete() -> None:
    host = placed((400.0, 40.0, 20.0), rotation_z(0.0), (0.0, 0.0, 0.0))
    guest = placed(
        (400.0, 40.0, 20.0), product(rotation_z(30.0), rotation_x(20.0)), (0.0, 0.0, 0.0)
    )
    with pytest.raises(JointError):
        MITER.plan(host, guest, MiterParams())


def test_onglet_en_biais_refuse_un_angle_trop_ferme() -> None:
    host, guest = _frame(10.0)
    with pytest.raises(JointError):
        MITER.plan(host, guest, MiterParams())
