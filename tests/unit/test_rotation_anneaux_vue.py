# SPDX-License-Identifier: LGPL-2.1-or-later
"""Anneaux de rotation dans la vue 3D, partie pure (RO-d, ADR 0025, ``gui/drag/rings.py`` et
``gui/drag/geometry.py``) : clés, anneaux d'une pièce (conteneur compris), cercle, anneau sous la
souris (caméra orthogonale et perspective, anneau vu par la tranche), angle cumulé sur plusieurs
tours, texte de l'angle, secteur parcouru et dessin."""

from __future__ import annotations

import math
from dataclasses import replace

import pytest

from freecad.menuiserie.core.geometry import Box, RigidTransform, Vec3
from freecad.menuiserie.core.magnet import Ray
from freecad.menuiserie.core.rotation import Ring, matrix_of, ring_angle
from freecad.menuiserie.core.snap import Frame
from freecad.menuiserie.gui.drag.geometry import (
    AXIS_COLORS,
    HOVER_COLOR,
    SECTOR_TRANSPARENCY,
    Drawing,
    Layout,
    Stroke,
    build_drawing,
    build_layout,
)
from freecad.menuiserie.gui.drag.rings import (
    RING_SEGMENTS,
    Sweep,
    advance,
    angle_label,
    build_rings,
    circle,
    ring_axis,
    ring_basis,
    ring_key,
    ring_ray,
    ring_under,
    sector,
)

BOX = Box.from_ranges([(0, 800), (0, 200), (0, 22)])
IDENTITY = RigidTransform.identity()
FRAME = Frame(Vec3(0, 0, 0), Vec3(1, 0, 0), Vec3(0, 1, 0), Vec3(0, 0, 1))
ZERO = Vec3(0.0, 0.0, 0.0)


def norm(v: Vec3) -> float:
    return math.sqrt(v.x**2 + v.y**2 + v.z**2)


def dist(a: Vec3, b: Vec3) -> float:
    return norm(Vec3(a.x - b.x, a.y - b.y, a.z - b.z))


def dot(a: Vec3, b: Vec3) -> float:
    return a.x * b.x + a.y * b.y + a.z * b.z


def ring_z() -> Ring:
    return build_rings(BOX, IDENTITY, IDENTITY)[2]


# --- Clés ---------------------------------------------------------------------------------


def test_cles_des_anneaux() -> None:
    assert [ring_axis(ring_key(a)) for a in range(3)] == [0, 1, 2]
    assert len({ring_key(a) for a in range(3)}) == 3


@pytest.mark.parametrize("key", [None, "", "arrow0", "handle0s", "ring3", "ring", "ring01"])
def test_ce_n_est_pas_un_anneau(key: str | None) -> None:
    assert ring_axis(key) is None


# --- Anneaux d'une pièce ------------------------------------------------------------------


def test_trois_anneaux_autour_du_centre_de_la_piece() -> None:
    rings = build_rings(BOX, IDENTITY, IDENTITY)
    assert [r.axis for r in rings] == [0, 1, 2]
    assert all(r.center == Vec3(400, 100, 11) for r in rings)
    assert [r.normal for r in rings] == [Vec3(1, 0, 0), Vec3(0, 1, 0), Vec3(0, 0, 1)]
    assert len({r.radius for r in rings}) == 1
    assert rings[0].radius == pytest.approx(1.15 * math.sqrt(800**2 + 200**2 + 22**2) / 2)


def test_les_anneaux_suivent_la_piece_mais_pas_ses_axes() -> None:
    """Pièce posée en (1000, 0, 0) : le centre bouge ; les normales restent celles du document
    (même pièce tournée : les axes de rotation sont fixes)."""
    turned = RigidTransform(matrix_of((0.0, 0.0, 90.0)), Vec3(1000, 0, 0))
    rings = build_rings(BOX, turned, IDENTITY)
    assert dist(rings[2].center, turned.apply(Vec3(400, 100, 11))) < 1e-9
    assert [r.normal for r in rings] == [Vec3(1, 0, 0), Vec3(0, 1, 0), Vec3(0, 0, 1)]


def test_les_anneaux_suivent_les_axes_du_conteneur() -> None:
    """B5 : dans un conteneur tourné de 90° autour de Z, l'anneau de l'axe X du ``Placement``
    local a pour normale l'axe Y du document."""
    container = RigidTransform(matrix_of((0.0, 0.0, 90.0)), Vec3(0, 0, 500))
    rings = build_rings(BOX, IDENTITY, container)
    assert dist(rings[0].normal, Vec3(0, 1, 0)) < 1e-9
    assert dist(rings[1].normal, Vec3(-1, 0, 0)) < 1e-9
    assert dist(rings[2].normal, Vec3(0, 0, 1)) < 1e-9
    assert dist(rings[0].center, container.apply(Vec3(400, 100, 11))) < 1e-9
    assert [r.axis for r in rings] == [0, 1, 2]


