# SPDX-License-Identifier: LGPL-2.1-or-later
"""Dessins cliquables du choix des arêtes (issue #5) : patron déplié et boîte en perspective."""

from __future__ import annotations

import pytest

from freecad.menuiserie.core.edges import (
    HIDDEN_FACES,
    Hit,
    all_edges,
    box_hit,
    box_view,
    face_corners,
    face_sides,
    net_cells,
    net_hit,
    parse_edge,
)
from freecad.menuiserie.core.part_model import Dimensions

BOARD = Dimensions(600.0, 300.0, 19.0)


def _rounded(*points: tuple[float, float]) -> set[tuple[float, float]]:
    return {(round(x, 6), round(y, 6)) for x, y in points}


def test_le_patron_a_six_cases_carrees_qui_tiennent_dans_le_dessin() -> None:
    cells = net_cells(240, 180)
    assert sorted(cell.face for cell in cells) == sorted(["Z+", "Z-", "Y-", "Y+", "X-", "X+"])
    for cell in cells:
        assert cell.x >= 0 and cell.x + cell.size <= 240
        assert cell.y >= 0 and cell.y + cell.size <= 180


@pytest.mark.parametrize("face", ["Z+", "Z-", "Y-", "Y+", "X-", "X+"])
def test_le_centre_d_une_case_designe_sa_face(face: str) -> None:
    cell = next(cell for cell in net_cells(240, 180) if cell.face == face)
    middle = cell.size / 2
    assert net_hit(net_cells(240, 180), cell.x + middle, cell.y + middle) == Hit("face", face)


@pytest.mark.parametrize("face", ["Z+", "Z-", "Y-", "Y+", "X-", "X+"])
def test_le_bord_d_une_case_designe_l_arete_partagee_avec_la_voisine(face: str) -> None:
    cells = net_cells(240, 180)
    cell = next(cell for cell in cells if cell.face == face)
    middle, inside = cell.size / 2, 2.0
    points = {
        "top": (cell.x + middle, cell.y + inside),
        "bottom": (cell.x + middle, cell.y + cell.size - inside),
        "left": (cell.x + inside, cell.y + middle),
        "right": (cell.x + cell.size - inside, cell.y + middle),
    }
    for side, _neighbour, edge in face_sides(face):
        assert net_hit(cells, *points[side]) == Hit("edge", edge.code)


def test_les_cases_voisines_du_patron_partagent_leur_arete() -> None:
    """Replié, le patron est une boîte : deux cases qui se touchent ont la même arête."""
    cells = net_cells(240, 180)
    shared = 0
    for one in cells:
        for other in cells:
            if one.face >= other.face:
                continue
            for s1, (a1, b1) in one.sides().items():
                for s2, (a2, b2) in other.sides().items():
                    if _rounded(a1, b1) == _rounded(a2, b2):
                        shared += 1
                        code1 = next(e.code for s, _n, e in face_sides(one.face) if s == s1)
                        code2 = next(e.code for s, _n, e in face_sides(other.face) if s == s2)
                        assert code1 == code2
    assert shared == 5


def test_hors_du_patron_rien() -> None:
    assert net_hit(net_cells(240, 180), 1.0, 1.0) is None


@pytest.mark.parametrize("face", ["Z+", "Z-", "Y-", "Y+", "X-", "X+"])
def test_coins_d_une_face(face: str) -> None:
    corners = face_corners(BOARD, face)
    assert len(set(corners)) == 4
    axis = {"X": 0, "Y": 1, "Z": 2}[face[0]]
    value = (BOARD.length, BOARD.width, BOARD.thickness)[axis] if face[1] == "+" else 0.0
    assert all(corner.component(axis) == value for corner in corners)


def test_la_boite_a_trois_aretes_cachees_entre_faces_cachees() -> None:
    view = box_view(BOARD, 240, 160)
    hidden = {edge.code for edge in view.edges if edge.hidden}
    assert hidden == {"Z-Y+", "Z-X-", "Y+X-"}
    assert {face.code for face in view.faces if face.hidden} == set(HIDDEN_FACES)
    assert len(view.edges) == 12 and len(view.faces) == 6


