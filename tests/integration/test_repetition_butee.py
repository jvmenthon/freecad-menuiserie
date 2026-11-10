# SPDX-License-Identifier: LGPL-2.1-or-later
"""Répétition jusqu'à une butée (ADR 0047, ``docs/specs/repetition.md`` § 10).

Butée = face, sommet ou pièce entière ; longueur calculée avec ou sans déduction de l'épaisseur
(dernière copie à fleur / en collision) ; la longueur suit la butée déplacée ; butée supprimée ;
grille à deux butées ; refus ; ensemble dans un Std Part ; enregistrer et rouvrir ; annuler et
rétablir ; document d'avant les butées.
"""

from __future__ import annotations

from typing import Any

import pytest

from tests.integration.aides_grille import Line, Reopen, X, Y
from tests.integration.cadre import stale_or_invalid

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
api = pytest.importorskip("freecad.menuiserie.api")
repeat = pytest.importorskip("freecad.menuiserie.features.repeat")

ON_SPAN = api.SpacingMode.COUNT_ON_SPAN
STEP_ON_SPAN = api.SpacingMode.STEP_ON_SPAN


def piece(doc: Any, mark: str = "Barreau", where: tuple[float, float, float] = (0, 0, 0)) -> Any:
    """Pièce de 30 x 20 x 10 mm (X, Y, Z) dont le coin bas est en ``where``."""
    part = api.make_wood_part(30, 20, 10, "chene", mark=mark, doc=doc)
    part.Placement = App.Placement(App.Vector(*where), App.Rotation())
    doc.recompute()
    return part


def face_at(part: Any, axis: str, value: float) -> str:
    """Nom de la face plane de ``part`` perpendiculaire à ``axis``, à la coordonnée ``value``."""
    for index, face in enumerate(part.Shape.Faces, start=1):
        box = face.BoundBox
        low, high = getattr(box, f"{axis}Min"), getattr(box, f"{axis}Max")
        if abs(low - value) < 1e-6 and abs(high - value) < 1e-6:
            return f"Face{index}"
    raise AssertionError((axis, value))


def vertex_at(part: Any, point: tuple[float, float, float]) -> str:
    for index, vertex in enumerate(part.Shape.Vertexes, start=1):
        if point == (vertex.X, vertex.Y, vertex.Z):
            return f"Vertex{index}"
    raise AssertionError(point)


def on_span(count: int, **values: Any) -> Any:
    """Nombre d'éléments ``count`` sur X en « nombre sur une longueur » (longueur : départ)."""
    return api.RepeatParams(spacing=ON_SPAN, grid=(Line(X, count, span=1.0),), **values)


def copies(rep: Any) -> list[Any]:
    found: list[Any] = repeat.copies_of(rep)
    return found


def xs(rep: Any) -> list[float]:
    return [round(c.Placement.Base.x, 6) for c in copies(rep)]


def x_max(copy: Any) -> float:
    return round(float(copy.Shape.BoundBox.XMax), 6)


@pytest.fixture
def undoable(document: Any) -> Any:
    document.UndoMode = 1
    return document


@pytest.fixture
def scene(document: Any) -> tuple[Any, Any]:
    """Un barreau à l'origine (X de 0 à 30) et une butée de 30 mm, face avant à X = 300."""
    return piece(document), piece(document, "Butee", (300, 0, 0))


def test_butee_piece_entiere_derniere_copie_a_fleur(document: Any, scene: Any) -> None:
    barreau, butee = scene
    rep = api.make_repeat([barreau], on_span(4), stops={X: api.Stop(butee)})
    assert rep.Span.Value == 300.0 and rep.Step.Value == 90.0 and rep.DeductThickness is True
    assert xs(rep) == [90.0, 180.0, 270.0] and x_max(copies(rep)[-1]) == 300.0  # à fleur
    assert rep.Stop[0] == butee and stale_or_invalid(document) == []


def test_sans_deduction_la_derniere_copie_commence_a_la_butee(document: Any, scene: Any) -> None:
    barreau, butee = scene
    rep = api.make_repeat([barreau], on_span(4, deduct_thickness=False), stops={X: api.Stop(butee)})
    assert rep.DeductThickness is False and rep.Step.Value == 100.0
    assert xs(rep) == [100.0, 200.0, 300.0] and x_max(copies(rep)[-1]) == 330.0  # en collision
    assert stale_or_invalid(document) == []


def test_butee_face_et_sommet(document: Any, scene: Any) -> None:
    barreau, butee = scene
    face = api.Stop(butee, face_at(butee, "X", 300.0))
    rep = api.make_repeat([barreau], on_span(3), stops={X: face})
    assert rep.Span.Value == 300.0 and xs(rep) == [135.0, 270.0]
    api.edit_repeat(rep, on_span(3), stops={X: api.Stop(butee, vertex_at(butee, (330, 0, 0)))})
    assert rep.Span.Value == 330.0 and rep.StopLabel.endswith(vertex_at(butee, (330, 0, 0)))
    assert xs(rep) == [150.0, 300.0]  # le sommet est le plus lointain : la butée est à 330


