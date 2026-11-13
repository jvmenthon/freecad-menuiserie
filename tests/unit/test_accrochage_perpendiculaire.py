# SPDX-License-Identifier: LGPL-2.1-or-later
"""Pièce créée perpendiculairement à la face d'une autre pièce (#136) : géométrie pure."""

from __future__ import annotations

import pytest

from freecad.menuiserie.core.geometry import Matrix3, Vec3
from freecad.menuiserie.core.part_model import Dimensions
from freecad.menuiserie.core.snap import (
    FaceTarget,
    Frame,
    face_section,
    perpendicular_orientation,
    snap,
    support_rotation,
)

X, Y, Z = Vec3(1, 0, 0), Vec3(0, 1, 0), Vec3(0, 0, 1)
MINUS_X = Vec3(-1, 0, 0)
IDENTITY: Matrix3 = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
# Pièce portant la face : 800 x 100 x 30 à l'origine ; la nouvelle a 500 de long, même section.
NEW = Dimensions(500, 100, 30)


def face(origin: Vec3, x: Vec3, y: Vec3, normal: Vec3) -> FaceTarget:
    return FaceTarget("Face", Frame(origin, x, y, normal), (100.0, 30.0), planar=True)


def occupied(target: FaceTarget, owner: Matrix3 = IDENTITY) -> tuple[Vec3, Vec3]:
    """Boîte (minimum, maximum) occupée par la nouvelle pièce posée contre ``target``."""
    support = support_rotation([target])
    assert support is not None
    orientation = perpendicular_orientation(support, owner)
    assert orientation is not None
    placement = snap(NEW, orientation, [target]).placement
    corners = [
        placement.apply(Vec3(a * 500, b * 100, c * 30))
        for a in (0, 1)
        for b in (0, 1)
        for c in (0, 1)
    ]
    low = Vec3(*(min(c.component(i) for c in corners) for i in range(3)))
    high = Vec3(*(max(c.component(i) for c in corners) for i in range(3)))
    return low, high


def test_extremite_angle_droit_avec_la_piece() -> None:
    """Contre l'extrémité (x = 800), la pièce est perpendiculaire à l'autre : sa longueur suit
    l'épaisseur de l'autre (Z), sa largeur reste selon Y, son épaisseur s'appuie sur la face."""
    low, high = occupied(face(Vec3(800, 0, 0), Y, Z, X))
    assert (high.z - low.z, high.y - low.y, high.x - low.x) == (500, 100, 30)
    assert low.x == 800


def test_grande_face_dresse_la_piece_largeur_parallele() -> None:
    """Sur la grande face (z = 30), la longueur monte, la largeur reste selon Y."""
    low, high = occupied(face(Vec3(0, 0, 30), X, Y, Z))
    assert (high.z - low.z, high.y - low.y, high.x - low.x) == (500, 100, 30)
    assert low.z == 30


def test_chant_epaisseur_parallele() -> None:
    """Sur le chant (y = 100), la longueur part du chant, l'épaisseur reste selon Z."""
    low, high = occupied(face(Vec3(0, 100, 0), Z, X, Y))
    assert (high.y - low.y, high.z - low.z, high.x - low.x) == (500, 30, 100)
    assert low.y == 100


def test_face_orientee_vers_moins_x() -> None:
    """La pièce part toujours du côté sortant de la face."""
    target = face(Vec3(0, 0, 0), Z, Y, MINUS_X)
    low, high = occupied(target)
    assert (low.x, high.x) == (-30, 0)


def test_piece_oblique_donne_la_main_a_l_orientation_habituelle() -> None:
    oblique: Matrix3 = ((0.9, -0.43, 0.0), (0.43, 0.9, 0.0), (0.0, 0.0, 1.0))
    assert perpendicular_orientation(IDENTITY, oblique) is None


