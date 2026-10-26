# SPDX-License-Identifier: LGPL-2.1-or-later
"""Échantillon d'une forme et repère automatique (ADR 0020, § 4.9) sur des formes simulées.

L'extraction réelle (OCC : maillage, faces planes, arêtes droites) et le calcul de la forme locale
sont vérifiés par ``tests/integration/test_piece_en_bois.py``."""

from __future__ import annotations

import itertools
import sys
import types
from collections.abc import Iterator
from typing import Any

import pytest

from freecad.menuiserie.core.shaped import MAX_EDGES, MAX_FACES, MAX_POINTS
from tests.unit.aides_freecad import simulated_freecad


class Vec:
    """Vecteur FreeCAD minimal."""

    def __init__(self, x: float, y: float, z: float) -> None:
        self.x, self.y, self.z = x, y, z

    def __sub__(self, other: Vec) -> Vec:
        return Vec(self.x - other.x, self.y - other.y, self.z - other.z)


class Plane:
    """Surface plane (``Part.Plane``)."""

    def __init__(self, axis: Vec) -> None:
        self.Axis = axis


class Line:
    """Courbe droite (``Part.Line``)."""


class Vertex:
    def __init__(self, point: Vec) -> None:
        self.Point = point


class Face:
    def __init__(self, surface: Any, area: float) -> None:
        self.Surface = surface
        self.Area = area


class Edge:
    def __init__(self, start: Vec, end: Vec, curve: Any) -> None:
        self.Curve = curve
        self.Vertexes = [Vertex(start), Vertex(end)]
        self.Length = (
            (end.x - start.x) ** 2 + (end.y - start.y) ** 2 + (end.z - start.z) ** 2
        ) ** 0.5


class Box:
    """Boîte de côtés ``size`` alignés sur les axes, avec ce que lit ``sample_of``."""

    def __init__(self, size: tuple[float, float, float]) -> None:
        a, b, c = size
        self.corners = [Vec(x, y, z) for x, y, z in itertools.product((0, a), (0, b), (0, c))]
        self.Vertexes = [Vertex(point) for point in self.corners]
        self.Faces = [
            Face(Plane(Vec(*axis)), area)
            for axis, area in (
                ((1, 0, 0), b * c),
                ((0, 1, 0), a * c),
                ((0, 0, 1), a * b),
            )
            for _ in range(2)
        ]
        self.Edges = [
            Edge(p, q, Line())
            for p, q in itertools.combinations(self.corners, 2)
            if sum((p.x != q.x, p.y != q.y, p.z != q.z)) == 1
        ]
        self.BoundBox = types.SimpleNamespace(DiagonalLength=(a * a + b * b + c * c) ** 0.5)
        self.tessellated: list[float] = []
        self.size = size

    def tessellate(self, tolerance: float) -> tuple[list[Vec], list[Any]]:
        self.tessellated.append(tolerance)
        return list(self.corners), []

    def optimalBoundingBox(self, *_flags: bool) -> Any:  # nom imposé par FreeCAD
        a, b, c = self.size
        return types.SimpleNamespace(XLength=a, YLength=b, ZLength=c)


@pytest.fixture
def frame(monkeypatch: pytest.MonkeyPatch) -> Iterator[Any]:
    """``features.shaped_frame`` importé sur un FreeCAD simulé dont ``Part`` a les classes de
    surface et de courbe des formes d'essai."""
    with simulated_freecad(monkeypatch):
        from freecad.menuiserie.features import shaped_frame

        part = sys.modules["Part"]  # le module Part simulé que voit shaped_frame
        monkeypatch.setattr(part, "Plane", Plane, raising=False)
        monkeypatch.setattr(part, "Line", Line, raising=False)
        monkeypatch.setattr(
            shaped_frame, "ERRORS", (RuntimeError, ValueError, TypeError)
        )  # les erreurs d'OCC, simulées
        monkeypatch.setattr(part, "LineSegment", type("LineSegment", (), {}), raising=False)
        yield shaped_frame


