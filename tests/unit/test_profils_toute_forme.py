# SPDX-License-Identifier: LGPL-2.1-or-later
"""Profils sur une arête quelconque (ADR 0063, lot P-a : critères A1 à A5)."""

from __future__ import annotations

import math

import pytest

from freecad.menuiserie.core._extrusion import Extrusion
from freecad.menuiserie.core.edges import (
    ANGLED_FAMILIES,
    OVERSHOOT_MM,
    EdgeError,
    EdgeFamily,
    EdgeFrame,
    EdgeId,
    all_edges,
    edge_cut,
    edge_cut_in_frame,
    frame_refusal,
)
from freecad.menuiserie.core.geometry import Vec3
from freecad.menuiserie.core.part_model import Dimensions

PIECE = Dimensions(600.0, 300.0, 20.0)
SIZES = {
    EdgeFamily.CHAMFER: (3.0, 2.0),
    EdgeFamily.ROUND: (4.0, 0.0),
    EdgeFamily.COVE: (4.0, 0.0),
    EdgeFamily.BULLNOSE: (5.0, 0.0),
    EdgeFamily.BEAK: (3.0, 2.0),
    EdgeFamily.OGEE: (6.0, 4.0),
}


def _box_frame(edge: EdgeId, dimensions: Dimensions = PIECE) -> EdgeFrame:
    """Repère d'une des 12 arêtes d'une boîte, construit comme ``features/`` le ferait."""
    sizes = (dimensions.length, dimensions.width, dimensions.thickness)
    corner = [0.0, 0.0, 0.0]
    for face in (edge.first, edge.second):
        corner[face.index] = sizes[face.index] if face.sign > 0 else 0.0
    direction = [0.0, 0.0, 0.0]
    direction[edge.along] = 1.0
    return EdgeFrame(
        name=edge.name,
        start=Vec3.of(corner),
        direction=Vec3.of(direction),
        length=sizes[edge.along],
        first=edge.second.opposite().unit(),
        second=edge.first.opposite().unit(),
        convex=True,
        room_first=sizes[edge.second.index],
        room_second=sizes[edge.first.index],
    )


def _wedge(angle_deg: float, *, convex: bool = True, room: float = 100.0) -> EdgeFrame:
    """Arête de 200 mm le long de Z, première face le long de X, seconde à ``angle_deg``."""
    alpha = math.radians(angle_deg)
    return EdgeFrame(
        name="Edge7",
        start=Vec3(0.0, 0.0, 0.0),
        direction=Vec3(0.0, 0.0, 1.0),
        length=200.0,
        first=Vec3(1.0, 0.0, 0.0),
        second=Vec3(math.cos(alpha), math.sin(alpha), 0.0),
        convex=convex,
        room_first=room,
        room_second=room,
    )


def _ends(cut: Extrusion) -> set[tuple[float, ...]]:
    """Contour de la section aux deux bouts du balayage, en points 3D arrondis."""
    points = set()
    for u, v in cut.section.outline():
        for along in (0.0, cut.length):
            p = cut.point(u, v, along)
            points.add((round(p.x, 6), round(p.y, 6), round(p.z, 6)))
    return points


# --- A1, A2 : à angle droit, la coupe est celle d'une boîte (non-régression) -----------------


@pytest.mark.parametrize("family", list(EdgeFamily))
@pytest.mark.parametrize("edge", all_edges(), ids=lambda edge: edge.code)
def test_angle_droit_meme_coupe_que_la_boite(family: EdgeFamily, edge: EdgeId) -> None:
    a, b = SIZES[family]
    expected = edge_cut(PIECE, edge, family, a, b)
    cut = edge_cut_in_frame(_box_frame(edge), family, a, b)
    assert cut.volume() == pytest.approx(expected.volume())
    assert _ends(cut) == _ends(expected)


def test_angle_du_repere() -> None:
    assert _wedge(90.0).angle == pytest.approx(90.0)
    assert _wedge(60.0).angle == pytest.approx(60.0)
    assert _wedge(90.0).is_right
    assert not _wedge(80.0).is_right


# --- A3 : angles autres que 90° --------------------------------------------------------------


@pytest.mark.parametrize("angle", [45.0, 60.0, 120.0, 135.0])
def test_chanfrein_oblique(angle: float) -> None:
    cut = edge_cut_in_frame(_wedge(angle), EdgeFamily.CHAMFER, 3.0, 2.0)
    area = 0.5 * 3.0 * 2.0 * math.sin(math.radians(angle))
    assert cut.section.area() == pytest.approx(area)
    assert cut.length == pytest.approx(200.0 + 2 * OVERSHOOT_MM)


