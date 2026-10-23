# SPDX-License-Identifier: LGPL-2.1-or-later
"""Miniature isométrique d'une pièce (demande de jv du 2026-10-22, critère A1) : projection et
dessin SVG purs de ``core.cutlist``, sans FreeCAD ni Qt."""

from __future__ import annotations

import math
import re

import pytest

from freecad.menuiserie.core.cutlist import (
    DEFAULT_COLOR,
    THUMBNAIL_HEIGHT,
    THUMBNAIL_WIDTH,
    Point3,
    ThumbFace,
    box_faces,
    isometric,
    svg_data_uri,
    thumbnail_svg,
)

PATH = re.compile(r'<path d="([^"]*)" fill="([^"]*)"')


def paths(svg: str) -> list[tuple[str, str]]:
    """(tracé, remplissage) de chaque ``<path>``."""
    return PATH.findall(svg)


def numbers(path: tuple[str, str]) -> list[float]:
    return [float(value) for value in re.findall(r"-?\d+\.\d+", path[0])]


def attribute(svg: str, name: str) -> str:
    """Attribut ``name`` de l'élément ``<svg>``."""
    match = re.search(rf'<svg [^>]*\b{name}="([^"]*)"', svg)
    assert match is not None
    return match.group(1)


def moved(faces: tuple[ThumbFace, ...], dx: float, dy: float, dz: float) -> tuple[ThumbFace, ...]:
    """``faces`` translatées."""

    def shift(point: Point3) -> Point3:
        return (point[0] + dx, point[1] + dy, point[2] + dz)

    return tuple(
        ThumbFace(
            tuple((shift(a), shift(b), shift(c)) for a, b, c in face.triangles),
            tuple(tuple(shift(p) for p in edge) for edge in face.edges),
        )
        for face in faces
    )


def test_projection_isometrique() -> None:
    assert isometric((0, 0, 0)) == (0, 0)
    x, y = isometric((10, 0, 0))
    assert (x, y) == pytest.approx((10 * math.cos(math.radians(30)), 5))
    x, y = isometric((0, 10, 0))
    assert (x, y) == pytest.approx((-10 * math.cos(math.radians(30)), 5))
    assert isometric((0, 0, 10)) == (0, -10)  # le haut est vers le haut de l'image
    # Les trois axes ont la même longueur à l'écran.
    lengths = {math.dist((0, 0), isometric(p)) for p in ((1, 0, 0), (0, 1, 0), (0, 0, 1))}
    assert max(lengths) - min(lengths) == pytest.approx(0)


def test_boite_six_faces_orientees_vers_l_exterieur() -> None:
    faces = box_faces(30, 20, 10)
    assert len(faces) == 6
    volume = 0.0
    for face in faces:
        assert len(face.triangles) == 2
        for a, b, c in face.triangles:  # volume signé par le théorème de la divergence
            volume += (
                a[0] * (b[1] * c[2] - b[2] * c[1])
                - a[1] * (b[0] * c[2] - b[2] * c[0])
                + a[2] * (b[0] * c[1] - b[1] * c[0])
            ) / 6
    assert volume == pytest.approx(30 * 20 * 10)


@pytest.mark.parametrize("sizes", [(0, 1, 1), (1, -1, 1), (1, 1, float("nan")), (math.inf, 1, 1)])
def test_boite_refuse_une_cote_invalide(sizes: tuple[float, float, float]) -> None:
    with pytest.raises(ValueError, match="invalides"):
        box_faces(*sizes)


def test_boite_n_affiche_que_trois_faces_dans_le_cadre() -> None:
    svg = thumbnail_svg(box_faces(300, 100, 22), (180, 130, 90))
    assert attribute(svg, "viewBox") == f"0 0 {THUMBNAIL_WIDTH} {THUMBNAIL_HEIGHT}"
    assert (attribute(svg, "width"), attribute(svg, "height")) == ("480", "320")
    fills = [fill for _path, fill in paths(svg) if fill != "none"]
    assert len(fills) == 3  # dessus et deux faces latérales : trois tons
    assert len(set(fills)) == 3
    assert len(paths(svg)) == 6  # trois faces et leurs arêtes


def test_dessin_centre_et_dans_le_cadre() -> None:
    for sizes in ((1000, 60, 20), (20, 20, 20), (50, 400, 18)):
        coordinates = [n for path in paths(thumbnail_svg(box_faces(*sizes))) for n in numbers(path)]
        xs, ys = coordinates[0::2], coordinates[1::2]
        assert min(xs) > 0
        assert max(xs) < THUMBNAIL_WIDTH
        assert min(ys) > 0
        assert max(ys) < THUMBNAIL_HEIGHT
        assert (min(xs) + max(xs)) / 2 == pytest.approx(THUMBNAIL_WIDTH / 2, abs=0.05)
        assert (min(ys) + max(ys)) / 2 == pytest.approx(THUMBNAIL_HEIGHT / 2, abs=0.05)


def test_couleur_du_materiau_ombree() -> None:
    svg = thumbnail_svg(box_faces(10, 10, 10), (100, 100, 100))
    lightness = sorted(int(fill[1:3], 16) for _path, fill in paths(svg) if fill != "none")
    assert lightness[0] < lightness[-1] <= 255
    default = thumbnail_svg(box_faces(10, 10, 10))
    assert thumbnail_svg(box_faces(10, 10, 10), DEFAULT_COLOR) == default


def test_une_piece_avec_un_tenon_ne_donne_pas_le_dessin_de_la_boite() -> None:
    """Un tenon (boîte saillante au bout) ajoute des faces visibles au dessin de la boîte."""
    body = box_faces(100, 40, 20)
    with_tenon = body + moved(box_faces(30, 20, 10), 100, 10, 5)
    assert thumbnail_svg(with_tenon) != thumbnail_svg(body)
    assert len(paths(thumbnail_svg(with_tenon))) > len(paths(thumbnail_svg(body)))


def test_ordre_du_peintre_independant_de_l_ordre_des_faces() -> None:
    near = box_faces(10, 10, 10)
    far = moved(near, -8, -8, -8)
    assert thumbnail_svg(far + near) == thumbnail_svg(near + far)


def test_faces_arriere_non_dessinees() -> None:
    back = ThumbFace((((0, 0, 0), (0, 1, 0), (1, 0, 0)),))  # normale -Z : vue de dessous
    front = ThumbFace((((0, 0, 0), (1, 0, 0), (0, 1, 0)),))  # normale +Z
    assert paths(thumbnail_svg([back])) == []
    assert len(paths(thumbnail_svg([front]))) == 1


def test_sans_face_visible_le_svg_est_vide() -> None:
    svg = thumbnail_svg(())
    assert paths(svg) == []
    assert attribute(svg, "viewBox") == "0 0 120 80"
    flat = ThumbFace((((0, 0, 0), (1, 0, 0), (2, 0, 0)),))  # triangle dégénéré
    assert paths(thumbnail_svg([flat])) == []


def test_svg_autonome_sans_ressource_externe() -> None:
    svg = thumbnail_svg(box_faces(300, 100, 22))
    assert "<text" not in svg
    assert "<script" not in svg
    assert "href" not in svg
    assert "http" not in svg.replace("http://www.w3.org/2000/svg", "")
    assert thumbnail_svg(box_faces(300, 100, 22)) == svg  # déterministe


def test_data_uri() -> None:
    svg = thumbnail_svg(box_faces(30, 20, 10))
    uri = svg_data_uri(svg)
    assert uri.startswith("data:image/svg+xml;base64,")
    assert " " not in uri
    with pytest.raises(ValueError, match="SVG"):
        svg_data_uri("<html></html>")