def edge_at(part: Any, x: float) -> str:
    """Nom d'une arête de ``part`` entièrement à la coordonnée X ``x``."""
    for index, edge in enumerate(part.Shape.Edges, start=1):
        box = edge.BoundBox
        if abs(box.XMin - x) < 1e-6 and abs(box.XMax - x) < 1e-6:
            return f"Edge{index}"
    raise AssertionError(x)


def test_butee_arete(document: Any, scene: Any) -> None:
    barreau, butee = scene
    edge = edge_at(butee, 300.0)
    rep = api.make_repeat([barreau], on_span(3), stops={X: api.Stop(butee, edge)})
    assert rep.Span.Value == 300.0 and xs(rep) == [135.0, 270.0]
    assert rep.Stop[1] == [edge] and rep.StopLabel.endswith(edge)
    butee.Placement = App.Placement(App.Vector(400, 0, 0), App.Rotation())
    document.recompute()
    assert rep.Span.Value == 400.0 and stale_or_invalid(document) == []


def test_la_longueur_suit_la_butee_deplacee(document: Any, scene: Any) -> None:
    barreau, butee = scene
    rep = api.make_repeat([barreau], on_span(4), stops={X: api.Stop(butee)})
    butee.Placement = App.Placement(App.Vector(450, 0, 0), App.Rotation())
    document.recompute()
    assert rep.Span.Value == 450.0 and rep.Step.Value == 140.0
    assert xs(rep) == [140.0, 280.0, 420.0] and x_max(copies(rep)[-1]) == 450.0
    butee.Length = 60  # redimensionnée : sa face avant ne bouge pas
    document.recompute()
    assert rep.Span.Value == 450.0 and stale_or_invalid(document) == []


def test_pas_sur_une_longueur_le_nombre_ne_change_qu_a_l_edition(
    document: Any, scene: Any, vue_rapport: Any
) -> None:
    barreau, butee = scene
    params = api.RepeatParams(spacing=STEP_ON_SPAN, grid=(Line(X, 2, 50.0, 1.0),))
    rep = api.make_repeat([barreau], params, stops={X: api.Stop(butee)})
    assert rep.Count == 5 and xs(rep) == [50.0, 100.0, 150.0, 200.0, 250.0]
    butee.Placement = App.Placement(App.Vector(400, 0, 0), App.Rotation())
    document.recompute()
    assert rep.Span.Value == 400.0 and rep.Count == 5 and rep.Step.Value == 50.0
    assert any("butée a bougé" in text for text in vue_rapport.de_niveau("Warning"))
    api.edit_repeat(rep, params)  # garde la butée et recalcule le nombre
    assert rep.Count == 7 and x_max(copies(rep)[-1]) == 380.0


def test_butee_supprimee_longueur_saisie_et_avertissement(
    document: Any, scene: Any, vue_rapport: Any
) -> None:
    barreau, butee = scene
    rep = api.make_repeat([barreau], on_span(4), stops={X: api.Stop(butee)})
    document.removeObject(butee.Name)
    document.recompute()
    assert rep.Stop is None and rep.StopLabel == "" and rep.Span.Value == 300.0
    assert xs(rep) == [90.0, 180.0, 270.0] and stale_or_invalid(document) == []
    assert vue_rapport.de_niveau("Error") == []
    assert [t for t in vue_rapport.de_niveau("Warning") if "n'existe plus" in t]
    api.edit_repeat(rep, api.RepeatParams(spacing=ON_SPAN, grid=(Line(X, 5, span=300.0),)))
    assert rep.Span.Value == 300.0 and rep.Step.Value == 67.5 and len(copies(rep)) == 4


def test_refus_traduits(document: Any, scene: Any) -> None:
    barreau, butee = scene
    large = api.make_wood_part(100, 20, 10, "chene", mark="Large", doc=document)
    large.Placement = App.Placement(App.Vector(-50, 0, 0), App.Rotation())  # chevauche le barreau
    document.recompute()
    for stop, message in (
        (api.Stop(large), "chevauche"),
        (api.Stop(butee, "Wire1"), "ni une face, ni une arête, ni un sommet"),
        (api.Stop(barreau), "pièce répétée"),
        (api.Stop(piece(document, "Proche", (20, 0, 0))), "trop proche"),
    ):
        with pytest.raises(ValueError, match=message):
            api.make_repeat([barreau], on_span(4), stops={X: stop})
    with pytest.raises(ValueError, match="n'existe pas"):
        api.make_repeat([barreau], on_span(4), stops={X: api.Stop(butee, "Face99")})
    with pytest.raises(ValueError, match="longueur"):
        api.make_repeat([barreau], api.RepeatParams(count=2), stops={X: api.Stop(butee)})
    with pytest.raises(ValueError, match="Suivre"):
        api.make_repeat([barreau], on_span(4, follow_resize=True), stops={X: api.Stop(butee)})
    assert document.findObjects("App::FeaturePython", "Repeat*") == []


