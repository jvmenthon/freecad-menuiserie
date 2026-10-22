# SPDX-License-Identifier: LGPL-2.1-or-later
"""Accrochage de la nouvelle pièce (J6a, critères S1 à S11) : géométrie pure, sans FreeCAD."""

from __future__ import annotations

import itertools
import math
import random
from pathlib import Path

import pytest

from freecad.menuiserie.core.geometry import RigidTransform, Vec3
from freecad.menuiserie.core.part_model import Dimensions
from freecad.menuiserie.core.snap import (
    MAX_TARGETS,
    EdgeTarget,
    FaceTarget,
    Frame,
    Orientation,
    SnapNoticeKind,
    SnapResult,
    Target,
    Turn,
    VertexTarget,
    snap,
    tangent_frame,
    turned_in_place,
)
from tests.unit.aides import ROOT, imported_modules

X, Y, Z = Vec3(1, 0, 0), Vec3(0, 1, 0), Vec3(0, 0, 1)
NEG_X, NEG_Y, NEG_Z = Vec3(-1, 0, 0), Vec3(0, -1, 0), Vec3(0, 0, -1)
DIMS = Dimensions(800, 200, 22)
Box = tuple[tuple[float, float], tuple[float, float], tuple[float, float]]
SNAP_PACKAGE = ROOT / "freecad" / "menuiserie" / "core" / "snap"


def frame_of(origin: Vec3, x: Vec3, z: Vec3) -> Frame:
    """Repère direct d'origine, d'axe x et de normale z donnés (y = z ∧ x)."""
    y = Vec3(z.y * x.z - z.z * x.y, z.z * x.x - z.x * x.z, z.x * x.y - z.y * x.x)
    return Frame(origin, x, y, z)


def face(
    name: str, origin: Vec3, x: Vec3, z: Vec3, extent: tuple[float, float] = (600, 300)
) -> FaceTarget:
    return FaceTarget(name, frame_of(origin, x, z), extent, planar=True)


def top(z: float = 100.0) -> FaceTarget:
    """Dessus d'un bloc 600 x 300, coin le plus proche du clic en (0, 0, z)."""
    return face("dessus", Vec3(0, 0, z), X, Z)


def wall(name: str, x: float, outward: float) -> FaceTarget:
    """Face verticale perpendiculaire à X, en x, de normale sortante ±X (bord y = 0, z = 0)."""
    normal = X if outward > 0 else NEG_X
    return face(name, Vec3(x, 0, 0), Y, normal, (300, 500))


def side(name: str, y: float, outward: float) -> FaceTarget:
    """Face verticale perpendiculaire à Y, en y, de normale sortante ±Y."""
    normal = Y if outward > 0 else NEG_Y
    return face(name, Vec3(0, y, 0), NEG_X if outward > 0 else X, normal, (300, 500))


def box_from(placement: RigidTransform, size: Dimensions) -> Box:
    """Boîte globale de la pièce (rotation d'équerre)."""
    corners = [
        placement.apply(Vec3(a, b, c))
        for a, b, c in itertools.product((0, size.length), (0, size.width), (0, size.thickness))
    ]
    ranges = [
        (min(p.component(i) for p in corners), max(p.component(i) for p in corners))
        for i in range(3)
    ]
    return (ranges[0], ranges[1], ranges[2])


def box_of(result: SnapResult) -> Box:
    return box_from(result.placement, result.dimensions)


def assert_vec(got: Vec3, want: Vec3) -> None:
    assert (got.x, got.y, got.z) == pytest.approx((want.x, want.y, want.z), abs=1e-9)


def assert_box(result: SnapResult, expected: Box) -> None:
    for got, want in zip(box_of(result), expected, strict=True):
        assert got == pytest.approx(want, abs=1e-6)


def kinds(result: SnapResult) -> list[SnapNoticeKind]:
    return [notice.kind for notice in result.notices]


def snapped(
    *targets: Target, orientation: Orientation | None = None, stretch: bool = True
) -> SnapResult:
    return snap(DIMS, orientation or Orientation(), targets, stretch=stretch)


# --- S1 : objets valeur -------------------------------------------------------------------


def test_repere_valide_et_renormalise() -> None:
    frame = Frame(Vec3(1, 2, 3), Vec3(1 + 1e-9, 0, 0), Y, Z)
    assert frame.x == Vec3(1, 0, 0)
    assert frame.z == Z
    assert frame.to_transform().apply(Vec3(1, 1, 1)) == Vec3(2, 3, 4)


