# SPDX-License-Identifier: LGPL-2.1-or-later
"""Pièce en bois : cas limites des sources et du dessin (relecture de fin de jalon, issue #73).

Corps vide, esquisse avec trou ou à contours disjoints, ``App::Part`` imbriqués, ``App::Link``,
annuler / rétablir, suppression de la source puis annulation, cotes aux bornes, forme au-delà des
plafonds de taille (§ 4.9), forme importée tournée de 30°.
"""

from __future__ import annotations

import math
from typing import Any

import pytest

from tests.integration.test_piece_en_bois import (
    TOLERANCE,
    assert_same_place,
    box,
    closed_sketch,
    dimensions,
    imported,
    leg,
    part_of,
    rectangle,
    snapshot,
)

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
Part = pytest.importorskip("Part")
Sketcher = pytest.importorskip("Sketcher")
api = pytest.importorskip("freecad.menuiserie.api")

MAX_DIMENSION = 20_000.0
MIN_DIMENSION = 0.1
SIDES = 5_100  # prisme régulier : 5 102 faces, au-delà du plafond de 5 000 faces


def add_rectangle(sketch: Any, left: float, bottom: float, width: float, height: float) -> None:
    """Contour rectangulaire fermé de plus dans l'esquisse (trou, ou second contour)."""
    first = len(sketch.Geometry)
    right, top = left + width, bottom + height
    corners = [(left, bottom), (right, bottom), (right, top), (left, top)]
    for index, (x, y) in enumerate(corners):
        nx, ny = corners[(index + 1) % 4]
        sketch.addGeometry(Part.LineSegment(App.Vector(x, y, 0), App.Vector(nx, ny, 0)), False)
    for index in range(4):
        sketch.addConstraint(
            Sketcher.Constraint("Coincident", first + index, 2, first + (index + 1) % 4, 1)
        )


def assert_refused(document: Any, source: Any, error: type[Exception], match: str) -> None:
    """La conversion de ``source`` est refusée sans rien créer ni modifier."""
    before, count = snapshot(source), len(document.Objects)
    with pytest.raises(error, match=match):
        api.make_shaped_part(source)
    assert len(document.Objects) == count
    assert snapshot(source) == before
    assert source.Visibility


# --- sources refusées ----------------------------------------------------------------------


def test_corps_vide_refuse(document: Any) -> None:
    body = document.addObject("PartDesign::Body", "Vide")
    document.recompute()
    assert_refused(document, body, ValueError, "pas de forme|pas un solide")


def test_corps_avec_esquisse_seule_refuse(document: Any) -> None:
    body = document.addObject("PartDesign::Body", "SansProtrusion")
    rectangle(body.newObject("Sketcher::SketchObject", "Esquisse"), 45.0, 95.0)
    document.recompute()
    assert_refused(document, body, ValueError, "pas de forme|pas un solide")


def test_lien_refuse(document: Any) -> None:
    target = box(document, (100.0, 50.0, 20.0))
    link = document.addObject("App::Link", "Lien")
    link.LinkedObject = target
    document.recompute()
    assert_refused(document, link, TypeError, "ne peut pas devenir une pièce en bois")
    assert target.Visibility


def test_esquisse_a_deux_contours_disjoints_refusee(document: Any) -> None:
    sketch = closed_sketch(document, 100.0, 50.0)
    add_rectangle(sketch, 300.0, 0.0, 80.0, 40.0)
    document.recompute()
    assert_refused(document, sketch, ValueError, "plusieurs surfaces")


def test_esquisse_qui_se_recoupe_refusee(document: Any) -> None:
    sketch = document.addObject("Sketcher::SketchObject", "Noeud")
    points = [(0, 0), (100, 100), (100, 0), (0, 100)]
    for index, (x, y) in enumerate(points):
        nx, ny = points[(index + 1) % 4]
        sketch.addGeometry(Part.LineSegment(App.Vector(x, y, 0), App.Vector(nx, ny, 0)), False)
    for index in range(4):
        sketch.addConstraint(Sketcher.Constraint("Coincident", index, 2, (index + 1) % 4, 1))
    document.recompute()
    assert_refused(document, sketch, ValueError, ".")