def test_une_copie_ne_sert_pas_de_butee(document: Any, scene: Any) -> None:
    barreau, butee = scene
    rep = api.make_repeat([barreau], on_span(4), stops={X: api.Stop(butee)})
    with pytest.raises(ValueError, match="pièce répétée"):
        api.edit_repeat(rep, on_span(4), stops={X: api.Stop(copies(rep)[0])})
    assert rep.Stop[0] == butee  # rien n'a changé


def test_grille_avec_deux_butees(document: Any) -> None:
    barreau = piece(document)
    mur_x = piece(document, "MurX", (300, 0, 0))
    mur_y = piece(document, "MurY", (0, 200, 0))
    params = api.RepeatParams(spacing=ON_SPAN, grid=(Line(X, 4, span=1.0), Line(Y, 3, span=1.0)))
    stops = {X: api.Stop(mur_x), Y: api.Stop(mur_y)}
    rep = api.make_repeat([barreau], params, stops=stops)
    assert (rep.Span.Value, rep.Span2.Value) == (300.0, 200.0)
    assert (rep.Step.Value, rep.Step2.Value) == (90.0, 90.0) and len(copies(rep)) == 11
    assert {rep.Stop[0], rep.Stop2[0]} == {mur_x, mur_y} and rep.Stop2[0] == mur_y
    mur_y.Placement = App.Placement(App.Vector(0, 290, 0), App.Rotation())
    document.recompute()
    assert (rep.Span.Value, rep.Span2.Value, rep.Step2.Value) == (300.0, 290.0, 135.0)
    corner = max(copies(rep), key=lambda c: (c.Placement.Base.y, c.Placement.Base.x))
    assert round(corner.Shape.BoundBox.YMax, 6) == 290.0 and x_max(corner) == 300.0
    api.edit_repeat(rep, on_span(4), stops={X: api.Stop(mur_x)})
    assert rep.Stop2 is None and rep.Stop[0] == mur_x


def test_sens_inverse_butee_a_gauche(document: Any) -> None:
    barreau = piece(document, where=(500, 0, 0))
    mur = piece(document, "Mur", (100, 0, 0))  # face la plus proche : X = 130
    params = api.RepeatParams(spacing=ON_SPAN, grid=(api.AxisRepeat(X, 3, span=1.0),))
    rep = api.make_repeat([barreau], params, stops={X: api.Stop(mur)})  # « Inverser » déduit
    assert rep.Reverse is True and rep.Span.Value == 400.0 and rep.Step.Value == 185.0
    assert xs(rep) == [315.0, 130.0] and copies(rep)[-1].Shape.BoundBox.XMin == 130.0


def test_butee_passee_de_l_autre_cote_change_le_sens(document: Any) -> None:
    barreau = piece(document, where=(500, 0, 0))
    mur = piece(document, "Mur", (100, 0, 0))
    params = api.RepeatParams(spacing=ON_SPAN, grid=(api.AxisRepeat(X, 3, span=1.0, reverse=True),))
    rep = api.make_repeat([barreau], params, stops={X: api.Stop(mur)})
    mur.Placement = App.Placement(App.Vector(900, 0, 0), App.Rotation())
    document.recompute()
    assert rep.Reverse is False and rep.Span.Value == 400.0
    assert xs(rep) == [685.0, 870.0] and stale_or_invalid(document) == []


def test_enregistrer_et_rouvrir(document: Any, scene: Any, rouvrir: Reopen) -> None:
    barreau, butee = scene
    rep = api.make_repeat([barreau], on_span(4, deduct_thickness=False), stops={X: api.Stop(butee)})
    names = (barreau.Name, butee.Name, rep.Name)
    doc = rouvrir(document)
    barreau, butee, rep = (doc.getObject(n) for n in names)
    assert rep.Stop[0] == butee and rep.DeductThickness is False and rep.StopLabel
    assert rep.getEditorMode("Stop") == ["ReadOnly"]
    butee.Placement = App.Placement(App.Vector(600, 0, 0), App.Rotation())
    doc.recompute()
    assert rep.Span.Value == 600.0 and xs(rep) == [200.0, 400.0, 600.0]
    assert stale_or_invalid(doc) == []