@pytest.mark.parametrize(
    ("origin", "x", "y", "z", "field"),
    [
        (Vec3(math.nan, 0, 0), X, Y, Z, "origin"),
        (Vec3(0, 0, 0), Vec3(2, 0, 0), Y, Z, "x"),
        (Vec3(0, 0, 0), X, Y, Vec3(0.6, 0, 0.8), "orthogonaux"),
        (Vec3(0, 0, 0), X, Y, NEG_Z, "z"),
    ],
)
def test_repere_refuse(origin: Vec3, x: Vec3, y: Vec3, z: Vec3, field: str) -> None:
    with pytest.raises(ValueError, match=field):
        Frame(origin, x, y, z)


def test_face_validation() -> None:
    frame = frame_of(Vec3(0, 0, 0), X, Z)
    assert FaceTarget("cylindre", frame, (0, 0), planar=False).extent == (0, 0)
    for extent, planar in (((-1, 5), False), ((0, 0), True), ((math.inf, 1), False)):
        with pytest.raises(ValueError, match="extent"):
            FaceTarget("f", frame, extent, planar=planar)
    with pytest.raises(ValueError, match="name"):
        FaceTarget(" ", frame, (1, 1), planar=True)


def test_arete_validation() -> None:
    assert EdgeTarget("a", Vec3(0, 0, 0), Vec3(0.011, 0, 0), Z, Y).support == Z
    cases = {
        "end": (Vec3(0, 0, 0), Vec3(0.005, 0, 0), Z, Y),
        "support": (Vec3(0, 0, 0), Vec3(5, 0, 0), X, Y),
        "inward": (Vec3(0, 0, 0), Vec3(5, 0, 0), Z, Vec3(0.6, 0.8, 0)),
    }
    for field, (start, end, support, inward) in cases.items():
        with pytest.raises(ValueError, match=field):
            EdgeTarget("a", start, end, support, inward)
    with pytest.raises(ValueError, match="inward"):
        EdgeTarget("a", Vec3(0, 0, 0), Vec3(5, 0, 0), Z, Vec3(0, 0, 2))


def test_sommet_validation() -> None:
    axes = frame_of(Vec3(9, 9, 9), X, Z)
    assert VertexTarget("s", Vec3(0, 0, 0), axes).point == Vec3(0, 0, 0)
    with pytest.raises(ValueError, match="point"):
        VertexTarget("s", Vec3(0, math.inf, 0), axes)


def test_orientation_validation() -> None:
    assert Orientation(tilt=2, pivot=3).pivot == 3
    refused = ((3, 0, "tilt"), (0, 4, "pivot"), (-1, 0, "tilt"), (0, True, "pivot"))
    for tilt, pivot, field in refused:
        with pytest.raises(ValueError, match=field):
            Orientation(tilt, pivot)


# --- S2 : sans élément --------------------------------------------------------------------


def test_sans_element_identite() -> None:
    result = snap(DIMS, Orientation(), ())
    assert result.placement == RigidTransform.identity()
    assert (result.dimensions, result.used, result.notices) == (DIMS, (), ())


@pytest.mark.parametrize("tilt", range(3))
@pytest.mark.parametrize("pivot", range(4))
def test_sans_element_octant_positif(tilt: int, pivot: int) -> None:
    result = snap(DIMS, Orientation(tilt, pivot), ())
    assert [low for low, _ in box_of(result)] == pytest.approx([0, 0, 0])
    assert sorted(high for _, high in box_of(result)) == pytest.approx([22, 200, 800])


# --- S3 / S4 : une face -------------------------------------------------------------------


def test_face_plane_a_plat() -> None:
    result = snapped(top())
    assert_box(result, ((0, 800), (0, 200), (100, 122)))
    assert result.used == ("dessus",)
    assert result.notices == ()


def test_face_verticale() -> None:
    target = face("avant", Vec3(0, 0, 50), X, NEG_Y)
    assert_box(snapped(target), ((0, 800), (-22, 0), (50, 250)))


def test_face_inclinee_a_30_degres() -> None:
    normal = Vec3(0, -math.sin(math.radians(30)), math.cos(math.radians(30)))
    target = face("pente", Vec3(0, 0, 0), X, normal)
    result = snapped(target)
    expected = target.frame.to_transform()
    for row, wanted in zip(result.placement.rotation, expected.rotation, strict=True):
        assert row == pytest.approx(wanted)
    assert result.placement.rotate(Z).z == pytest.approx(math.cos(math.radians(30)))
    assert_vec(result.placement.translation, Vec3(0, 0, 0))


