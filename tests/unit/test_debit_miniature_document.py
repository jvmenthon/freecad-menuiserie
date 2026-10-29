# SPDX-License-Identifier: LGPL-2.1-or-later
"""Miniatures de la liste de débit côté document (demande de jv du 2026-10-22, critère A1) sur
FreeCAD simulé : forme usinée discrétisée, repli sur la boîte de débit, une miniature par groupe,
couleur du matériau. Les vraies formes (tenon, queue d'aronde) sont vérifiées par
``tests/integration/test_liste_de_debit_miniatures.py``."""

from __future__ import annotations

import types
from collections.abc import Iterator
from typing import Any

import pytest

from freecad.menuiserie.core.cutlist import (
    DEFAULT_COLOR,
    Point3,
    ThumbFace,
    box_faces,
    build_cut_list,
    thumbnail_svg,
)
from tests.unit.aides_debit import entry
from tests.unit.aides_debit_document import Doc, Obj, World, simulated_world


class Vector:
    def __init__(self, point: Point3) -> None:
        self.x, self.y, self.z = point


class FakeEdge:
    def __init__(self, points: tuple[Point3, ...]) -> None:
        self.points = points

    def discretize(self, Deflection: float) -> list[Vector]:  # noqa: N803  (nom FreeCAD)
        assert Deflection > 0
        return [Vector(point) for point in self.points]


class FakeFace:
    def __init__(self, face: ThumbFace, error: Exception | None = None) -> None:
        self.face, self.error = face, error
        self.Edges = [FakeEdge(edge) for edge in face.edges]

    def tessellate(self, tolerance: float) -> tuple[list[Vector], list[tuple[int, int, int]]]:
        assert tolerance > 0
        if self.error is not None:
            raise self.error
        points = [p for triangle in self.face.triangles for p in triangle]
        indices = [(3 * i, 3 * i + 1, 3 * i + 2) for i in range(len(self.face.triangles))]
        return [Vector(p) for p in points], indices


class FakeShape:
    """Forme usinée simulée : déjà dans le repère de la brute (``transformed`` la rend)."""

    def __init__(self, faces: tuple[ThumbFace, ...], error: Exception | None = None) -> None:
        self.Faces = [FakeFace(face, error) for face in faces]
        self.Solids = [object()]
        self.Placement = types.SimpleNamespace(
            inverse=lambda: types.SimpleNamespace(toMatrix=lambda: "local")
        )
        self.BoundBox = types.SimpleNamespace(
            DiagonalLength=1000.0, XMin=0.0, XMax=840.0, YMin=0.0, YMax=100.0, ZMin=0.0, ZMax=22.0
        )

    def isNull(self) -> bool:
        return False

    def isValid(self) -> bool:
        return True

    def transformed(self, _matrix: str) -> FakeShape:
        return self


class Document(Doc):
    def getObject(self, name: str) -> Obj | None:
        return next((obj for obj in self.Objects if obj.Name == name), None)


@pytest.fixture
def world(monkeypatch: pytest.MonkeyPatch) -> Iterator[World]:
    with simulated_world(monkeypatch) as simulated:
        from freecad.menuiserie.features import cutlist_thumbnail

        simulated.features.cutlist_thumbnail = cutlist_thumbnail
        colors: dict[str, tuple[int, int, int]] = {"chene": (184, 135, 90)}

        class Library:
            @staticmethod
            def find(material_id: str) -> Any:
                color = colors.get(material_id)
                return None if color is None else types.SimpleNamespace(color=color)

        monkeypatch.setattr(cutlist_thumbnail, "get_library", Library)
        yield simulated


def cut_list_of(world: World, doc: Doc) -> Any:
    return world.features.cutlist_collect.cut_list_of(doc)


def rough_box(cut_list: Any, color: tuple[int, int, int] = (184, 135, 90)) -> str:
    """Miniature attendue en repli : boîte de débit de la première ligne."""
    rough = cut_list.lines[0].rough
    return thumbnail_svg(box_faces(rough.length, rough.width, rough.thickness), color)