def test_la_boite_tient_dans_le_dessin() -> None:
    view = box_view(BOARD, 240, 160)
    points = [p for face in view.faces for p in face.outline]
    assert all(0 <= x <= 240 and 0 <= y <= 160 for x, y in points)


def test_le_dessus_est_en_haut_et_l_avant_devant() -> None:
    """Vue de l'avant, de la droite et du dessus : le dessus est plus haut que l'avant."""
    view = box_view(BOARD, 240, 160)
    by_code = {face.code: face for face in view.faces}
    top = sum(y for _x, y in by_code["Z+"].outline) / 4
    front = sum(y for _x, y in by_code["Y-"].outline) / 4
    assert top < front


@pytest.mark.parametrize("code", [edge.code for edge in all_edges()])
def test_le_milieu_de_chaque_arete_la_designe(code: str) -> None:
    view = box_view(BOARD, 240, 160)
    edge = next(e for e in view.edges if e.code == code)
    middle = ((edge.start[0] + edge.end[0]) / 2, (edge.start[1] + edge.end[1]) / 2)
    hit = box_hit(view, *middle)
    assert hit is not None and hit.kind == "edge"
    # Un trait caché peut croiser un trait visible : le visible l'emporte, jamais une autre
    # arête visible n'est prise pour une visible désignée.
    if not edge.hidden:
        assert hit.code == code


@pytest.mark.parametrize("face", ["Z+", "Z-", "Y-", "Y+", "X-", "X+"])
def test_l_interieur_de_chaque_face_la_designe(face: str) -> None:
    """Un point de la face loin de tout trait (un trait caché peut traverser une face visible :
    il reste cliquable) désigne la face."""
    view = box_view(BOARD, 240, 160)
    drawn = next(f for f in view.faces if f.code == face)
    corners = drawn.outline
    candidates = [
        (
            sum(c[0] * w for c, w in zip(corners, weights, strict=True)),
            sum(c[1] * w for c, w in zip(corners, weights, strict=True)),
        )
        for weights in _weights()
    ]
    x, y = max(candidates, key=lambda p: _clearance(view, p))
    assert _clearance(view, (x, y)) > 2.0
    assert box_hit(view, x, y, tolerance=1.0) == Hit("face", face)


def _weights() -> list[tuple[float, float, float, float]]:
    steps = [i / 6 for i in range(1, 6)]
    return [((1 - u) * (1 - v), u * (1 - v), u * v, (1 - u) * v) for u in steps for v in steps]


def _clearance(view: object, point: tuple[float, float]) -> float:
    import math

    def distance(a: tuple[float, float], b: tuple[float, float]) -> float:
        vx, vy = b[0] - a[0], b[1] - a[1]
        t = max(
            0.0, min(1.0, ((point[0] - a[0]) * vx + (point[1] - a[1]) * vy) / (vx * vx + vy * vy))
        )
        return math.hypot(point[0] - a[0] - t * vx, point[1] - a[1] - t * vy)

    segments = [(e.start, e.end) for e in view.edges]  # type: ignore[attr-defined]
    for f in view.faces:  # type: ignore[attr-defined]
        outline = f.outline
        segments += list(zip(outline, outline[1:] + outline[:1], strict=True))
    return min(distance(a, b) for a, b in segments)


@pytest.mark.parametrize("face", HIDDEN_FACES)
def test_le_bord_d_une_face_cachee_designe_son_arete(face: str) -> None:
    view = box_view(BOARD, 240, 160)
    drawn = next(f for f in view.faces if f.code == face)
    (ax, ay), (bx, by) = drawn.outline[0], drawn.outline[1]
    hit = box_hit(view, (ax + bx) / 2, (ay + by) / 2, tolerance=1.0)
    assert hit is not None and hit.kind == "edge"
    edge = parse_edge(hit.code)
    assert face in {f.value[1] + f.value[0] for f in (edge.first, edge.second)}


def test_une_planche_fine_reste_lisible() -> None:
    view = box_view(Dimensions(2000.0, 300.0, 5.0), 240, 160)
    front = next(f for f in view.faces if f.code == "Y-")
    heights = [y for _x, y in front.outline]
    assert max(heights) - min(heights) > 10