def test_petite_piece_anneau_d_au_moins_20_mm() -> None:
    tiny = Box.from_ranges([(0, 2), (0, 2), (0, 2)])
    assert all(r.radius == 20.0 for r in build_rings(tiny, IDENTITY, IDENTITY))


# --- Cercle -------------------------------------------------------------------------------


@pytest.mark.parametrize("axis", [0, 1, 2])
def test_cercle_dans_le_plan_de_l_anneau(axis: int) -> None:
    ring = build_rings(BOX, IDENTITY, IDENTITY)[axis]
    points = circle(ring)
    assert len(points) == RING_SEGMENTS + 1
    assert dist(points[0], points[-1]) < 1e-9
    for p in points:
        offset = Vec3(p.x - ring.center.x, p.y - ring.center.y, p.z - ring.center.z)
        assert abs(dot(offset, ring.normal)) < 1e-9
        assert norm(offset) == pytest.approx(ring.radius)


@pytest.mark.parametrize(
    "normal", [Vec3(1, 0, 0), Vec3(0, 1, 0), Vec3(0, 0, 1), Vec3(0.6, 0.0, 0.8)]
)
def test_base_du_plan_directe(normal: Vec3) -> None:
    u, v = ring_basis(normal)
    assert norm(u) == pytest.approx(1) and norm(v) == pytest.approx(1)
    assert dot(u, v) == pytest.approx(0, abs=1e-12)
    cross = Vec3(u.y * v.z - u.z * v.y, u.z * v.x - u.x * v.z, u.x * v.y - u.y * v.x)
    assert dist(cross, normal) < 1e-12


# --- Anneau sous la souris ----------------------------------------------------------------


def test_anneau_touche_vu_de_dessus() -> None:
    rings = build_rings(BOX, IDENTITY, IDENTITY)
    radius = rings[2].radius
    on_ring = Ray(Vec3(400 + radius, 100, 500), Vec3(0, 0, -1))
    assert ring_under(rings, on_ring, 5.0) == ring_key(2)
    assert ring_under(rings, Ray(Vec3(400, 100, 500), Vec3(0, 0, -1)), 5.0) is None
    assert ring_under(rings, Ray(Vec3(400 + radius + 30, 100, 500), Vec3(0, 0, -1)), 5.0) is None


def test_anneau_vu_par_la_tranche_n_est_pas_propose() -> None:
    """D5 : vu de dessus, les anneaux X et Y sont de chant ; aucun rayon vertical ne les touche."""
    rings = build_rings(BOX, IDENTITY, IDENTITY)
    for x in range(-600, 1400, 25):
        for y in range(-500, 700, 25):
            key = ring_under(rings[:2], Ray(Vec3(x, y, 500), Vec3(0, 0, -1)), 12.0)
            assert key is None


def test_camera_orthogonale_origine_au_dela_de_l_anneau() -> None:
    """Le rayon d'une caméra orthogonale part du plan focal : un anneau plus près de la caméra que
    ce plan reste saisissable (``ring_ray`` recule l'origine)."""
    ring = ring_z()
    behind = Ray(Vec3(400 + ring.radius, 100, -300), Vec3(0, 0, -1))  # plan de l'anneau derrière
    assert ring_under((ring,), behind, 5.0) == ring_key(2)
    moved = ring_ray(behind, ring)
    assert moved.direction == behind.direction
    assert moved.origin.z > ring.center.z


def test_camera_en_perspective() -> None:
    ring = ring_z()
    camera = Vec3(400, 100, 1500)
    target = Vec3(400 + ring.radius, 100, 11)
    ray = Ray(camera, Vec3(target.x - camera.x, target.y - camera.y, target.z - camera.z))
    assert ring_under((ring,), ray, 5.0) == ring_key(2)


# --- Angle cumulé -------------------------------------------------------------------------


def test_angle_cumule_sur_plusieurs_tours() -> None:
    total, last = 0.0, 0.0
    for raw in (90.0, 170.0, -150.0, -70.0, 20.0, 110.0):  # 90, 170, 210, 290, 380, 470
        total, last = advance(total, last, raw), raw
    assert total == pytest.approx(470.0)


def test_angle_cumule_en_arriere() -> None:
    total, last = 0.0, 0.0
    for raw in (-100.0, -179.0, 170.0, 100.0):  # -100, -179, -190, -260
        total, last = advance(total, last, raw), raw
    assert total == pytest.approx(-260.0)


def test_angle_cumule_est_l_angle_lu_en_dessous_d_un_demi_tour() -> None:
    ring = ring_z()
    start = Ray(Vec3(400 + ring.radius, 100, 500), Vec3(0, 0, -1))
    now = Ray(Vec3(400, 100 + ring.radius, 500), Vec3(0, 0, -1))
    raw = ring_angle(ring_ray(now, ring), ring, ring_ray(start, ring))
    assert raw == pytest.approx(90.0)
    assert advance(0.0, 0.0, raw or 0.0) == pytest.approx(90.0)