def test_document_d_avant_les_butees(document: Any, scene: Any, rouvrir: Reopen) -> None:
    barreau, _butee = scene
    rep = api.make_repeat([barreau], api.RepeatParams(count=2, step=50.0))
    for name in ("Stop", "Stop2", "Stop3", "StopLabel", "StopLabel2", "StopLabel3"):
        rep.removeProperty(name)
    rep.removeProperty("DeductThickness")
    names = (barreau.Name, rep.Name)
    doc = rouvrir(document)
    barreau, rep = (doc.getObject(n) for n in names)
    assert rep.DeductThickness is True and rep.Stop is None  # recréées, case cochée
    doc.recompute()
    assert xs(rep) == [50.0, 100.0] and stale_or_invalid(doc) == []


def test_annuler_et_retablir(undoable: Any, scene: Any) -> None:
    barreau, butee = scene
    undoable.openTransaction("a")
    rep = api.make_repeat([barreau], on_span(4), stops={X: api.Stop(butee)}, transaction=False)
    undoable.commitTransaction()
    undoable.openTransaction("b")
    butee.Placement = App.Placement(App.Vector(450, 0, 0), App.Rotation())
    undoable.recompute()
    undoable.commitTransaction()
    assert rep.Span.Value == 450.0
    undoable.undo()
    undoable.recompute()
    assert rep.Span.Value == 300.0 and xs(rep) == [90.0, 180.0, 270.0]
    undoable.redo()
    undoable.recompute()
    assert rep.Span.Value == 450.0 and rep.Stop[0] == butee
    undoable.undo()
    undoable.undo()
    assert undoable.getObject("Repeat") is None
    undoable.redo()
    assert undoable.getObject("Repeat").Stop[0] == undoable.getObject(butee.Name)
    undoable.recompute()
    assert stale_or_invalid(undoable) == []


def test_ensemble_avec_std_part_jusqu_a_une_butee(document: Any) -> None:
    """Un caisson (600 mm sur X, rangé dans son Std Part) répété jusqu'à un mur à X = 3000."""
    from tests.integration.test_repetition_ensembles import caisson, corner

    source = caisson(document)
    mur = piece(document, "Mur", (3000, 0, 0))
    rep = api.make_repeat([source], on_span(4), stops={X: api.Stop(mur)})
    assert rep.Span.Value == 3000.0 and rep.Step.Value == 800.0
    found = sorted(corner(c)[0] for c in repeat.copies_of(rep, source))
    assert found == [800.0, 1600.0, 2400.0]  # la dernière copie finit à 2400 + 600 = 3000
    mur.Placement = App.Placement(App.Vector(3300, 0, 0), App.Rotation())
    document.recompute()
    assert rep.Step.Value == 900.0 and corner(repeat.copies_of(rep, source)[-1])[0] == 2700.0
    assert stale_or_invalid(document) == []


def test_butee_hors_du_conteneur(document: Any) -> None:
    """Répétition rangée dans un Std Part, butée dans un autre conteneur décalé de 1000 mm."""
    zone = document.addObject("App::Part", "Zone")
    zone.Placement = App.Placement(App.Vector(0, 0, 0), App.Rotation())
    mur_zone = document.addObject("App::Part", "ZoneMur")
    mur_zone.Placement = App.Placement(App.Vector(1000, 0, 0), App.Rotation())
    barreau, mur = piece(document), piece(document, "Mur")
    zone.addObject(barreau)
    mur_zone.addObject(mur)  # son X local 0 est X = 1000 dans le document
    document.recompute()
    rep = api.make_repeat([barreau], on_span(4), stops={X: api.Stop(mur)})
    assert rep.getParentGeoFeatureGroup() == zone and rep.Span.Value == 1000.0
    assert x_max(copies(rep)[-1]) == 1000.0
    mur_zone.Placement = App.Placement(App.Vector(1300, 0, 0), App.Rotation())
    document.recompute()
    assert rep.Span.Value == 1300.0 and stale_or_invalid(document) == []


def test_intervalle_avant_la_butee(document: Any, scene: Any) -> None:
    """Demande de jv : 3 éléments jusqu'à la butée (X = 300) partagent 300 mm en 3 intervalles ;
    la dernière copie s'arrête à 230, un intervalle avant la butée."""
    barreau, butee = scene
    rep = api.make_repeat([barreau], on_span(3, end_gap=True), stops={X: api.Stop(butee)})
    assert rep.EndGap is True and rep.Step.Value == 100.0 and xs(rep) == [100.0, 200.0]
    butee.Placement = App.Placement(App.Vector(450, 0, 0), App.Rotation())
    document.recompute()
    assert rep.Step.Value == 150.0 and xs(rep) == [150.0, 300.0]
    assert stale_or_invalid(document) == []
