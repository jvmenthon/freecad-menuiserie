# SPDX-License-Identifier: LGPL-2.1-or-later
"""Orientation de départ et rotation autour des axes du document (J6d) : géométrie pure."""

from __future__ import annotations

import math

import pytest

from freecad.menuiserie.core.geometry import RigidTransform, Vec3, squared_rotation
from freecad.menuiserie.core.part_model import Dimensions
from freecad.menuiserie.core.snap import (
    EdgeTarget,
    FaceTarget,
    Frame,
    Orientation,
    SnapNoticeKind,
    Turn,
    all_orientations,
    initial_orientation,
    snap,
    source_orientation,
    support_rotation,
)

X, Y, Z = Vec3(1, 0, 0), Vec3(0, 1, 0), Vec3(0, 0, 1)
DIMS = Dimensions(800, 200, 22)
ZERO = Vec3(0, 0, 0)


def frame_of(origin: Vec3, x: Vec3, z: Vec3) -> Frame:
    y = Vec3(z.y * x.z - z.z * x.y, z.z * x.x - z.x * x.z, z.x * x.y - z.y * x.x)
    return Frame(origin, x, y, z)


def cheek(x: float, outward: float, long_axis: Vec3 = Y) -> FaceTarget:
    """Face verticale d'une joue en ``x``, de normale sortante ``outward`` (±X), 560 x 700."""
    z = Vec3(outward, 0, 0)
    return FaceTarget("joue", frame_of(Vec3(x, 0, 0), long_axis, z), (560, 700), planar=True)


def box_of(placement: RigidTransform, dims: Dimensions) -> tuple[tuple[float, float], ...]:
    corners = [
        placement.apply(Vec3(i * dims.length, j * dims.width, k * dims.thickness))
        for i in (0, 1)
        for j in (0, 1)
        for k in (0, 1)
    ]
    return tuple(
        (
            round(min(c.component(a) for c in corners), 6),
            round(max(c.component(a) for c in corners), 6),
        )
        for a in range(3)
    )


def test_vingt_quatre_orientations_distinctes_dans_un_ordre_stable() -> None:
    found = all_orientations()
    assert len(found) == len(set(found)) == 24
    assert found[0] == Orientation()
    assert found == all_orientations()


def test_appui_d_equerre_les_boutons_tournent_autour_des_axes_du_document() -> None:
    """Face de normale -Y dont le repère est permuté : le bouton X tourne autour de X global."""
    frame = frame_of(ZERO, Z, Vec3(0, -1, 0))
    support = frame.to_transform().rotation
    for turn in Turn:
        turned = Orientation().turned(turn, support)
        in_document = RigidTransform(support, ZERO).compose(RigidTransform(turned.matrix, ZERO))
        local_x = in_document.rotate(X)
        expected = RigidTransform(turn.matrix, ZERO).compose(RigidTransform(support, ZERO))
        assert local_x == expected.rotate(X)


@pytest.mark.parametrize("turn", list(Turn))
def test_quatre_clics_ramenent_au_depart_avec_un_appui_permute(turn: Turn) -> None:
    support = frame_of(ZERO, Z, Vec3(0, -1, 0)).to_transform().rotation
    orientation = Orientation()
    for _ in range(4):
        orientation = orientation.turned(turn, support)
    assert orientation == Orientation()


def test_appui_incline_tourne_autour_des_axes_du_repere_d_appui() -> None:
    """Limite documentée : face à 30°, le quart de tour se fait autour de l'axe du repère."""
    c, s = math.cos(math.radians(30)), math.sin(math.radians(30))
    frame = Frame(ZERO, X, Vec3(0, c, s), Vec3(0, -s, c))
    support = frame.to_transform().rotation
    for turn in Turn:
        assert Orientation().turned(turn, support) == Orientation().turned(turn)


def test_sans_appui_comme_avant() -> None:
    assert support_rotation(()) is None
    assert Orientation().turned(Turn.Y, None) == Orientation().turned(Turn.Y)


def test_tablette_entre_deux_joues_est_etiree_en_longueur() -> None:
    targets = (cheek(22, 1), cheek(578, -1))
    flat = snap(DIMS, Orientation(), targets)
    assert [n.kind for n in flat.notices] == [SnapNoticeKind.THICKNESS_GAP]
    orientation = initial_orientation(DIMS, targets)
    assert orientation != Orientation()
    result = snap(DIMS, orientation, targets)
    assert result.notices == ()
    assert result.dimensions == Dimensions(556, 200, 22)
    assert result.used == ("joue", "joue")
    (x, y, z) = box_of(result.placement, result.dimensions)
    assert x == (22, 578)
    assert z[1] - z[0] == 22  # l'épaisseur reste verticale : tablette à l'horizontale
    assert y[1] - y[0] == 200


def test_orientation_stable_quel_que_soit_le_cote_du_clic() -> None:
    for targets in (
        (cheek(22, 1), cheek(578, -1)),
        (cheek(578, -1), cheek(22, 1)),
        (cheek(22, 1, Z), cheek(578, -1, Z)),
    ):
        result = snap(DIMS, initial_orientation(DIMS, targets), targets)
        assert result.dimensions.length == 556
        assert result.notices == ()
        z = box_of(result.placement, result.dimensions)[2]
        assert z[1] - z[0] == 22


def test_orientation_a_plat_conservee_sans_vis_a_vis() -> None:
    assert initial_orientation(DIMS, ()) == Orientation()
    assert initial_orientation(DIMS, (cheek(22, 1),)) == Orientation()
    side = FaceTarget("fond", frame_of(Vec3(0, 300, 0), X, Y), (600, 300), planar=True)
    assert initial_orientation(DIMS, (cheek(22, 1), side)) == Orientation()


def test_ecart_egal_a_l_epaisseur_garde_la_pose_a_plat() -> None:
    targets = (cheek(22, 1), cheek(44, -1))
    assert initial_orientation(DIMS, targets) == Orientation()


# --- Arête seule : la pièce reprend la rotation de l'objet source (demande de jv) ---------------

WORLD = Frame(ZERO, X, Y, Z)


def edge_along_y(axes: Frame | None) -> EdgeTarget:
    """Arête du dessus d'une planche, le long de Y, face d'appui vers +Z."""
    return EdgeTarget("arête", Vec3(0, 0, 22), Vec3(0, 500, 22), Z, Vec3(1, 0, 0), axes)


def test_arete_seule_garde_la_rotation_de_l_objet_source() -> None:
    target = edge_along_y(WORLD)
    result = snap(DIMS, initial_orientation(DIMS, [target]), [target])
    assert squared_rotation(result.placement.rotation) == ((1, 0, 0), (0, 1, 0), (0, 0, 1))


def test_arete_d_un_objet_tourne_suit_sa_rotation() -> None:
    turned = Frame(ZERO, Y, Vec3(-1, 0, 0), Z)  # objet tourné d'un quart de tour autour de Z
    target = edge_along_y(turned)
    result = snap(DIMS, initial_orientation(DIMS, [target]), [target])
    assert squared_rotation(result.placement.rotation) == ((0, -1, 0), (1, 0, 0), (0, 0, 1))


def test_arete_sans_axes_ou_oblique_reste_a_plat() -> None:
    assert source_orientation([edge_along_y(None)]) == Orientation()
    half = math.sqrt(0.5)
    oblique = Frame(ZERO, Vec3(half, half, 0), Vec3(-half, half, 0), Z)
    assert source_orientation([edge_along_y(oblique)]) == Orientation()
