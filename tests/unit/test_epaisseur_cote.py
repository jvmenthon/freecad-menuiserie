# SPDX-License-Identifier: LGPL-2.1-or-later
"""Côté où ajouter l'épaisseur d'une pièce assemblée (ADR 0060) : géométrie pure.

Angle à queue d'aronde : H à plat (400 x 150 x 18) à l'origine, I debout (sa longueur selon +Z),
son épaisseur vers -X depuis x = 18 : sa face haute est la face extérieure, en x = 0, à fleur du
bout de H.
"""

from __future__ import annotations

import pytest

from freecad.menuiserie.core.geometry import Matrix3, PlacedBlock, RigidTransform, Vec3
from freecad.menuiserie.core.part_model import Dimensions
from freecad.menuiserie.core.thickness_follow import touches_raised_face
from freecad.menuiserie.core.thickness_side import (
    Extension,
    flush_extension,
    grows_toward,
    other_side_shift,
)

IDENTITY: Matrix3 = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
UPRIGHT: Matrix3 = ((0.0, 0.0, -1.0), (0.0, 1.0, 0.0), (1.0, 0.0, 0.0))
OBLIQUE: Matrix3 = ((0.9, -0.43, 0.0), (0.43, 0.9, 0.0), (0.0, 0.0, 1.0))
SIZE = Dimensions(400, 150, 18)
STANDING = PlacedBlock(SIZE, RigidTransform(UPRIGHT, Vec3(18, 0, 18)))


def flat(at: Vec3, rotation: Matrix3 = IDENTITY) -> PlacedBlock:
    return PlacedBlock(SIZE, RigidTransform(rotation, at))


def test_piece_a_fleur_de_la_face_haute_prolongee_par_son_debut() -> None:
    assert flush_extension(STANDING, flat(Vec3(0, 0, 0))) == Extension(0, at_end=False)


def test_piece_a_fleur_par_son_bout_de_fin() -> None:
    turned: Matrix3 = ((-1.0, 0.0, 0.0), (0.0, -1.0, 0.0), (0.0, 0.0, 1.0))  # longueur vers -X
    assert flush_extension(STANDING, flat(Vec3(400, 150, 0), turned)) == Extension(0, True)


def test_piece_qui_depasse_ou_s_arrete_avant_n_est_pas_prolongee() -> None:
    assert flush_extension(STANDING, flat(Vec3(-5, 0, 0))) is None
    assert flush_extension(STANDING, flat(Vec3(5, 0, 0))) is None


def test_piece_posee_sur_la_face_ou_oblique_n_est_pas_prolongee() -> None:
    assert flush_extension(STANDING, flat(Vec3(-400, 0, 100))) is None
    assert flush_extension(STANDING, flat(Vec3(0, 0, 0), OBLIQUE)) is None


def test_face_basse() -> None:
    through = flat(Vec3(-382, 0, 0))  # traverse I, bout de fin à fleur de sa face basse (x = 18)
    assert flush_extension(STANDING, through, lowered=True) == Extension(0, at_end=True)
    assert flush_extension(STANDING, flat(Vec3(0, 0, 0)), lowered=True) is None


def test_origine_reculee_seulement_par_le_bout_de_debut() -> None:
    assert Extension(0, at_end=False).origin_shift(12) == Vec3(-12, 0, 0)
    assert Extension(1, at_end=True).origin_shift(12) == Vec3(0, 0, 0)


def test_vers_l_interieur_est_du_cote_de_l_autre_piece() -> None:
    assert grows_toward(STANDING, flat(Vec3(0, 0, 0)))
    assert not grows_toward(STANDING, flat(Vec3(-400, 0, 0)))
    assert not grows_toward(STANDING, flat(Vec3(0, 0, 0), OBLIQUE))


def test_l_autre_cote_garde_la_face_haute() -> None:
    shift = other_side_shift(STANDING, 12)
    assert (shift.x, shift.y, shift.z) == pytest.approx((12, 0, 0))


def test_piece_contre_la_face_basse() -> None:
    against = PlacedBlock(Dimensions(150, 150, 18), RigidTransform(IDENTITY, Vec3(18, 0, 200)))
    assert touches_raised_face(STANDING, against, lowered=True)
    assert not touches_raised_face(STANDING, against)