@pytest.mark.parametrize("angle", [45.0, 60.0, 120.0, 135.0])
def test_quart_de_rond_tangent_aux_deux_faces(angle: float) -> None:
    radius = 4.0
    alpha = math.radians(angle)
    tangent = radius / math.tan(alpha / 2)
    cut = edge_cut_in_frame(_wedge(angle), EdgeFamily.ROUND, radius, 9.0)  # B ignorée
    area = radius * tangent - (math.pi - alpha) * radius**2 / 2
    assert cut.section.area() == pytest.approx(area, rel=1e-6)
    ends = {(round(u, 6), round(v, 6)) for u, v in cut.section.outline()}
    assert (round(tangent, 6), 0.0) in ends
    far = (tangent * math.cos(alpha), tangent * math.sin(alpha))
    assert any(math.dist(far, point) < 1e-6 for point in ends)


@pytest.mark.parametrize("angle", [45.0, 120.0])
def test_gorge_oblique_secteur_centre_sur_l_arete(angle: float) -> None:
    cut = edge_cut_in_frame(_wedge(angle), EdgeFamily.COVE, 4.0)
    assert cut.section.area() == pytest.approx(math.radians(angle) * 16.0 / 2, rel=1e-6)


@pytest.mark.parametrize(
    "family", sorted(set(EdgeFamily) - ANGLED_FAMILIES, key=lambda family: family.value)
)
def test_familles_a_angle_droit_seulement(family: EdgeFamily) -> None:
    a, b = SIZES[family]
    refusal = frame_refusal(_wedge(120.0), family)
    assert refusal is not None
    assert "angle droit" in str(refusal)
    with pytest.raises(EdgeError, match="angle droit"):
        edge_cut_in_frame(_wedge(120.0), family, a, b)
    assert frame_refusal(_wedge(90.0), family) is None


# --- A4, A5 : refus --------------------------------------------------------------------------


def test_arete_rentrante_refusee() -> None:
    with pytest.raises(EdgeError, match="rentrante"):
        edge_cut_in_frame(_wedge(90.0, convex=False), EdgeFamily.CHAMFER, 2.0)


@pytest.mark.parametrize("angle", [10.0, 170.0])
def test_angle_hors_bornes_refuse(angle: float) -> None:
    with pytest.raises(EdgeError, match="entre 30"):
        edge_cut_in_frame(_wedge(angle), EdgeFamily.CHAMFER, 2.0)


def test_profil_plus_grand_que_la_moitie_de_la_face_refuse() -> None:
    with pytest.raises(EdgeError, match="trop grand"):
        edge_cut_in_frame(_wedge(90.0, room=10.0), EdgeFamily.ROUND, 6.0)
    edge_cut_in_frame(_wedge(90.0, room=10.0), EdgeFamily.ROUND, 5.0)


def test_cote_trop_petite_nomme_l_arete() -> None:
    with pytest.raises(EdgeError, match="Edge7"):
        edge_cut_in_frame(_wedge(90.0), EdgeFamily.CHAMFER, 0.01)


# --- B5 : dépassement seulement là où le prolongement sort du solide -------------------------


def test_bouts_sans_depassement_au_ras_du_sommet() -> None:
    frame = _wedge(90.0)
    closed = EdgeFrame(**{**frame.__dict__, "extend_start": False, "extend_end": False})
    cut = edge_cut_in_frame(closed, EdgeFamily.CHAMFER, 2.0)
    assert cut.length == pytest.approx(200.0)
    zs = {round(cut.point(0, 0, along).z, 9) for along in (0.0, cut.length)}
    assert zs == {0.0, 200.0}
    half = EdgeFrame(**{**frame.__dict__, "extend_start": False})
    cut = edge_cut_in_frame(half, EdgeFamily.CHAMFER, 2.0)
    zs = {round(cut.point(0, 0, along).z, 9) for along in (0.0, cut.length)}
    assert zs == {0.0, round(200.0 + OVERSHOOT_MM, 9)}


def test_repere_invalide_refuse() -> None:
    with pytest.raises(ValueError, match="unitaires"):
        EdgeFrame(**{**_wedge(90.0).__dict__, "first": Vec3(2.0, 0.0, 0.0)})
    with pytest.raises(ValueError, match="perpendiculaires"):
        EdgeFrame(**{**_wedge(90.0).__dict__, "first": Vec3(0.0, 0.0, 1.0)})
    with pytest.raises(ValueError, match="longueur"):
        EdgeFrame(**{**_wedge(90.0).__dict__, "length": 0.0})
