# SPDX-License-Identifier: LGPL-2.1-or-later
"""Position relative de deux pièces en biais : ``relation`` (AB-a, A2 à A6)."""

from __future__ import annotations

import math

import pytest

from freecad.menuiserie.core._oblique_contact import EDGE_HIT, TOO_OBLIQUE
from freecad.menuiserie.core.contact import (
    Contact,
    ObliqueContact,
    Overlap,
    Separated,
    classify,
    relation,
)
from freecad.menuiserie.core.geometry import Axis, JointError, PlacedBlock, Vec3, is_square
from freecad.menuiserie.core.joints._roles import guess_roles
from tests.unit.aides_assemblages import placed, rail, rotation_z, stile
from tests.unit.aides_biais import (
    Mode,
    product,
    rail_against_stile,
    rotation_x,
    rotation_y,
    spun_rail,
    stile_block,
    tilted_rail,
)

WIDTH, THICKNESS = 60.0, 22.0


def oblique(host: PlacedBlock, guest: PlacedBlock) -> ObliqueContact:
    found = relation(host, guest)
    assert isinstance(found, ObliqueContact)
    return found


def volume(polyhedron: object) -> float:
    return 0.0 if polyhedron is None else polyhedron.volume()  # type: ignore[attr-defined]


def test_equerre_donne_exactement_classify() -> None:
    host, guest = stile(), rail()
    assert is_square(host, guest)
    assert relation(host, guest) == classify(host, guest)
    assert isinstance(relation(host, guest), Contact)


def test_is_square_faux_en_biais() -> None:
    assert not is_square(stile_block(), tilted_rail(10.0))


@pytest.mark.parametrize("degrees", [5.0, 10.0, 30.0, 45.0, 70.0])
def test_pointe_contre_la_face_ajoute_un_coin(degrees: float) -> None:
    contact = oblique(stile_block(), tilted_rail(degrees, "pointe"))
    wedge = 0.5 * WIDTH**2 * math.tan(math.radians(degrees)) * THICKNESS
    assert contact.angle == pytest.approx(degrees)
    assert contact.guest_face is Axis.X_NEG
    assert contact.host_face is Axis.Y_POS
    assert contact.removed is None
    assert volume(contact.added) == pytest.approx(wedge, rel=1e-6)
    assert contact.host_depth == pytest.approx(WIDTH)


@pytest.mark.parametrize("degrees", [5.0, 10.0, 30.0, 45.0, 70.0])
def test_hors_tout_retire_un_coin(degrees: float) -> None:
    contact = oblique(stile_block(), tilted_rail(degrees, "hors tout"))
    wedge = 0.5 * WIDTH**2 * math.tan(math.radians(degrees)) * THICKNESS
    assert contact.added is None
    assert volume(contact.removed) == pytest.approx(wedge, rel=1e-6)


@pytest.mark.parametrize("degrees", [5.0, 10.0, 30.0, 45.0, 70.0])
def test_a_cheval_retire_et_ajoute_deux_coins_egaux(degrees: float) -> None:
    contact = oblique(stile_block(), tilted_rail(degrees, "cheval"))
    wedge = 0.5 * (WIDTH / 2) ** 2 * math.tan(math.radians(degrees)) * THICKNESS
    assert volume(contact.removed) == pytest.approx(wedge, rel=1e-6)
    assert volume(contact.added) == pytest.approx(wedge, rel=1e-6)


def test_le_biais_se_lit_dans_les_deux_sens() -> None:
    plus, moins = (
        oblique(stile_block(), tilted_rail(15.0)),
        oblique(stile_block(), tilted_rail(-15.0)),
    )
    assert plus.angle == pytest.approx(15.0)
    assert moins.angle == pytest.approx(15.0)


def test_plan_d_epaulement_est_la_face_de_l_hote() -> None:
    contact = oblique(stile_block(), tilted_rail(10.0, "pointe"))
    host_normal = contact.transform.rotate(contact.shoulder.normal)
    assert (host_normal.x, host_normal.y, host_normal.z) == pytest.approx((0.0, 1.0, 0.0))
    opposite = contact.transform.rotate(contact.opposite.normal)
    assert opposite.y == pytest.approx(-1.0)