def test_face_non_plane_repere_tangent() -> None:
    point = Vec3(10, 20, 30)
    frame = tangent_frame(point, Vec3(0, 0, 1))
    assert (frame.x, frame.z) == (X, Z)
    target = FaceTarget("cylindre", tangent_frame(point, Vec3(0, 0, 2)), (0, 0), planar=False)
    assert_box(snapped(target), ((10, 810), (20, 220), (30, 52)))


def test_repere_tangent_projette_x_ou_y() -> None:
    oblique = tangent_frame(Vec3(0, 0, 0), Vec3(0, 1, 1))
    assert oblique.x == X
    assert oblique.z.y == pytest.approx(math.sqrt(0.5))
    normal_to_x = tangent_frame(Vec3(0, 0, 0), Vec3(1, 0, 0))
    assert normal_to_x.x == Y
    along_x_slope = tangent_frame(Vec3(0, 0, 0), Vec3(1, 0, 1))
    assert along_x_slope.x.z == pytest.approx(-math.sqrt(0.5))


# --- S5 : une arête -----------------------------------------------------------------------


def test_arete_droite_a_plat_sur_la_face() -> None:
    edge = EdgeTarget("arête", Vec3(0, 0, 0), Vec3(600, 0, 0), Z, Y)
    assert_box(snapped(edge), ((0, 800), (0, 200), (0, 22)))


def test_arete_depuis_l_extremite_la_plus_proche() -> None:
    edge = EdgeTarget("arête", Vec3(600, 0, 0), Vec3(0, 0, 0), Z, Y)
    assert_box(snapped(edge), ((-200, 600), (0, 200), (0, 22)))


def test_arete_face_d_appui_de_l_autre_cote() -> None:
    edge = EdgeTarget("arête", Vec3(0, 0, 0), Vec3(600, 0, 0), Z, NEG_Y)
    assert_box(snapped(edge), ((0, 800), (-200, 0), (0, 22)))
    vertical = EdgeTarget("chant", Vec3(0, 0, 0), Vec3(600, 0, 0), NEG_Y, Z)
    assert_box(snapped(vertical), ((0, 800), (-22, 0), (0, 200)))


def test_arete_courbe_tangente() -> None:
    edge = EdgeTarget("cercle", Vec3(5, 6, 7), Vec3(5, 7, 7), Z, NEG_X)
    assert_box(snapped(edge), ((-195, 5), (6, 806), (7, 29)))


def test_arete_libre_plan_face_a_l_observateur() -> None:
    edge = EdgeTarget("esquisse", Vec3(0, 0, 0), Vec3(0, 0, 400), NEG_Y, X)
    assert_box(snapped(edge), ((0, 200), (-22, 0), (0, 800)))


# --- S6 : un sommet -----------------------------------------------------------------------


def vertex(axes: Frame | None = None) -> VertexTarget:
    return VertexTarget("coin", Vec3(10, 20, 30), axes or frame_of(Vec3(10, 20, 30), X, Z))


def test_sommet_premier_octant_sans_is_free() -> None:
    assert_box(snapped(vertex()), ((10, 810), (20, 220), (30, 52)))


def test_sommet_axes_de_l_objet() -> None:
    turned = frame_of(Vec3(10, 20, 30), Y, Z)
    assert_box(snapped(vertex(turned)), ((-190, 10), (20, 820), (30, 52)))


def test_sommet_octant_libre() -> None:
    def below(placement: RigidTransform, dimensions: Dimensions) -> bool:
        return box_from(placement, dimensions)[2][1] <= 30 + 1e-9

    result = snap(DIMS, Orientation(), [vertex()], is_free=below)
    assert_box(result, ((10, 810), (20, 220), (8, 30)))


def test_sommet_ordre_des_octants() -> None:
    order: list[tuple[int, int, int]] = []

    def record(placement: RigidTransform, dimensions: Dimensions) -> bool:
        box = box_from(placement, dimensions)
        order.append(tuple(1 if box[i][0] >= (10, 20, 30)[i] - 1e-9 else -1 for i in range(3)))  # type: ignore[arg-type]
        return False

    result = snap(DIMS, Orientation(), [vertex()], is_free=record)
    assert order == [
        (1, 1, 1), (-1, 1, 1), (1, -1, 1), (-1, -1, 1),
        (1, 1, -1), (-1, 1, -1), (1, -1, -1), (-1, -1, -1),
    ]  # fmt: skip
    assert_box(result, ((10, 810), (20, 220), (30, 52)))


