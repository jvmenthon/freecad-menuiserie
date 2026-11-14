# SPDX-License-Identifier: LGPL-2.1-or-later
"""Sonde provisoire (issue #257) : noms cartographiés des faces d'une source à plusieurs solides.

Ce test échoue exprès avec un rapport : il sert à lire le comportement de FreeCAD 1.1 dans la CI
avant d'écrire la spécification. Il est remplacé par des tests qui fixent ce comportement.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
Part = pytest.importorskip("Part")
Sketcher = pytest.importorskip("Sketcher")


def _rectangle(sketch: Any, x: float, y: float, dx: float, dy: float) -> None:
    points = [
        App.Vector(x, y, 0),
        App.Vector(x + dx, y, 0),
        App.Vector(x + dx, y + dy, 0),
        App.Vector(x, y + dy, 0),
    ]
    first = sketch.GeometryCount
    for index in range(4):
        sketch.addGeometry(Part.LineSegment(points[index], points[(index + 1) % 4]), False)
    for index in range(4):
        sketch.addConstraint(
            Sketcher.Constraint("Coincident", first + index, 2, first + (index + 1) % 4, 1)
        )


def _names(shape: Any) -> list[tuple[str, set[str]]]:
    """Pour chaque solide : position (centre) et noms cartographiés de ses faces."""
    faces = list(shape.Faces)
    result = []
    for solid in shape.Solids:
        found = set()
        for face in solid.Faces:
            for index, other in enumerate(faces, start=1):
                if face.isSame(other):
                    found.add(str(shape.getElementMappedName(f"Face{index}")))
                    break
        direct = {
            str(solid.getElementMappedName(f"Face{rank}"))
            for rank in range(1, len(solid.Faces) + 1)
        }
        if direct != found:
            found.add("DIRECT-DIFFERENT")
        center = solid.CenterOfMass
        where = f"({center.x:.0f},{center.y:.0f},{center.z:.0f}) V={solid.Volume:.0f}"
        result.append((where, found))
    return result


_HOLDERS: list[Any] = []


def _link(doc: Any, obj: Any) -> None:
    """Un porteur de lien par solide de ``obj``, vers toutes ses faces."""
    _HOLDERS.clear()
    faces = list(obj.Shape.Faces)
    for rank, solid in enumerate(obj.Shape.Solids):
        subs = [
            f"Face{index}"
            for face in solid.Faces
            for index, other in enumerate(faces, start=1)
            if face.isSame(other)
        ]
        holder = doc.addObject("App::FeaturePython", f"Porteur{rank}")
        holder.addProperty("App::PropertyLinkSub", "Lien")
        holder.Lien = (obj, subs)
        _HOLDERS.append(holder)
    doc.recompute()


def _links(obj: Any) -> list[str]:
    """Pour chaque porteur : ses sous-éléments, et le solide qui contient chacun."""
    lines = []
    shape = obj.Shape
    for rank, holder in enumerate(_HOLDERS):
        where = []
        for sub in holder.Lien[1]:
            try:
                face = shape.getElement(sub)
            except Exception:  # pylint: disable=broad-exception-caught
                where.append(f"{sub}=absent")
                continue
            owners = [
                str(index)
                for index, solid in enumerate(shape.Solids)
                if any(face.isSame(other) for other in solid.Faces)
            ]
            where.append(f"{sub}={'+'.join(owners) or 'aucun'}")
        lines.append(f"  lien du solide {rank} état={holder.State} : {' '.join(where)}")
    try:
        lines.append(f"  historique Face1 : {str(shape.getElementHistory('Face1'))[:300]}")
    except Exception as error:  # pylint: disable=broad-exception-caught
        lines.append(f"  historique : {type(error).__name__} {error}")
    return lines


def _describe(title: str, obj: Any, before: list[tuple[str, set[str]]] | None = None) -> list[str]:
    shape = obj.Shape
    lines = [
        f"## {title} : état={obj.State} type={shape.ShapeType} solides={len(shape.Solids)} "
        f"faces={len(shape.Faces)} carte={shape.ElementMapSize}"
    ]
    for rank, (where, names) in enumerate(_names(shape)):
        kept = ""
        if before is not None:
            kept = " gardés:" + ",".join(
                f"{old_rank}:{len(names & old)}/{len(old)}"
                for old_rank, (_w, old) in enumerate(before)
            )
        lines.append(f"  solide {rank} {where} noms={len(names)} vides={'' in names}{kept}")
    lines.extend(_links(obj))
    return lines


def _body(report: list[str], doc: Any) -> None:  # noqa: PLR0915
    body = doc.addObject("PartDesign::Body", "Corps")
    report.append(f"AllowCompound présent : {'AllowCompound' in body.PropertiesList}")
    if "AllowCompound" in body.PropertiesList:
        report.append(f"AllowCompound = {body.AllowCompound}")
    sketch = body.newObject("Sketcher::SketchObject", "Esquisse")
    _rectangle(sketch, 0, 0, 100, 50)
    _rectangle(sketch, 200, 0, 100, 50)
    pad = body.newObject("PartDesign::Pad", "Protrusion")
    pad.Profile = sketch
    pad.Length = 20
    doc.recompute()
    report.extend(_describe("corps, 2 rectangles", body))
    if len(body.Shape.Solids) < 2:
        report.append(f"  Protrusion : {pad.State} {getattr(pad, 'getStatusString', str)()}")
        return
    start = _names(body.Shape)
    _link(doc, body)
    sub = body.Shape.Solids[0]
    report.append(
        f"  sous-solide : carte={sub.ElementMapSize} Tag={sub.Tag} corps Tag={body.Shape.Tag}"
    )
    pad.Length = 30
    doc.recompute()
    report.extend(_describe("corps, protrusion 30", body, start))
    hole = body.newObject("Sketcher::SketchObject", "Trou")
    _rectangle(hole, 220, 10, 20, 20)
    pocket = body.newObject("PartDesign::Pocket", "Poche")
    pocket.Profile = hole
    pocket.Type = 1
    pocket.Reversed = True
    doc.recompute()
    report.extend(_describe("corps, poche dans le solide de droite", body, start))

    groove = body.newObject("Sketcher::SketchObject", "Trait")
    _rectangle(groove, 40, -10, 5, 70)
    cut = body.newObject("PartDesign::Pocket", "Rainure")
    cut.Profile = groove
    cut.Type = 0
    cut.Length = 5
    cut.Reversed = True
    doc.recompute()
    report.extend(_describe("corps, rainure 5 mm en travers du solide de gauche", body, start))
    cut.Type = 1
    doc.recompute()
    report.extend(_describe("corps, trait de scie qui scinde le solide de gauche", body, start))
    doc.removeObject(cut.Name)
    doc.removeObject(groove.Name)
    doc.recompute()

    third = body.newObject("Sketcher::SketchObject", "Troisieme")
    _rectangle(third, -300, 0, 100, 50)
    pad3 = body.newObject("PartDesign::Pad", "Protrusion3")
    pad3.Profile = third
    pad3.Length = 20
    doc.recompute()
    report.extend(_describe("corps, 3e solide ajouté à gauche", body, start))

    bridge = body.newObject("Sketcher::SketchObject", "Pont")
    _rectangle(bridge, 50, 10, 200, 20)
    pad4 = body.newObject("PartDesign::Pad", "Pont3D")
    pad4.Profile = bridge
    pad4.Length = 20
    doc.recompute()
    report.extend(_describe("corps, pont qui fusionne les deux premiers", body, start))


def _feature_box(doc: Any, name: str, x: float, size: tuple[float, float, float]) -> Any:
    box = doc.addObject("Part::Box", name)
    box.Length, box.Width, box.Height = size
    box.Placement.Base = App.Vector(x, 0, 0)
    return box


def _compound(report: list[str], doc: Any) -> None:
    one = _feature_box(doc, "A", 0, (100, 50, 20))
    two = _feature_box(doc, "B", 200, (80, 50, 20))
    compound = doc.addObject("Part::Compound", "Compose")
    compound.Links = [one, two]
    doc.recompute()
    report.extend(_describe("composé Part A, B", compound))
    start = _names(compound.Shape)
    compound.Links = [two, one]
    doc.recompute()
    report.extend(_describe("composé Part B, A (ordre inversé)", compound, start))
    one.Length = 150
    doc.recompute()
    report.extend(_describe("composé, A allongée", compound, start))


def _cut(report: list[str], doc: Any) -> None:
    _HOLDERS.clear()
    board = _feature_box(doc, "Planche", 0, (300, 50, 20))
    saw = _feature_box(doc, "Scie", 400, (10, 80, 40))
    saw.Placement.Base = App.Vector(400, -10, -10)
    cut = doc.addObject("Part::Cut", "Coupe")
    cut.Base, cut.Tool = board, saw
    doc.recompute()
    report.extend(_describe("coupe Part, scie à côté (1 solide)", cut))
    whole = _names(cut.Shape)
    _link(doc, cut)
    saw.Placement.Base = App.Vector(100, -10, -10)
    doc.recompute()
    report.extend(_describe("coupe Part, scie à x=100 (2 solides)", cut, whole))
    halves = _names(cut.Shape)
    _link(doc, cut)
    saw.Placement.Base = App.Vector(200, -10, -10)
    doc.recompute()
    report.extend(_describe("coupe Part, scie à x=200", cut, halves))
    board.Length = 400
    doc.recompute()
    report.extend(_describe("coupe Part, planche allongée", cut, halves))
    saw.Placement.Base = App.Vector(500, -10, -10)
    doc.recompute()
    report.extend(_describe("coupe Part, scie retirée (1 solide)", cut, halves))


def _python_feature(report: list[str], doc: Any) -> None:
    obj = doc.addObject("Part::FeaturePython", "Externe")
    obj.Shape = Part.makeCompound(
        [Part.makeBox(10, 10, 10), Part.makeBox(5, 5, 5, App.Vector(50, 0, 0))]
    )
    doc.recompute()
    report.extend(_describe("FeaturePython d'un autre atelier (composé Python)", obj))
    start = _names(obj.Shape)
    obj.Shape = Part.makeCompound(
        [Part.makeBox(5, 5, 5, App.Vector(50, 0, 0)), Part.makeBox(10, 10, 10)]
    )
    doc.recompute()
    report.extend(_describe("FeaturePython, solides inversés par son script", obj, start))
    plain = doc.addObject("Part::Feature", "Importe")
    plain.Shape = Part.makeCompound(
        [Part.makeBox(10, 10, 10), Part.makeBox(5, 5, 5, App.Vector(50, 0, 0))]
    )
    doc.recompute()
    report.extend(_describe("forme importée (composé)", plain))


class _Suiveur:
    """Proxy qui recopie le premier solide de sa source et réécrit son propre lien de faces."""

    def __init__(self, obj: Any) -> None:
        obj.Proxy = self
        obj.addProperty("App::PropertyLink", "Source")
        obj.addProperty("App::PropertyLinkSub", "Faces")
        obj.addProperty("App::PropertyString", "Empreinte")
        obj.setPropertyStatus("Faces", "Output")
        obj.setPropertyStatus("Empreinte", "Output")
        self.runs = 0

    def execute(self, obj: Any) -> None:
        self.runs += 1
        shape = obj.Source.Shape
        obj.Shape = shape.Solids[0].copy()
        kept = [sub for sub in obj.Faces[1] if not sub.startswith("?")] if obj.Faces else []
        wanted = [f"Face{index}" for index in range(1, 4)]
        if kept != wanted:
            obj.Faces = (obj.Source, wanted)
        obj.Empreinte = f"{shape.Solids[0].Volume:.3f}"

    def dumps(self) -> None:
        return None

    def loads(self, _state: object) -> None:
        return None


def _self_writing(report: list[str], doc: Any) -> None:
    board = _feature_box(doc, "PlancheS", 0, (300, 50, 20))
    saw = _feature_box(doc, "ScieS", 100, (10, 80, 40))
    cut = doc.addObject("Part::Cut", "CoupeS")
    cut.Base, cut.Tool = board, saw
    doc.recompute()
    follower = doc.addObject("Part::FeaturePython", "Suiveur")
    proxy = _Suiveur(follower)
    follower.Source = cut
    follower.Faces = (cut, ["Face1"])
    for step, length in enumerate((300, 350, 400)):
        board.Length = length
        count = doc.recompute()
        report.append(
            f"  suiveur étape {step} : recalculés={count} exécutions={proxy.runs} "
            f"état={follower.State} faces={follower.Faces[1]} empreinte={follower.Empreinte} "
            f"à recalculer={[o.Name for o in doc.Objects if 'Touched' in o.State]}"
        )
    again = doc.recompute()
    report.append(f"  suiveur, recalcul à vide : recalculés={again} exécutions={proxy.runs}")


def test_sonde(document: Any) -> None:
    report: list[str] = [f"FreeCAD {'.'.join(App.Version()[:3])}"]
    probes: list[Callable[[list[str], Any], None]] = [_self_writing]
    for probe in probes:
        try:
            probe(report, document)
        except Exception as error:  # pylint: disable=broad-exception-caught
            report.append(f"!! {probe.__name__} : {type(error).__name__} : {error}")
    pytest.fail("\n".join(report))
