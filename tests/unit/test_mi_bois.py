# SPDX-License-Identifier: LGPL-2.1-or-later
"""Mi-bois (J4e, critères B1 et B2)."""

from __future__ import annotations

import pytest

from freecad.menuiserie.core.geometry import Box, JointError, PlacedBlock, RigidTransform, Vec3
from freecad.menuiserie.core.joints import JointKind, guess_roles, strategy_for
from freecad.menuiserie.core.joints.half_lap import HalfLapParams, HalfLapValues
from freecad.menuiserie.core.part_model import Dimensions
from tests.unit.aides_assemblages import block, matrix, rail, rotation_z, stile

HALF_LAP = strategy_for(JointKind.HALF_LAP)
CROSSING = "dessinez les deux pièces qui se croisent"
NOT_FLUSH = "même épaisseur et être à fleur"


def box(low: tuple[float, float, float], high: tuple[float, float, float]) -> Box:
    return Box(Vec3(*low), Vec3(*high))


def cross(
    thickness: float = 22.0, guest_z: float = 0.0, guest_thickness: float | None = None
) -> tuple[PlacedBlock, PlacedBlock]:
    """Deux traverses 600 x 60 croisées en leur milieu ; l'invitée tournée de 90° autour de Z."""
    guest_size = (600.0, 60.0, guest_thickness or thickness)
    host = block((600.0, 60.0, thickness))
    return host, block(guest_size, (330.0, -270.0, guest_z), 90.0)


def corner() -> tuple[PlacedBlock, PlacedBlock]:
    """Angle de deux traverses 400 x 50 x 19 qui se chevauchent de 50 x 50 au bout."""
    return block((400.0, 50.0, 19.0)), block((400.0, 50.0, 19.0), (50.0, 0.0, 0.0), 90.0)


def values(
    pair: tuple[PlacedBlock, PlacedBlock], params: HalfLapParams | None = None
) -> HalfLapValues:
    result: HalfLapValues = HALF_LAP.resolve(*pair, params or HalfLapParams())
    return result


def refused(pair: tuple[PlacedBlock, PlacedBlock], text: str, **params: object) -> None:
    with pytest.raises(JointError, match=text):
        HALF_LAP.plan(*pair, HalfLapParams(**params))  # type: ignore[arg-type]


# --- B1 : paramètres, entailles automatiques --------------------------------------------


def test_parametres_par_defaut() -> None:
    params = HalfLapParams()
    assert (params.depth, params.flip_side) == (0.0, False)
    assert isinstance(HalfLapParams(depth=8).depth, float)


def test_croix_automatique() -> None:
    plan = HALF_LAP.plan(*cross(), HalfLapParams())
    assert plan.host_cuts == (box((270, 0, 11), (330, 60, 22)),)
    # Repère de l'invitée : X le long de sa longueur (Y du document), Y vers -X du document.
    assert plan.guest_cuts == (box((270, 0, 0), (330, 60, 11)),)
    assert plan.host_additions == plan.guest_additions == plan.inserts == ()


def test_angle_epaisseur_impaire() -> None:
    result = values(corner())
    assert (result.depth, result.guest_depth) == (10.0, 9.0)
    assert result.host_cut == box((0, 0, 9), (50, 50, 19))
    assert result.guest_cut == box((0, 0, 0), (50, 50, 9))


def test_flip_side_inverse_haut_et_bas() -> None:
    result = values(corner(), HalfLapParams(flip_side=True))
    assert result.host_cut == box((0, 0, 0), (50, 50, 10))
    assert result.guest_cut == box((0, 0, 10), (50, 50, 19))


def test_profondeur_saisie() -> None:
    result = values(cross(), HalfLapParams(depth=8))
    assert (result.depth, result.guest_depth) == (8.0, 14.0)
    assert result.host_cut == box((270, 0, 14), (330, 60, 22))
    assert result.guest_cut == box((270, 0, 0), (330, 60, 14))


def test_profondeur_automatique_suit_l_epaisseur() -> None:
    assert values(cross(thickness=27.0)).depth == 14.0
    assert values(cross(thickness=27.0), HalfLapParams(depth=11)).depth == 11.0


def test_invitee_retournee() -> None:
    """Invitée retournée (son +Z vers le bas) : elle perd toujours le bas de la croix."""
    flipped = [[1.0, 0.0, 0.0], [0.0, -1.0, 0.0], [0.0, 0.0, -1.0]]
    rotation = [
        [sum(rotation_z(90)[i][k] * flipped[k][j] for k in range(3)) for j in range(3)]
        for i in range(3)
    ]
    placement = RigidTransform.from_matrix(matrix(rotation, (270.0, -270.0, 22.0)))
    guest = PlacedBlock(Dimensions(600.0, 60.0, 22.0), placement)
    result = values((stile(), guest))
    assert result.host_cut == box((270, 0, 11), (330, 60, 22))
    assert result.guest_cut == box((270, 0, 11), (330, 60, 22))  # le haut de son repère


def test_a_fleur_a_la_tolerance_pres_sans_peau() -> None:
    result = values(cross(guest_z=0.005))
    assert result.guest_cut.lo(2) == pytest.approx(0.0)
    assert result.guest_cut.hi(2) == pytest.approx(11.0 - 0.005)


def test_roles_a_epaisseur_egale_ordre_conserve() -> None:
    host, guest = cross()
    assert guess_roles(host, guest) == (0, 1)
    assert guess_roles(guest, host) == (0, 1)


# --- B2 : refus ---------------------------------------------------------------------------


def test_refus_pieces_en_contact() -> None:
    refused((stile(), rail()), CROSSING)


def test_refus_pieces_ecartees() -> None:
    refused((stile(), block((600.0, 60.0, 22.0), (0.0, 100.0, 0.0))), CROSSING)


def test_refus_epaisseurs_differentes() -> None:
    refused(cross(guest_thickness=18.0), NOT_FLUSH)


def test_refus_pas_a_fleur() -> None:
    refused(cross(guest_z=2.0), NOT_FLUSH)


def test_refus_epaisseurs_non_paralleles() -> None:
    """Invitée sur chant (épaisseur selon Y du document) de largeur égale à l'épaisseur."""
    on_edge = [[1.0, 0.0, 0.0], [0.0, 0.0, -1.0], [0.0, 1.0, 0.0]]
    placement = RigidTransform.from_matrix(matrix(on_edge, (0.0, 50.0, 0.0)))
    guest = PlacedBlock(Dimensions(600.0, 22.0, 30.0), placement)
    refused((stile(), guest), NOT_FLUSH)


@pytest.mark.parametrize("depth", [22.0, 30.0])
def test_refus_profondeur_trop_grande(depth: float) -> None:
    with pytest.raises(JointError, match="moins profonde que l'épaisseur") as error:
        HALF_LAP.plan(*cross(), HalfLapParams(depth=depth))
    assert error.value.params["thickness"] == "22"


def test_refus_pieces_pas_d_equerre() -> None:
    refused((stile(), block((600.0, 60.0, 22.0), (330.0, -270.0, 0.0), 45.0)), "d'équerre")
