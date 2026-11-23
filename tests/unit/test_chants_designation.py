# SPDX-License-Identifier: LGPL-2.1-or-later
"""Désignation des arêtes d'une boîte (issue #5) : bouts d'arête, élément cliqué, contour d'une
face, cas limites des dessins cliquables."""

from __future__ import annotations

import pytest

from freecad.menuiserie.core.edges import (
    Hit,
    all_edges,
    box_hit,
    box_view,
    edge_ends,
    edges_at,
    face_at,
    face_corners,
    face_ring_codes,
    loop_edges,
    nearest_edge,
    net_cells,
    net_hit,
    parse_edge,
)
from freecad.menuiserie.core.geometry import Vec3
from freecad.menuiserie.core.part_model import Dimensions

BOARD = Dimensions(600.0, 300.0, 19.0)
FACES = ["Z+", "Z-", "Y-", "Y+", "X-", "X+"]


def _sizes(dimensions: Dimensions) -> tuple[float, float, float]:
    return (dimensions.length, dimensions.width, dimensions.thickness)


@pytest.mark.parametrize("edge", all_edges(), ids=lambda edge: edge.code)
def test_les_bouts_d_une_arete_sont_sur_la_boite_et_ne_different_que_le_long_de_l_arete(
    edge: object,
) -> None:
    start, end = edge_ends(BOARD, edge)  # type: ignore[arg-type]
    sizes = _sizes(BOARD)
    for index in range(3):
        values = {start.component(index), end.component(index)}
        if index == edge.along:  # type: ignore[attr-defined]
            assert values == {0.0, sizes[index]}
        else:
            assert len(values) == 1 and values <= {0.0, sizes[index]}


@pytest.mark.parametrize("face", FACES)
def test_le_contour_d_une_face_est_fait_des_bouts_de_ses_aretes(face: str) -> None:
    corners = face_corners(BOARD, face)
    codes = face_ring_codes(face)
    assert sorted(codes) == sorted(edge.code for edge in loop_edges(face))
    for index, code in enumerate(codes):
        start, end = edge_ends(BOARD, parse_edge(code))
        side = {corners[index], corners[(index + 1) % 4]}
        assert {start, end} == side


@pytest.mark.parametrize("face", FACES)
def test_le_centre_d_une_face_designe_ses_quatre_aretes(face: str) -> None:
    corners = face_corners(BOARD, face)
    center = Vec3(
        sum(c.x for c in corners) / 4, sum(c.y for c in corners) / 4, sum(c.z for c in corners) / 4
    )
    assert face_at(BOARD, center) == face
    assert {e.code for e in edges_at(BOARD, "Face", center)} == {e.code for e in loop_edges(face)}


def test_un_morceau_d_arete_coupe_par_un_assemblage_reste_son_arete() -> None:
    # morceau au quart de l'arête dessus-avant, décalé de 0,5 mm vers l'intérieur
    point = Vec3(150.0, 0.5, 18.5)
    assert [e.code for e in edges_at(BOARD, "Edge", point)] == ["Z+Y-"]


@pytest.mark.parametrize("edge", all_edges(), ids=lambda edge: edge.code)
def test_un_sommet_designe_les_trois_aretes_du_coin(edge: object) -> None:
    start, _end = edge_ends(BOARD, edge)  # type: ignore[arg-type]
    found = edges_at(BOARD, "Vertex", start)
    assert len(found) == 3 and edge in found
    for other in found:
        assert start in edge_ends(BOARD, other)


def test_un_point_loin_hors_de_la_boite_donne_encore_une_arete() -> None:
    assert len(edges_at(BOARD, "Edge", Vec3(-1e6, -1e6, -1e6))) == 1
    assert len(edges_at(BOARD, "Vertex", Vec3(1e6, 1e6, 1e6))) == 3


def test_un_element_inconnu_est_refuse() -> None:
    with pytest.raises(ValueError, match="Wire"):
        edges_at(BOARD, "Wire", Vec3(0.0, 0.0, 0.0))


def test_a_egalite_la_premiere_arete_gagne_et_le_choix_est_stable() -> None:
    cube = Dimensions(100.0, 100.0, 100.0)
    center = Vec3(50.0, 50.0, 50.0)
    assert nearest_edge(cube, center) == nearest_edge(cube, center) == all_edges()[0]


def test_une_planche_tres_grande_ou_tres_fine_garde_ses_aretes_distinctes() -> None:
    thin = Dimensions(5000.0, 2000.0, 0.5)
    ends = {edge.code: edge_ends(thin, edge) for edge in all_edges()}
    assert len(set(ends.values())) == 12


def test_le_patron_survit_a_un_dessin_minuscule_ou_negatif() -> None:
    for width, height in ((0.0, 0.0), (-10.0, 5.0), (7.0, 7.0)):
        cells = net_cells(width, height)
        assert len(cells) == 6 and all(cell.size >= 1.0 for cell in cells)


def test_sur_le_coin_d_une_case_le_clic_designe_une_arete_et_une_seule() -> None:
    cells = net_cells(240, 180)
    cell = next(cell for cell in cells if cell.face == "Y-")
    hit = net_hit(cells, cell.x + cell.size / 2, cell.y + cell.size / 2)
    assert hit == Hit("face", "Y-")
    corner = net_hit(cells, cell.x + 0.5, cell.y + 0.5)
    assert corner is not None and corner.kind == "edge"


def test_le_bord_exact_du_patron_et_juste_au_dela() -> None:
    cells = net_cells(240, 180)
    last = next(cell for cell in cells if cell.face == "Y+")
    assert net_hit(cells, last.x + last.size - 1e-6, last.y + last.size / 2) is not None
    assert net_hit(cells, last.x + last.size + 0.5, last.y + last.size / 2) is None


def test_hors_de_la_boite_rien() -> None:
    view = box_view(BOARD, 240, 160)
    assert box_hit(view, -500.0, -500.0) is None
    assert box_hit(view, 1e6, 1e6) is None


def test_une_tolerance_nulle_ne_designe_une_arete_que_sur_le_trait() -> None:
    view = box_view(BOARD, 240, 160)
    edge = next(e for e in view.edges if not e.hidden)
    middle = ((edge.start[0] + edge.end[0]) / 2, (edge.start[1] + edge.end[1]) / 2)
    hit = box_hit(view, *middle, tolerance=0.0)
    assert hit is not None and hit.kind == "edge"


@pytest.mark.parametrize("size", [(60, 40), (1, 1), (4000, 3000)])
def test_la_boite_tient_dans_des_dessins_de_toute_taille(size: tuple[int, int]) -> None:
    width, height = size
    view = box_view(BOARD, width, height, margin=0.0)
    points = [p for face in view.faces for p in face.outline]
    assert all(-1e-6 <= x <= width + 1e-6 and -1e-6 <= y <= height + 1e-6 for x, y in points)


def test_les_proportions_ne_changent_pas_avec_l_echelle_des_cotes() -> None:
    small = box_view(Dimensions(60.0, 30.0, 10.0), 240, 160)
    large = box_view(Dimensions(6000.0, 3000.0, 1000.0), 240, 160)
    for one, other in zip(small.edges, large.edges, strict=True):
        assert one.code == other.code
        assert one.start == pytest.approx(other.start) and one.end == pytest.approx(other.end)


def test_une_boite_cube_a_douze_aretes_distinctes_dessinees() -> None:
    view = box_view(Dimensions(100.0, 100.0, 100.0), 240, 160)
    assert len({(e.start, e.end) for e in view.edges}) == 12