# --- Texte de l'angle ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("angle", "text"),
    [
        (37.5, "37,5°"),
        (15.0, "15°"),
        (0.0, "0°"),
        (-0.0, "0°"),
        (-30.0, "-30°"),
        (-0.04, "0°"),
        (12.34, "12,3°"),
        (360.0, "360°"),
        (-182.5, "-182,5°"),
    ],
)
def test_texte_de_l_angle(angle: float, text: str) -> None:
    assert angle_label(angle) == text


# --- Secteur ------------------------------------------------------------------------------


def sweep_of(angle: float) -> Sweep:
    ring = ring_z()
    return Sweep(ring, Vec3(ring.radius, 0, 0), angle, ring.center)


def test_secteur_nul() -> None:
    assert sector(sweep_of(0.0)) == ()


def test_secteur_de_90_degres_positif() -> None:
    ring = ring_z()
    triangles = sector(sweep_of(90.0))
    assert len(triangles) == math.ceil(90 / (360 / RING_SEGMENTS))
    assert all(t[0] == ring.center for t in triangles)
    first, last = triangles[0][1], triangles[-1][2]
    assert dist(first, Vec3(ring.center.x + ring.radius, ring.center.y, ring.center.z)) < 1e-9
    assert dist(last, Vec3(ring.center.x, ring.center.y + ring.radius, ring.center.z)) < 1e-9
    assert all(dist(p, ring.center) == pytest.approx(ring.radius) for t in triangles for p in t[1:])


def test_secteur_negatif_et_tour_plein() -> None:
    ring = ring_z()
    last = sector(sweep_of(-90.0))[-1][2]
    assert dist(last, Vec3(ring.center.x, ring.center.y - ring.radius, ring.center.z)) < 1e-9
    assert len(sector(sweep_of(900.0))) == RING_SEGMENTS


def test_secteur_suit_le_point_saisi_pas_un_axe() -> None:
    ring = ring_z()
    start = Vec3(0.0, -ring.radius / 2, 0.0)  # saisi sur -Y, vecteur plus court que le rayon
    triangles = sector(Sweep(ring, start, 90.0, ring.center))
    assert dist(triangles[0][1], Vec3(ring.center.x, ring.center.y - ring.radius, 11)) < 1e-9
    assert dist(triangles[-1][2], Vec3(ring.center.x + ring.radius, ring.center.y, 11)) < 1e-9


# --- Dessin -------------------------------------------------------------------------------


def layout_with_rings() -> Layout:
    layout = build_layout(FRAME, BOX, 80.0, frozenset(), frozenset())
    assert layout.rings == ()  # sans anneaux tant que la session n'en donne pas
    return replace(layout, rings=build_rings(BOX, IDENTITY, IDENTITY))


def ring_strokes(drawing: Drawing) -> list[Stroke]:
    return [
        s for s in drawing.strokes if len(s.lines) == 1 and len(s.lines[0]) == RING_SEGMENTS + 1
    ]


def test_dessin_de_trois_anneaux_aux_couleurs_des_axes() -> None:
    drawing = build_drawing(layout_with_rings())
    strokes = ring_strokes(drawing)
    assert [s.color for s in strokes] == list(AXIS_COLORS)
    assert len({s.width for s in strokes}) == 1
    assert drawing.labels == () and drawing.solids == ()


def test_anneau_survole_epaissi() -> None:
    normal = ring_strokes(build_drawing(layout_with_rings()))
    hover = ring_strokes(build_drawing(layout_with_rings(), ring_key(1)))
    assert hover[1].width > normal[1].width
    assert hover[1].color == HOVER_COLOR
    assert [s.width for s in (hover[0], hover[2])] == [normal[0].width, normal[2].width]


def test_dessin_sans_anneau_inchange() -> None:
    layout = build_layout(FRAME, BOX, 80.0, frozenset(), frozenset())
    drawing = build_drawing(layout)
    assert len(drawing.strokes) == 3  # trois flèches seulement
    assert drawing.labels == ()


def test_dessin_du_geste_secteur_transparent_et_angle() -> None:
    sweep = sweep_of(37.5)
    drawing = build_drawing(layout_with_rings(), ring_key(2), sweep=sweep)
    [solid] = drawing.solids
    assert solid.transparency == SECTOR_TRANSPARENCY and 0 < solid.transparency < 1
    assert solid.faces == sector(sweep)
    assert solid.color == AXIS_COLORS[2]
    [label] = drawing.labels
    assert label.text == "37,5°" and label.position == sweep.anchor


def test_dessin_du_geste_angle_nul_sans_secteur() -> None:
    drawing = build_drawing(layout_with_rings(), ring_key(2), sweep=sweep_of(0.0))
    assert drawing.solids == ()
    assert [label.text for label in drawing.labels] == ["0°"]
