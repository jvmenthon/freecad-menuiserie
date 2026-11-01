# SPDX-License-Identifier: LGPL-2.1-or-later
"""Pièces posées sur la face haute d'une pièce dont l'épaisseur change (#133) : géométrie pure."""

from __future__ import annotations

from freecad.menuiserie.core.geometry import Matrix3, PlacedBlock, RigidTransform, Vec3
from freecad.menuiserie.core.part_model import Dimensions
from freecad.menuiserie.core.thickness_follow import follow_shift, touches_raised_face

IDENTITY: Matrix3 = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
UPRIGHT: Matrix3 = ((0.0, 0.0, -1.0), (0.0, 1.0, 0.0), (1.0, 0.0, 0.0))  # longueur selon +Z
FLAT_TURNED: Matrix3 = ((0.0, -1.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0))  # tourné de 90° sur Z
HOST = PlacedBlock(Dimensions(600, 100, 30), RigidTransform(IDENTITY, Vec3(0, 0, 0)))


def block(rotation: Matrix3, at: Vec3) -> PlacedBlock:
    return PlacedBlock(Dimensions(400, 100, 30), RigidTransform(rotation, at))


def test_piece_posee_sur_la_face_haute_suit() -> None:
    assert touches_raised_face(HOST, block(UPRIGHT, Vec3(300, 0, 30)))


def test_piece_sous_la_face_basse_ne_suit_pas() -> None:
    assert not touches_raised_face(HOST, block(UPRIGHT, Vec3(300, 0, -400)))


def test_piece_contre_un_chant_ne_suit_pas() -> None:
    assert not touches_raised_face(HOST, block(FLAT_TURNED, Vec3(400, 100, 0)))


def test_piece_ecartee_ou_sans_recouvrement_ne_suit_pas() -> None:
    assert not touches_raised_face(HOST, block(UPRIGHT, Vec3(300, 0, 60)))
    assert not touches_raised_face(HOST, block(UPRIGHT, Vec3(700, 0, 30)))


def test_piece_oblique_ne_suit_pas() -> None:
    oblique: Matrix3 = ((0.9, -0.43, 0.0), (0.43, 0.9, 0.0), (0.0, 0.0, 1.0))
    assert not touches_raised_face(HOST, block(oblique, Vec3(300, 0, 30)))


def test_ecart_le_long_de_l_epaisseur_de_la_piece_tournee() -> None:
    """La translation suit l'épaisseur de la pièce modifiée, pas l'axe Z du document."""
    on_edge = PlacedBlock(Dimensions(600, 100, 30), RigidTransform(UPRIGHT, Vec3(0, 0, 0)))
    assert follow_shift(on_edge, -8.0) == Vec3(8.0, 0.0, 0.0)
    assert follow_shift(HOST, -8.0) == Vec3(0.0, 0.0, -8.0)