def test_echantillon_d_une_boite(frame: Any) -> None:
    box = Box((800.0, 400.0, 22.0))
    sample = frame.sample_of(box)
    assert sample is not None
    assert len(sample.points) == 16  # sommets + points du maillage
    assert len(sample.planar_faces) == 6
    assert len(sample.straight_edges) == 12
    assert not sample.exceeds_limits
    assert (
        sorted(length for _direction, length in sample.straight_edges)
        == [22.0] * 4 + [400.0] * 4 + [800.0] * 4
    )


def test_tolerance_du_maillage_bornee(frame: Any) -> None:
    for size, expected in (((10.0, 10.0, 10.0), 0.1), ((100_000.0, 1.0, 1.0), 50.0)):
        box = Box(size)
        frame.sample_of(box)
        assert box.tessellated == [expected]
    middle = Box((600.0, 600.0, 600.0))
    frame.sample_of(middle)
    assert middle.tessellated[0] == pytest.approx((600.0 * 3**0.5) / 200.0)


def test_faces_non_planes_et_aretes_courbes_ignorees(frame: Any) -> None:
    box = Box((100.0, 50.0, 20.0))
    box.Faces.append(Face(object(), 10.0))  # cylindre, B-spline...
    box.Faces.append(Face(Plane(Vec(0, 0, 1)), 0.0))  # face dégénérée
    box.Edges.append(Edge(Vec(0, 0, 0), Vec(1, 0, 0), object()))  # arc, B-spline...
    box.Edges.append(Edge(Vec(0, 0, 0), Vec(0, 0, 0), Line()))  # arête de longueur nulle
    sample = frame.sample_of(box)
    assert len(sample.planar_faces) == 6
    assert len(sample.straight_edges) == 12


@pytest.mark.parametrize(
    ("attribute", "count"),
    [("Faces", MAX_FACES + 1), ("Edges", MAX_EDGES + 1)],
)
def test_au_dela_des_plafonds_rien_n_est_examine(frame: Any, attribute: str, count: int) -> None:
    box = Box((100.0, 50.0, 20.0))
    setattr(box, attribute, [object()] * count)  # un accès à un élément ferait échouer
    assert frame.sample_of(box) is None
    assert box.tessellated == []


def test_trop_de_points_du_maillage(frame: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    box = Box((100.0, 50.0, 20.0))
    monkeypatch.setattr(
        box, "tessellate", lambda _tolerance: ([Vec(0, 0, 0)] * (MAX_POINTS + 1), [])
    )
    assert frame.sample_of(box) is None


def test_echantillon_invalide_donne_none(frame: Any) -> None:
    box = Box((100.0, 50.0, 20.0))
    box.Faces[0].Surface.Axis = Vec(0.0, 0.0, 0.0)  # normale nulle : ValueError de core
    assert frame.sample_of(box) is None


@pytest.mark.parametrize(
    ("size", "x", "y", "z"),
    [
        ((800.0, 400.0, 22.0), (1, 0, 0), (0, 1, 0), (0, 0, 1)),
        ((22.0, 800.0, 400.0), (0, 1, 0), (0, 0, 1), (1, 0, 0)),
        ((400.0, 22.0, 800.0), (0, 0, 1), (1, 0, 0), (0, 1, 0)),
    ],
)
def test_repere_automatique_longueur_largeur_epaisseur(
    frame: Any, size: tuple[float, float, float], x: Any, y: Any, z: Any
) -> None:
    axes, limited = frame.automatic_axes(Box(size))
    assert not limited
    for axis, expected in zip(axes.vectors(), (x, y, z), strict=True):
        assert (axis.x, axis.y, axis.z) == pytest.approx(expected)


def test_forme_trop_detaillee_garde_les_axes_de_la_source(frame: Any) -> None:
    box = Box((22.0, 800.0, 400.0))
    box.Faces = [Face(object(), 1.0)] * (MAX_FACES + 1)
    axes, limited = frame.automatic_axes(box)
    assert limited
    # axes de la source, seulement ordonnés d'après l'encombrement de la forme
    assert (axes.x.x, axes.x.y, axes.x.z) == pytest.approx((0, 1, 0))
    assert (axes.z.x, axes.z.y, axes.z.z) == pytest.approx((1, 0, 0))