# --- esquisse avec trou --------------------------------------------------------------------


def test_esquisse_avec_trou(document: Any, rouvrir: Any) -> None:
    sketch = closed_sketch(document, 300.0, 120.0)
    add_rectangle(sketch, 100.0, 40.0, 100.0, 40.0)
    document.recompute()
    part = api.make_shaped_part(sketch, profile_thickness=18.0)
    assert dimensions(part) == pytest.approx((300.0, 120.0, 18.0), abs=TOLERANCE)
    assert part.Shape.Volume == pytest.approx((300 * 120 - 100 * 40) * 18.0, rel=TOLERANCE)
    assert len(part.Shape.Faces) == 10  # dessus, dessous, quatre côtés et quatre parois du trou
    part.ProfileThickness = 30.0
    document.recompute()
    assert part.Shape.Volume == pytest.approx((300 * 120 - 100 * 40) * 30.0, rel=TOLERANCE)
    name = part.Name
    reopened = rouvrir(document)
    reopened.recompute()
    restored = reopened.getObject(name)
    assert restored.ProfileThickness.Value == pytest.approx(30.0)
    assert restored.Shape.Volume == pytest.approx((300 * 120 - 100 * 40) * 30.0, rel=TOLERANCE)


# --- conteneurs imbriqués ------------------------------------------------------------------


@pytest.mark.parametrize("kind", ["boite", "corps"])
def test_app_part_imbriques(document: Any, kind: str) -> None:
    outer = document.addObject("App::Part", "Atelier")
    inner = document.addObject("App::Part", "Meuble")
    outer.Placement = App.Placement(App.Vector(1000, 200, 0), App.Rotation(App.Vector(0, 0, 1), 90))
    inner.Placement = App.Placement(App.Vector(0, 300, 50), App.Rotation(App.Vector(1, 0, 0), 30))
    outer.addObject(inner)
    source = box(document, (45.0, 95.0, 720.0)) if kind == "boite" else leg(document)
    inner.addObject(source)
    document.recompute()
    part = part_of(source)
    document.recompute()
    assert part.Name in [obj.Name for obj in inner.Group]
    assert part.Name not in [obj.Name for obj in outer.Group]
    assert_same_place(part, source)
    outer.Placement = App.Placement(App.Vector(-500, 0, 100), App.Rotation(App.Vector(0, 1, 0), 20))
    document.recompute()
    assert_same_place(part, source)  # le conteneur déplacé emporte la source et la pièce


# --- annuler / rétablir --------------------------------------------------------------------


def test_annuler_retablir_la_conversion_de_bout_en_bout(document: Any) -> None:
    document.UndoMode = 1
    source = leg(document)
    before = snapshot(source)
    document.openTransaction("Conversion")
    part = part_of(source)
    document.commitTransaction()
    name, expected = part.Name, dimensions(part)
    document.undo()
    document.recompute()
    assert document.getObject(name) is None
    assert source.Visibility
    assert snapshot(source) == before
    document.redo()
    document.recompute()
    restored = document.getObject(name)
    assert api.is_shaped_part(restored)
    assert restored.Source == source
    assert not source.Visibility
    assert dimensions(restored) == pytest.approx(expected, abs=TOLERANCE)
    assert "Invalid" not in restored.State
    assert_same_place(restored, source)
    document.undo()
    again = part_of(source)  # après un aller-retour, la source peut être convertie de nouveau
    assert api.is_shaped_part(again)


def test_annuler_une_modification_du_repere(document: Any) -> None:
    document.UndoMode = 1
    source = leg(document)
    part = part_of(source)
    document.recompute()
    axes, placement, expected = part.SourceAxes, part.Placement, dimensions(part)
    document.openTransaction("Repère")
    api.reset_shaped_axes(part)
    part.Placement = App.Placement(App.Vector(7, 8, 9), part.Placement.Rotation)
    document.commitTransaction()
    document.undo()
    document.recompute()
    assert part.SourceAxes.isSame(axes, 1e-9)
    assert part.Placement.isSame(placement, 1e-6)
    assert dimensions(part) == pytest.approx(expected, abs=TOLERANCE)