def test_sommet_deuxieme_octant() -> None:
    result = snap(DIMS, Orientation(), [vertex()], is_free=lambda t, d: t.translation.x < 10)
    assert_box(result, ((-790, 10), (20, 220), (30, 52)))


# --- S7 : éléments suivants ---------------------------------------------------------------


def test_traverse_puis_joue_touche_par_le_bout() -> None:
    result = snapped(top(), wall("joue", 300, outward=-1))
    assert_box(result, ((-500, 300), (0, 200), (100, 122)))
    assert result.used == ("dessus", "joue")
    result = snapped(top(), wall("joue", 300, outward=1))
    assert_box(result, ((300, 1100), (0, 200), (100, 122)))


def test_face_suivante_selon_y() -> None:
    result = snapped(top(), side("fond", 250, outward=1))
    assert_box(result, ((0, 800), (250, 450), (100, 122)))


def test_arete_et_sommet_suivants() -> None:
    post = EdgeTarget("poteau", Vec3(300, 50, 100), Vec3(300, 50, 200), X, Y)
    assert_box(snapped(top(), post), ((300, 1100), (50, 250), (100, 122)))
    corner = VertexTarget("pointe", Vec3(700, 150, 100), frame_of(Vec3(700, 150, 100), X, Z))
    assert_box(snapped(top(), corner), ((-100, 700), (-50, 150), (100, 122)))


def test_arete_suivante_dans_le_plan_d_appui() -> None:
    along_x = EdgeTarget("ligne", Vec3(0, 190, 100), Vec3(500, 190, 100), Z, NEG_Y)
    assert_box(snapped(top(), along_x), ((0, 800), (-10, 190), (100, 122)))
    far = EdgeTarget("ligne", Vec3(0, 300, 100), Vec3(500, 300, 100), Z, NEG_Y)
    assert_box(snapped(top(), far), ((0, 800), (100, 300), (100, 122)))


def test_ordre_des_suivants_indifferent() -> None:
    followers = [wall("joue", 300, outward=-1), side("fond", 250, outward=1)]
    results = [snapped(top(), *order) for order in itertools.permutations(followers)]
    assert box_of(results[0]) == box_of(results[1])
    assert_box(results[0], ((-500, 300), (250, 450), (100, 122)))


# --- S8 : étirement -----------------------------------------------------------------------


def test_tablette_entre_deux_joues_dessus_d_une_traverse() -> None:
    result = snapped(top(0), wall("gauche", 22, outward=1), wall("droite", 578, outward=-1))
    assert result.dimensions == Dimensions(556, 200, 22)
    assert_box(result, ((22, 578), (0, 200), (0, 22)))
    assert result.notices == ()
    assert result.used == ("dessus", "gauche", "droite")


def test_tablette_etiree_selon_la_largeur() -> None:
    result = snapped(top(0), side("a", 0, outward=1), side("b", 300, outward=-1))
    assert result.dimensions == Dimensions(800, 300, 22)


def test_deux_joues_dont_la_premiere_est_l_appui() -> None:
    left = face("gauche", Vec3(22, 0, 0), Y, X)
    right = face("droite", Vec3(578, 0, 0), Y, NEG_X)
    result = snapped(left, right, orientation=Orientation(tilt=2))
    assert result.dimensions == Dimensions(556, 200, 22)
    assert_box(result, ((22, 578), (0, 200), (0, 22)))
    flat = snapped(left, right)
    assert flat.dimensions == DIMS
    assert kinds(flat) == [SnapNoticeKind.THICKNESS_GAP]
    assert flat.used == ("gauche",)


def test_dessous_d_un_plateau_en_vis_a_vis() -> None:
    plateau = face("plateau", Vec3(0, 0, 180), X, NEG_Z)
    on_edge = snapped(top(0), plateau, orientation=Orientation(tilt=1))
    assert on_edge.dimensions == Dimensions(800, 180, 22)
    assert kinds(snapped(top(0), plateau)) == [SnapNoticeKind.THICKNESS_GAP]


def test_epaisseur_inchangee_si_l_ecart_est_exact() -> None:
    result = snapped(top(0), face("plateau", Vec3(0, 0, 22), X, NEG_Z))
    assert result.notices == ()
    assert result.dimensions == DIMS
    assert result.used == ("dessus", "plateau")