@pytest.mark.parametrize("quarter", [((0.0, -1.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0))])
def test_piece_tournee_d_un_quart_de_tour(quarter: Matrix3) -> None:
    """La pièce de départ tournée de 90° autour de Z : la face +Y est son extrémité."""
    target = face(Vec3(0, 800, 0), Z, X, Y)  # normale +Y = longueur de la pièce tournée
    low, high = occupied(target, quarter)
    assert (low.y, high.y) == (800, 830)


def section_against(target: FaceTarget, owner: Matrix3 = IDENTITY) -> tuple[float, float]:
    """Section de la pièce posée contre ``target`` (pièce de 100 x 30 qui porte la face)."""
    support = support_rotation([target])
    assert support is not None
    orientation = perpendicular_orientation(support, owner)
    assert orientation is not None
    return face_section(support, owner, orientation, target.extent, (100.0, 30.0))


def narrow(x: Vec3, y: Vec3, normal: Vec3, extent: tuple[float, float]) -> FaceTarget:
    return FaceTarget("Face", Frame(Vec3(0, 0, 0), x, y, normal), extent, planar=True)


def test_section_d_une_extremite_plus_etroite_que_la_piece() -> None:
    # bout d'une pièce dessinée : 40 selon la largeur (Y) ; l'épaisseur s'appuie sur la face
    assert section_against(narrow(Y, Z, X, (40.0, 30.0))) == (40.0, 30.0)
    assert section_against(narrow(Z, Y, MINUS_X, (30.0, 40.0))) == (40.0, 30.0)


def test_section_contre_une_grande_face_prend_la_largeur_de_la_face() -> None:
    # face de dessus réduite à 300 x 60 : largeur de la face, épaisseur de la pièce
    assert section_against(narrow(X, Y, Z, (300.0, 60.0))) == (60.0, 30.0)


def test_section_contre_un_chant_garde_la_largeur_de_la_piece() -> None:
    # chant : la largeur de la nouvelle pièce suit la longueur de l'autre, elle ne change pas
    assert section_against(narrow(Z, X, Y, (20.0, 300.0))) == (100.0, 30.0)


def test_section_piece_tournee_d_un_quart_de_tour() -> None:
    # pièce tournée de 90° autour de Z : la face +Y est son extrémité, largeur de la pièce selon -X
    quarter: Matrix3 = ((0.0, -1.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0))
    assert section_against(narrow(Z, X, Y, (40.0, 70.0)), quarter) == (70.0, 30.0)


def test_section_piece_oblique_garde_la_section_de_la_piece() -> None:
    oblique: Matrix3 = ((0.9, -0.43, 0.0), (0.43, 0.9, 0.0), (0.0, 0.0, 1.0))
    assert face_section(
        IDENTITY,
        oblique,
        perpendicular_orientation(IDENTITY, IDENTITY),
        (40.0, 60.0),
        (100.0, 30.0),
    ) == (100.0, 30.0)  # type: ignore[arg-type]


@pytest.mark.parametrize("extent", [(0.0, 0.0), (-5.0, -5.0), (0.0, 60.0)])
def test_etendue_nulle_ou_negative_refusee_par_la_cible(extent: tuple[float, float]) -> None:
    with pytest.raises(ValueError, match="étendue"):
        narrow(X, Y, Z, extent)


def test_section_face_non_rectangulaire_tranche_etroite() -> None:
    # triangle : à l'endroit du clic la tranche ne fait que 0,05 mm, sous la cote minimale (0,1)
    # DÉFAUT : face_section renvoie 0,05 et make_wood_part lève InvalidDimensionsError
    width, _thickness = section_against(narrow(X, Y, Z, (300.0, 0.05)))
    assert width >= 0.1


def test_section_tres_grande_etendue_reste_dans_les_bornes() -> None:
    # face de 1e6 mm : au-delà de MAX_DIMENSION_MM la largeur doit retomber sur celle de la pièce
    width, _thickness = section_against(narrow(X, Y, Z, (300.0, 1.0e6)))
    assert width <= 20000.0