def tenon_faces() -> tuple[ThumbFace, ...]:
    """Une planche de 800 x 100 x 22 avec un tenon de 40 x 50 x 10 à son bout."""
    tenon = tuple(
        ThumbFace(
            tuple(
                tuple((x + 800, y + 25, z + 6) for x, y, z in triangle)  # type: ignore[misc]
                for triangle in face.triangles
            ),
            (),
        )
        for face in box_faces(40, 50, 10)
    )
    return box_faces(800, 100, 22) + tenon


def test_forme_usinee_dessinee_a_la_couleur_du_materiau(world: World) -> None:
    blank = world.part("Planche", "M1")
    machined = world.machined("Planche_usinee", blank, FakeShape(tenon_faces()))
    doc = Document(blank, machined)
    cut_list = cut_list_of(world, doc)
    thumbnails = world.features.cutlist_thumbnail.thumbnails_of(doc, cut_list)
    assert thumbnails == {"Planche": thumbnail_svg(tenon_faces(), (184, 135, 90))}
    assert thumbnails["Planche"] != thumbnail_svg(box_faces(800, 100, 22), (184, 135, 90))


def test_repli_sur_la_boite_de_debit_sans_piece_usinee(world: World) -> None:
    blank = world.part(
        "Planche", "M1", (800, 100, 22), LengthAllowance=types.SimpleNamespace(Value=10.0)
    )
    doc = Document(blank)
    cut_list = cut_list_of(world, doc)
    line = cut_list.lines[0]
    expected = thumbnail_svg(
        box_faces(line.rough.length, line.rough.width, line.rough.thickness), (184, 135, 90)
    )
    assert line.rough.length == 810
    assert world.features.cutlist_thumbnail.thumbnails_of(doc, cut_list) == {"Planche": expected}


@pytest.mark.parametrize("state", [["Invalid"], ["Touched"]])
def test_repli_si_la_piece_usinee_est_invalide_ou_a_recalculer(
    world: World, state: list[str]
) -> None:
    blank = world.part("Planche", "M1")
    machined = world.machined("Planche_usinee", blank, FakeShape(tenon_faces()))
    machined.State = state
    doc = Document(blank, machined)
    cut_list = cut_list_of(world, doc)
    svg = world.features.cutlist_thumbnail.thumbnails_of(doc, cut_list)["Planche"]
    assert svg == rough_box(cut_list)


@pytest.mark.parametrize("error", [RuntimeError("OCC"), ValueError("x"), ArithmeticError()])
def test_repli_si_la_discretisation_echoue(world: World, error: Exception) -> None:
    blank = world.part("Planche", "M1")
    machined = world.machined("Planche_usinee", blank, FakeShape(tenon_faces(), error))
    doc = Document(blank, machined)
    cut_list = cut_list_of(world, doc)
    svg = world.features.cutlist_thumbnail.thumbnails_of(doc, cut_list)["Planche"]
    assert svg == rough_box(cut_list)