def test_71_degres_est_refuse_70_est_accepte() -> None:
    assert oblique(stile_block(), tilted_rail(70.0)).angle == pytest.approx(70.0)
    with pytest.raises(JointError) as error:
        relation(stile_block(), tilted_rail(71.0))
    assert error.value.template == TOO_OBLIQUE
    assert error.value.params["angle"] == "71.0"


def test_invitee_ecartee_est_separee() -> None:
    guest = tilted_rail(10.0, "pointe")
    lifted = placed(
        (guest.dimensions.length, guest.dimensions.width, guest.dimensions.thickness),
        [list(row) for row in guest.placement.rotation],
        (guest.placement.translation.x, guest.placement.translation.y + 5.0, 11.0),
    )
    assert isinstance(relation(stile_block(), lifted), Separated)


def test_bout_sur_l_arete_est_refuse() -> None:
    guest = tilted_rail(10.0, "cheval", centre_z=THICKNESS)
    with pytest.raises(JointError) as error:
        relation(stile_block(), guest)
    assert error.value.template == EDGE_HIT


def test_invitee_qui_traverse_l_hote_est_un_chevauchement() -> None:
    crossing = rail_against_stile(
        product(rotation_z(100.0)), "cheval", size=(280.0, WIDTH, THICKNESS)
    )
    deep = placed(
        (280.0, WIDTH, THICKNESS),
        [list(row) for row in crossing.placement.rotation],
        (crossing.placement.translation.x, -50.0, 0.0),
    )
    assert isinstance(relation(stile_block(), deep), Overlap)


def test_torsion_seule_de_30_degres() -> None:
    guest = spun_rail(30.0)
    assert not is_square(stile_block(), guest)
    contact = oblique(stile_block(), guest)
    assert contact.angle == pytest.approx(0.0, abs=1e-6)
    assert contact.removed is None
    assert contact.added is None


@pytest.mark.parametrize(("front", "side"), [(8.0, 8.0), (20.0, 15.0)])
def test_angle_compose_volumes_contre_echantillonnage(front: float, side: float) -> None:
    rotation = product(rotation_y(side), rotation_x(front), rotation_z(90.0))
    host = stile_block(thickness=80.0)  # assez épais pour que le coin y reste
    guest = rail_against_stile(rotation, "cheval", centre_z=40.0)
    contact = oblique(host, guest)
    assert 0.0 < contact.angle < 70.0
    assert contact.removed is not None
    assert contact.added is not None
    inside = _sampled_inside_volume(host, guest)
    assert volume(contact.removed) == pytest.approx(inside, rel=0.05)


def _sampled_inside_volume(host: PlacedBlock, guest: PlacedBlock) -> float:
    """Volume de la partie de l'invitée dans l'hôte, par échantillonnage régulier du bout."""
    steps = 40
    length = 40.0  # profondeur d'invitée examinée, largement au-delà du coin
    cell = (
        (length / steps) * (guest.dimensions.width / steps) * (guest.dimensions.thickness / steps)
    )
    to_host = host.placement.inverse().compose(guest.placement)
    box = host.local_box()
    count = 0
    for i in range(steps):
        for j in range(steps):
            for k in range(steps):
                local = Vec3(
                    (i + 0.5) * length / steps,
                    (j + 0.5) * guest.dimensions.width / steps,
                    (k + 0.5) * guest.dimensions.thickness / steps,
                )
                point = to_host.apply(local)
                if all(box.lo(a) <= point.component(a) <= box.hi(a) for a in range(3)):
                    count += 1
    return count * cell


@pytest.mark.parametrize("mode", ["pointe", "hors tout", "cheval"])
def test_roles_en_biais_l_invitee_est_celle_dont_le_bout_touche(mode: Mode) -> None:
    host, guest = stile_block(), tilted_rail(10.0, mode)
    assert guess_roles(host, guest) == (0, 1)
    assert guess_roles(guest, host) == (1, 0)