@pytest.mark.parametrize(("right", "low"), [(22.05, 22), (22, 578), (30000, 22)])
def test_ecart_hors_bornes(right: float, low: float) -> None:
    result = snapped(top(0), wall("a", low, outward=1), wall("b", right, outward=-1))
    assert kinds(result) == [SnapNoticeKind.GAP_OUT_OF_RANGE]
    assert result.dimensions == DIMS
    assert result.used == ("dessus", "a")
    assert result.notices[0].target == "b"


def test_sans_etirement_seule_la_premiere_est_gardee() -> None:
    result = snapped(
        top(0), wall("gauche", 22, outward=1), wall("droite", 578, outward=-1), stretch=False
    )
    assert result.dimensions == DIMS
    assert_box(result, ((22, 822), (0, 200), (0, 22)))
    assert result.used == ("dessus", "gauche")


# --- S9 : refus doux ----------------------------------------------------------------------


def test_face_suivante_non_d_equerre() -> None:
    normal = Vec3(math.cos(math.radians(30)), math.sin(math.radians(30)), 0)
    slanted = face("biaise", Vec3(300, 0, 0), Z, normal)
    result = snapped(top(), slanted)
    assert kinds(result) == [SnapNoticeKind.NOT_SQUARE]
    assert result.notices[0].target == "biaise"
    assert "biaise" in result.notices[0].message
    assert result.used == ("dessus",)
    assert_box(result, ((0, 800), (0, 200), (100, 122)))


def test_arete_suivante_en_diagonale() -> None:
    diagonal = EdgeTarget(
        "diag", Vec3(0, 0, 100), Vec3(100, 100, 100), Z, Vec3(-math.sqrt(0.5), math.sqrt(0.5), 0)
    )
    assert kinds(snapped(top(), diagonal)) == [SnapNoticeKind.NOT_SQUARE]


def test_plus_de_trois_elements() -> None:
    extra = [wall("d", 50, 1), wall("e", 60, 1)]
    result = snapped(top(), wall("joue", 300, -1), side("fond", 250, 1), *extra)
    assert kinds(result) == [SnapNoticeKind.TOO_MANY]
    assert result.notices[0].target == "d"
    assert result.used == ("dessus", "joue", "fond")


def test_conflit_le_dernier_l_emporte() -> None:
    result = snapped(top(), wall("a", 100, 1), wall("b", 200, 1))
    assert kinds(result) == [SnapNoticeKind.CONFLICT]
    assert result.notices[0].target == "b"
    assert_box(result, ((200, 1000), (0, 200), (100, 122)))


def test_conflit_avec_le_plan_d_appui() -> None:
    result = snapped(top(), face("autre", Vec3(0, 0, 500), X, Z))
    assert kinds(result) == [SnapNoticeKind.CONFLICT]
    assert result.used == ("dessus",)
    assert_box(result, ((0, 800), (0, 200), (100, 122)))


def test_notices_traduisibles() -> None:
    result = snapped(top(), wall("a", 22, 1), wall("b", 22.05, -1))
    notice = result.notices[0]
    assert "{target}" in notice.template
    assert notice.params["target"] == "b"
    assert "0.1" in notice.message


def test_jamais_d_exception() -> None:
    rng = random.Random(7)  # noqa: S311
    pool: list[Target] = [
        top(),
        wall("w", 50, -1),
        side("s", 90, 1),
        vertex(),
        EdgeTarget("e", Vec3(0, 0, 0), Vec3(0, 0, 5), X, Y),
    ]
    for _ in range(200):
        chosen = [rng.choice(pool) for _ in range(rng.randint(0, 5))]
        orientation = Orientation(rng.randrange(3), rng.randrange(4))
        result = snap(DIMS, orientation, chosen, stretch=rng.random() < 0.5)
        assert len(result.used) <= MAX_TARGETS


# --- S10 : rotation -----------------------------------------------------------------------


def test_quatre_pivots_et_trois_bascules_ferment_le_cycle() -> None:
    start = Orientation()
    pivoted = start
    for _ in range(4):
        pivoted = pivoted.turned(Turn.PIVOT)
    tilted = start
    for _ in range(3):
        tilted = tilted.turned(Turn.TILT)
    assert pivoted == tilted == start
    assert start.turned(Turn.TILT) == Orientation(tilt=1)
    assert start.turned(Turn.PIVOT) == Orientation(pivot=1)