def test_repli_si_la_forme_est_trop_fine(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    thumbnail = world.features.cutlist_thumbnail
    monkeypatch.setattr(thumbnail, "MAX_TRIANGLES", 5)
    blank = world.part("Planche", "M1")
    machined = world.machined("Planche_usinee", blank, FakeShape(tenon_faces()))
    doc = Document(blank, machined)
    cut_list = cut_list_of(world, doc)
    svg = thumbnail.thumbnails_of(doc, cut_list)["Planche"]
    assert svg == rough_box(cut_list)


def test_une_miniature_par_groupe_pas_par_piece(world: World) -> None:
    first = world.part("A", "M1")
    twin = world.part("B", "M1")  # même cotes et matériau : même groupe
    other = world.part("C", "M2", (500, 90, 18))
    doc = Document(first, twin, other)
    cut_list = cut_list_of(world, doc)
    assert [line.quantity for line in cut_list.lines] == [2, 1]
    thumbnails = world.features.cutlist_thumbnail.thumbnails_of(doc, cut_list)
    assert sorted(thumbnails) == ["A", "C"]  # la première pièce de chaque groupe


def test_materiau_inconnu_couleur_par_defaut(world: World) -> None:
    blank = world.part("Planche", "M1", MaterialId="inconnu", Material="Inconnu")
    doc = Document(blank)
    cut_list = cut_list_of(world, doc)
    svg = world.features.cutlist_thumbnail.thumbnails_of(doc, cut_list)["Planche"]
    assert svg == rough_box(cut_list, DEFAULT_COLOR)


def test_piece_absente_du_document_repli_et_ligne_sans_cle(world: World) -> None:
    thumbnail = world.features.cutlist_thumbnail
    cut_list = build_cut_list([entry("M1"), entry("M2", (500, 90, 18))])  # source vide
    assert thumbnail.thumbnails_of(Document(), cut_list) == {}
    from dataclasses import replace

    gone = replace(cut_list.lines[0], source="Disparue")
    svg = thumbnail.thumbnail_of(Document(), gone)
    assert svg.startswith("<svg") and "<path" in svg


def test_aucun_import_de_l_interface() -> None:
    from tests.unit.aides import ROOT

    source = (ROOT / "freecad/menuiserie/features/cutlist_thumbnail.py").read_text(encoding="utf-8")
    assert "FreeCADGui" not in source
    assert "PySide" not in source


# --- Pièce en bois à forme libre (ADR 0020) : la miniature montre sa forme, pas sa boîte --------


class DrawnShape(FakeShape):
    """Forme d'une pièce en bois : volume, aire et faces servent à son empreinte."""

    Volume = 1.0e6
    Area = 5.0e5


def drawn_part(world: World, name: str, shape: Any, mark: str = "M1") -> Any:
    """Pièce en bois (proxy ``ShapedPart``) de forme ``shape``, dans son repère."""
    proxy = world._proxy("shaped_part", "ShapedPart")
    return world.part(name, mark, Proxy=proxy, Shape=shape)


def test_piece_en_bois_miniature_de_sa_forme_et_non_de_sa_boite(world: World) -> None:
    pied = drawn_part(world, "Pied", DrawnShape(tenon_faces()))
    doc = Document(pied)
    cut_list = cut_list_of(world, doc)
    assert cut_list.lines[0].shape is not None
    svg = world.features.cutlist_thumbnail.thumbnails_of(doc, cut_list)["Pied"]
    assert svg == thumbnail_svg(tenon_faces(), (184, 135, 90))
    finished = cut_list.lines[0].finished
    box = box_faces(finished.length, finished.width, finished.thickness)
    assert svg != thumbnail_svg(box, (184, 135, 90))


def test_piece_en_bois_usinee_miniature_de_la_piece_usinee(world: World) -> None:
    pied = drawn_part(world, "Pied", DrawnShape(box_faces(800, 200, 22)))
    machined = world.machined("Pied_usinee", pied, FakeShape(tenon_faces()))
    doc = Document(pied, machined)
    cut_list = cut_list_of(world, doc)
    svg = world.features.cutlist_thumbnail.thumbnails_of(doc, cut_list)["Pied"]
    assert svg == thumbnail_svg(tenon_faces(), (184, 135, 90))


@pytest.mark.parametrize("state", [["Invalid"], ["Touched"]])
def test_piece_en_bois_illisible_repli_sur_son_encombrement(world: World, state: list[str]) -> None:
    pied = drawn_part(world, "Pied", DrawnShape(tenon_faces()))
    pied.State = state
    doc = Document(pied)
    cut_list = cut_list_of(world, doc)
    finished = cut_list.lines[0].finished
    expected = thumbnail_svg(
        box_faces(finished.length, finished.width, finished.thickness), (184, 135, 90)
    )
    assert world.features.cutlist_thumbnail.thumbnails_of(doc, cut_list)["Pied"] == expected
