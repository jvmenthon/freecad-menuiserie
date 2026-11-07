# SPDX-License-Identifier: LGPL-2.1-or-later
"""Mi-bois entre pièces en biais (ADR 0034, lot S-b, critères H1 à H3)."""

from __future__ import annotations

import pytest

from freecad.menuiserie.core._polyhedron import Polyhedron
from freecad.menuiserie.core.geometry import JointError
from freecad.menuiserie.core.joints import JointKind, strategy_for
from freecad.menuiserie.core.joints.half_lap import NOT_FLUSH, HalfLapParams
from tests.unit.aides_assemblages import placed, rotation_z
from tests.unit.aides_biais import rotation_x

HALF_LAP = strategy_for(JointKind.HALF_LAP)


def _bar(degrees: float, base: tuple[float, float, float]) -> object:
    return placed((300.0, 40.0, 20.0), rotation_z(degrees), base)


@pytest.mark.parametrize("degrees", [30.0, 60.0, 120.0])
def test_croix_en_biais_les_deux_entailles_partagent_la_matiere_commune(degrees: float) -> None:
    host = _bar(0.0, (0.0, 0.0, 0.0))
    guest = _bar(degrees, (150.0, -60.0, 0.0))
    values = HALF_LAP.resolve(host, guest, HalfLapParams())  # type: ignore[arg-type]
    assert isinstance(values.host_cut, Polyhedron) and isinstance(values.guest_cut, Polyhedron)
    assert values.depth == 10.0 and values.guest_depth == 10.0
    assert values.host_cut.volume() == pytest.approx(values.guest_cut.volume(), rel=1e-6)
    assert values.host_cut.volume() > 0


def test_flip_side_inverse_les_entailles_sans_changer_leur_volume() -> None:
    host = _bar(0.0, (0.0, 0.0, 0.0))
    guest = _bar(45.0, (150.0, -60.0, 0.0))
    straight = HALF_LAP.resolve(host, guest, HalfLapParams())  # type: ignore[arg-type]
    flipped = HALF_LAP.resolve(host, guest, HalfLapParams(flip_side=True))  # type: ignore[arg-type]
    assert isinstance(straight.host_cut, Polyhedron) and isinstance(flipped.host_cut, Polyhedron)
    assert flipped.host_cut.volume() == pytest.approx(straight.host_cut.volume(), rel=1e-6)


def test_mi_bois_en_biais_refuse_des_pieces_qui_ne_sont_pas_a_fleur() -> None:
    host = _bar(0.0, (0.0, 0.0, 0.0))
    guest = placed((300.0, 40.0, 20.0), rotation_z(45.0), (150.0, -60.0, 5.0))
    with pytest.raises(JointError) as error:
        HALF_LAP.plan(host, guest, HalfLapParams())  # type: ignore[arg-type]
    assert error.value.template == NOT_FLUSH


def test_mi_bois_en_biais_refuse_une_inclinaison_hors_de_l_epaisseur() -> None:
    host = _bar(0.0, (0.0, 0.0, 0.0))
    guest = placed((300.0, 40.0, 20.0), rotation_x(20.0), (100.0, 0.0, 0.0))
    with pytest.raises(JointError):
        HALF_LAP.plan(host, guest, HalfLapParams())  # type: ignore[arg-type]


def test_croix_a_30_degres_a_la_surface_du_losange() -> None:
    import math

    angle = math.radians(30.0)
    # Centre de l'invitée posé sur le centre (150, 20) de l'hôte.
    base = (
        150.0 - (150.0 * math.cos(angle) - 20.0 * math.sin(angle)),
        20.0 - (150.0 * math.sin(angle) + 20.0 * math.cos(angle)),
        0.0,
    )
    values = HALF_LAP.resolve(_bar(0.0, (0.0, 0.0, 0.0)), _bar(30.0, base), HalfLapParams())  # type: ignore[arg-type]
    assert isinstance(values.host_cut, Polyhedron)
    assert values.host_cut.volume() == pytest.approx(40.0 * 40.0 / math.sin(angle) * 10.0, rel=1e-6)