def test_supprimer_la_source_puis_annuler(document: Any) -> None:
    document.UndoMode = 1
    source = box(document, (45.0, 95.0, 720.0))
    part = part_of(source)
    document.recompute()
    name, expected = source.Name, dimensions(part)
    document.openTransaction("Supprimer la source")
    document.removeObject(name)
    document.commitTransaction()
    document.recompute()  # aucune exception Python
    assert "Invalid" in part.State
    document.undo()
    document.recompute()
    assert part.Source is not None
    assert part.Source.Name == name
    assert "Invalid" not in part.State
    assert dimensions(part) == pytest.approx(expected, abs=TOLERANCE)


# --- bornes de cotes -----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("size", "accepted"),
    [
        ((MAX_DIMENSION, 100.0, 100.0), True),
        ((MAX_DIMENSION + 1.0, 100.0, 100.0), False),
        ((100.0, 50.0, MIN_DIMENSION), True),
        ((100.0, 50.0, MIN_DIMENSION / 2), False),
    ],
    ids=["tres-grande", "trop-grande", "tres-petite", "trop-petite"],
)
def test_cotes_aux_bornes(document: Any, size: tuple[float, float, float], accepted: bool) -> None:
    source = box(document, size)
    if accepted:
        part = part_of(source)
        assert sorted(dimensions(part)) == pytest.approx(sorted(size), abs=0.01)
        assert "Invalid" not in part.State
    else:
        assert_refused(document, source, ValueError, "Cote invalide")


def test_dessin_qui_devient_trop_mince_puis_se_corrige(document: Any) -> None:
    source = leg(document)
    pad = source.Group[1]
    part = part_of(source)
    document.recompute()
    pad.Length = 0.05  # en dessous de la cote minimale : erreur traduite, pas d'exception
    document.recompute()
    assert "Invalid" in part.State
    pad.Length = 720.0
    document.recompute()
    assert "Invalid" not in part.State
    assert dimensions(part) == pytest.approx((720.0, 95.0, 45.0), abs=TOLERANCE)


# --- plafonds de taille (§ 4.9) --------------------------------------------------------------


def test_forme_au_dela_des_plafonds_garde_les_axes_de_la_source(
    document: Any, vue_rapport: Any
) -> None:
    ring = [
        App.Vector(
            100 * math.cos(2 * math.pi * k / SIDES), 100 * math.sin(2 * math.pi * k / SIDES), 0
        )
        for k in range(SIDES)
    ]
    prism = Part.Face(Part.makePolygon([*ring, ring[0]])).extrude(App.Vector(0, 0, 30))
    assert len(prism.Faces) > 5_000
    source = imported(document, prism, name="Prisme")
    part = part_of(source)
    assert any("trop détaillée" in text for text in vue_rapport.de_niveau("Warning"))
    assert dimensions(part) == pytest.approx((200.0, 200.0, 30.0), abs=0.01)
    assert "Invalid" not in part.State
    assert_same_place(part, source)
    api.reset_shaped_axes(part)  # le repère automatique retombe de même sur les axes de la source
    assert dimensions(part) == pytest.approx((200.0, 200.0, 30.0), abs=0.01)


# --- forme importée tournée de 30° ---------------------------------------------------------


@pytest.mark.parametrize(
    "axis", [App.Vector(0, 0, 1), App.Vector(1, 2, 3)], ids=["autour-de-z", "oblique"]
)
def test_plateau_importe_tourne_de_30_degres(document: Any, axis: Any) -> None:
    plank = Part.makeBox(800, 400, 22)
    turn = App.Placement(App.Vector(10, 20, 30), App.Rotation(axis, 30))
    plank.transformShape(turn.toMatrix(), True)  # la rotation est dans la géométrie
    source = imported(document, plank, name="Plateau")
    assert source.Placement.isIdentity()
    part = part_of(source)
    assert dimensions(part) == pytest.approx((800.0, 400.0, 22.0), abs=0.02)
    assert_same_place(part, source)
    local = part.Shape.copy()
    local.Placement = App.Placement()
    box_ = local.BoundBox
    assert (box_.XMin, box_.YMin, box_.ZMin) == pytest.approx((0.0, 0.0, 0.0), abs=TOLERANCE)
