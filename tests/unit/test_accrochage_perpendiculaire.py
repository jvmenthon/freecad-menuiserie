# SPDX-License-Identifier: LGPL-2.1-or-later
"""Pièce créée perpendiculairement à la face d'une autre pièce (#136) : géométrie pure."""

from __future__ import annotations

import pytest

from freecad.menuiserie.core.geometry import Matrix3, Vec3
from freecad.menuiserie.core.part_model import Dimensions
from freecad.menuiserie.core.snap import (
    FaceTarget,
    Frame,
    Orientation,
    along_edge,
    face_section,
    footprint,
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
    assert section_against(narrow(Z, X, Y, (300.0, 300.0))) == (100.0, 30.0)


def test_largeur_non_parallele_limitee_a_la_place_disponible() -> None:
    # chant dont l'étendue selon la largeur de la nouvelle pièce n'est que de 60 : pas de débord
    assert section_against(narrow(Z, X, Y, (300.0, 60.0))) == (60.0, 30.0)


def test_epaisseur_limitee_a_la_place_disponible_sur_la_face() -> None:
    # chant de 20 seulement dans le sens de l'épaisseur : la pièce ne dépasse pas de l'arête
    assert section_against(narrow(Z, X, Y, (20.0, 300.0))) == (100.0, 20.0)


def test_section_piece_tournee_d_un_quart_de_tour() -> None:
    # pièce tournée de 90° autour de Z : la face +Y est son extrémité, largeur de la pièce selon -X
    quarter: Matrix3 = ((0.0, -1.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0))
    assert section_against(narrow(Z, X, Y, (40.0, 70.0)), quarter) == (70.0, 30.0)


def test_section_piece_oblique_garde_la_section_de_la_piece() -> None:
    oblique: Matrix3 = ((0.9, -0.43, 0.0), (0.43, 0.9, 0.0), (0.0, 0.0, 1.0))
    orientation = perpendicular_orientation(IDENTITY, IDENTITY)
    assert orientation is not None
    section = face_section(IDENTITY, oblique, orientation, (40.0, 60.0), (100.0, 30.0))
    assert section == (100.0, 30.0)


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


def test_emprise_de_la_piece_selon_les_axes_de_la_face() -> None:
    # grande face (normale Z) : la largeur reste selon Y, l'épaisseur selon X
    target = narrow(X, Y, Z, (300.0, 60.0))
    support = support_rotation([target])
    assert support is not None
    orientation = perpendicular_orientation(support, IDENTITY)
    assert orientation is not None
    assert footprint(orientation, (60.0, 30.0)) == (30.0, 60.0)


def orientation_against(
    target: FaceTarget, owner: Matrix3 = IDENTITY
) -> tuple[Matrix3, Orientation]:
    support = support_rotation([target])
    assert support is not None
    orientation = perpendicular_orientation(support, owner)
    assert orientation is not None
    return support, orientation


def test_emprise_contre_une_extremite_la_longueur_est_dans_la_face() -> None:
    # bout (normale X) : largeur selon Y, longueur selon Z (dans la face : emprise nulle), épaisseur
    # sur la normale
    _support, orientation = orientation_against(narrow(Y, Z, X, (100.0, 30.0)))
    assert footprint(orientation, (60.0, 20.0)) == (60.0, 0.0)


def test_emprise_contre_un_chant() -> None:
    # chant (normale Y) : l'épaisseur reste selon Z (ligne 0 du repère d'appui), la largeur selon X
    _support, orientation = orientation_against(narrow(Z, X, Y, (30.0, 800.0)))
    assert footprint(orientation, (60.0, 20.0)) == (20.0, 60.0)


def test_emprise_ne_depend_pas_du_sens_de_la_normale() -> None:
    plus = orientation_against(narrow(X, Y, Z, (300.0, 60.0)))[1]
    minus = orientation_against(narrow(X, Vec3(0, -1, 0), Vec3(0, 0, -1), (300.0, 60.0)))[1]
    assert footprint(plus, (60.0, 20.0)) == footprint(minus, (60.0, 20.0))


def test_emprise_section_nulle() -> None:
    _support, orientation = orientation_against(narrow(X, Y, Z, (300.0, 60.0)))
    assert footprint(orientation, (0.0, 0.0)) == (0.0, 0.0)


@pytest.mark.parametrize(
    "target",
    [
        narrow(X, Y, Z, (300.0, 60.0)),
        narrow(Y, Z, X, (60.0, 30.0)),
        narrow(Z, X, Y, (30.0, 300.0)),
    ],
)
@pytest.mark.parametrize(
    "quarter",
    [
        ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
        ((0.0, -1.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0)),
        ((-1.0, 0.0, 0.0), (0.0, -1.0, 0.0), (0.0, 0.0, 1.0)),
        ((0.0, 0.0, 1.0), (0.0, 1.0, 0.0), (-1.0, 0.0, 0.0)),
    ],
)
def test_section_calee_tient_dans_l_etendue_utilisable(
    target: FaceTarget, quarter: Matrix3
) -> None:
    """Quelle que soit la face et la rotation de la pièce qui la porte, une fois la section limitée
    à l'étendue de la face, l'emprise de la nouvelle pièce ne la dépasse sur aucun axe."""
    support, orientation = orientation_against(target, quarter)
    section = face_section(support, quarter, orientation, target.extent, (100.0, 30.0))
    sizes = footprint(orientation, section)
    assert all(size <= extent + 1e-9 for size, extent in zip(sizes, target.extent, strict=True))


def test_largeur_tournee_pour_suivre_l_arete_la_plus_proche() -> None:
    # grande face : la largeur suit Y ; l'arête la plus proche suit X -> quart de tour autour de Z
    target = narrow(X, Y, Z, (300.0, 60.0))
    support = support_rotation([target])
    assert support is not None
    orientation = perpendicular_orientation(support, IDENTITY)
    assert orientation is not None
    turned = along_edge(orientation, 0)
    width = Vec3(*(row[1] for row in turned.rotation()))
    length = Vec3(*(row[0] for row in turned.rotation()))
    assert abs(width.x) == 1.0
    assert length == Z
    assert along_edge(orientation, 1) == orientation
    assert face_section(support, IDENTITY, turned, (300.0, 60.0), (100.0, 30.0), 0) == (300.0, 30.0)


def test_extremite_jamais_tournee() -> None:
    # contre une extrémité, la pièce est couchée : pas de quart de tour pour suivre une arête
    target = narrow(Y, Z, X, (100.0, 30.0))
    support = support_rotation([target])
    assert support is not None
    orientation = perpendicular_orientation(support, IDENTITY)
    assert orientation is not None
    assert along_edge(orientation, 0) == orientation
    assert along_edge(orientation, 1) == orientation


def test_along_edge_idempotent_et_quart_de_tour_sur_les_deux_lignes() -> None:
    target = narrow(X, Y, Z, (300.0, 60.0))
    _support, orientation = orientation_against(target)
    turned = along_edge(orientation, 0)
    assert turned != orientation
    assert along_edge(turned, 0) == turned  # déjà le long de l'arête 0
    back = along_edge(turned, 1)  # second quart de tour : la largeur suit de nouveau Y
    assert abs(Vec3(*(r[1] for r in back.rotation())).y) == 1.0
    assert along_edge(orientation, 1) == orientation


@pytest.mark.parametrize("row", [0, 1])
def test_along_edge_sur_chant_la_largeur_suit_l_arete_demandee(row: int) -> None:
    # chant (normale Y), repère (Z, X) : la largeur suit toujours l'axe d'appui demandé
    _support, orientation = orientation_against(narrow(Z, X, Y, (30.0, 800.0)))
    width = Vec3(*(r[1] for r in along_edge(orientation, row).rotation()))
    assert abs(width.component(row)) == 1.0  # l'orientation est exprimée dans le repère d'appui


def test_section_largeur_suivant_l_arete_prend_toute_la_longueur_de_l_arete() -> None:
    # pièce porteuse tournée de 90° : la largeur suit l'arête demandée, la longueur de l'arête
    quarter: Matrix3 = ((0.0, -1.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0))
    target = narrow(X, Y, Z, (300.0, 60.0))
    support, orientation = orientation_against(target, quarter)
    for row, expected in ((0, 300.0), (1, 60.0)):
        turned = along_edge(orientation, row)
        assert face_section(support, quarter, turned, target.extent, (100.0, 30.0), row) == (
            expected,
            30.0,
        )


def test_section_arete_hors_bornes_garde_la_largeur() -> None:
    # arête de 0,05 mm (pointe) : ignorée, la largeur de la pièce est gardée
    target = narrow(X, Y, Z, (0.05, 60.0))
    support, orientation = orientation_against(target)
    turned = along_edge(orientation, 0)
    assert face_section(support, IDENTITY, turned, target.extent, (100.0, 30.0), 0)[0] == 100.0