def test_douze_orientations_distinctes() -> None:
    seen = set()
    orientation = Orientation()
    for _ in range(3):
        for _ in range(4):
            orientation = orientation.turned(Turn.PIVOT)
            seen.add(orientation.rotation())
        orientation = orientation.turned(Turn.TILT)
    assert len(seen) == 12
    for rotation in seen:
        det = (
            rotation[0][0] * (rotation[1][1] * rotation[2][2] - rotation[1][2] * rotation[2][1])
            - rotation[0][1] * (rotation[1][0] * rotation[2][2] - rotation[1][2] * rotation[2][0])
            + rotation[0][2] * (rotation[1][0] * rotation[2][1] - rotation[1][1] * rotation[2][0])
        )
        assert det == 1


@pytest.mark.parametrize("tilt", range(3))
@pytest.mark.parametrize("pivot", range(4))
def test_la_piece_reste_accrochee_apres_rotation(tilt: int, pivot: int) -> None:
    orientation = Orientation(tilt, pivot)
    result = snapped(top(), orientation=orientation)
    ranges = box_of(result)
    assert ranges[2][0] == pytest.approx(100)
    assert (ranges[0][0], ranges[1][0]) == pytest.approx((0, 0))
    heights = {0: 22, 1: 200, 2: 800}
    assert ranges[2][1] - 100 == pytest.approx(heights[tilt])
    with_wall = snapped(top(), wall("joue", 300, 1), orientation=orientation)
    assert box_of(with_wall)[0][0] == pytest.approx(300)
    assert box_of(with_wall)[2][0] == pytest.approx(100)


def test_pivot_echange_longueur_et_largeur() -> None:
    assert_box(snapped(top(), orientation=Orientation(pivot=1)), ((0, 200), (0, 800), (100, 122)))
    assert_box(snapped(top(), orientation=Orientation(tilt=1)), ((0, 22), (0, 800), (100, 300)))
    assert_box(snapped(top(), orientation=Orientation(tilt=2)), ((0, 200), (0, 22), (100, 900)))


def test_etirement_apres_bascule() -> None:
    def between(orientation: Orientation) -> SnapResult:
        return snapped(top(0), wall("a", 22, 1), wall("b", 578, -1), orientation=orientation)

    assert between(Orientation(tilt=2)).dimensions == Dimensions(800, 556, 22)
    assert between(Orientation(pivot=1)).dimensions == Dimensions(800, 556, 22)
    on_edge = between(Orientation(tilt=1))
    assert on_edge.dimensions == DIMS
    assert kinds(on_edge) == [SnapNoticeKind.THICKNESS_GAP]


def placed() -> RigidTransform:
    start = snapped(top(), wall("joue", 300, 1)).placement
    return start.compose(RigidTransform(((0, -1, 0), (1, 0, 0), (0, 0, 1)), Vec3(5, 6, 7)))


@pytest.mark.parametrize("turn", list(Turn))
def test_rotation_sur_place_garde_le_centre(turn: Turn) -> None:
    placement = placed()
    center = Vec3(400, 100, 11)
    turned = turned_in_place(placement, DIMS, turn)
    assert_vec(turned.apply(center), placement.apply(center))
    assert turned.rotation != placement.rotation


def test_rotation_sur_place_cycles_et_sens() -> None:
    placement = placed()
    assert_vec(turned_in_place(placement, DIMS, Turn.PIVOT).rotate(X), placement.rotate(Y))
    for turn, count in ((Turn.PIVOT, 4), (Turn.TILT, 3)):
        current = placement
        for _ in range(count):
            current = turned_in_place(current, DIMS, turn)
        for row, wanted in zip(current.rotation, placement.rotation, strict=True):
            assert row == pytest.approx(wanted)
        assert_vec(current.translation, placement.translation)
    tilt = turned_in_place(RigidTransform.identity(), DIMS, Turn.TILT)
    assert tilt.rotate(Y).z == pytest.approx(1)


# --- S11 : pureté du paquet ---------------------------------------------------------------


def test_paquet_pur_et_court() -> None:
    forbidden = {"FreeCAD", "FreeCADGui", "Part", "PySide", "PySide2", "PySide6", "shiboken"}
    files = sorted(SNAP_PACKAGE.glob("*.py"))
    assert len(files) >= 5
    for path in files:
        roots = {module.split(".")[0] for module in imported_modules(path)}
        assert roots.isdisjoint(forbidden), path.name
        assert len(Path(path).read_text(encoding="utf-8").splitlines()) <= 400, path.name
