# SPDX-License-Identifier: LGPL-2.1-or-later
"""Pièces en bois et montages de référence des assemblages avec une pièce en bois (PD-e).

Module d'aide des tests d'intégration (importé seulement avec FreeCAD).
"""

from __future__ import annotations

import math
from typing import Any

import pytest

from tests.integration.cadre import placement
from tests.integration.test_piece_en_bois import box, imported
from tests.integration.types_assemblages import FRAME, Montage, Scenario, assemble, wood

App = pytest.importorskip("FreeCAD")
Part = pytest.importorskip("Part")
Sketcher = pytest.importorskip("Sketcher")
api = pytest.importorskip("freecad.menuiserie.api")

LENGTH, WIDTH, THICKNESS = 720.0, 95.0, 45.0
SAG = 15.0  # flèche de l'arc : la longue arête de dessus est creusée de 15 mm
BOX_VOLUME = LENGTH * WIDTH * THICKNESS
# Les pièces assemblées en pièces de bois pour comparaison sont posées loin des pièces dessinées.
SHIFT = App.Placement(App.Vector(0, 5000, 0), App.Rotation())
UP = App.Vector(0, 0, 1)


def curved_rail(doc: Any, thickness: float = THICKNESS, name: str = "Galbe") -> Any:
    """Traverse galbée : corps PartDesign dont l'esquisse (720 x 95) a une longue arête creusée
    d'un arc de 15 mm de flèche, protrusion de ``thickness`` mm. Les bouts et la face du dessous
    sont plans et coïncident avec la boîte d'encombrement."""
    body = doc.addObject("PartDesign::Body", name)
    sketch = body.newObject("Sketcher::SketchObject", "Esquisse")
    radius = ((LENGTH / 2) ** 2 + SAG**2) / (2 * SAG)
    center = App.Vector(LENGTH / 2, WIDTH - SAG + radius, 0)
    half_angle = math.asin((LENGTH / 2) / radius)
    start = math.radians(270) - half_angle
    stop = math.radians(270) + half_angle
    corners = [App.Vector(0, 0, 0), App.Vector(LENGTH, 0, 0), App.Vector(LENGTH, WIDTH, 0)]
    sketch.addGeometry(Part.LineSegment(corners[0], corners[1]), False)
    sketch.addGeometry(Part.LineSegment(corners[1], corners[2]), False)
    arc = Part.ArcOfCircle(Part.Circle(center, UP, radius), start, stop)
    sketch.addGeometry(arc, False)
    sketch.addGeometry(Part.LineSegment(App.Vector(0, WIDTH, 0), corners[0]), False)
    for first, first_end, second, second_end in ((0, 2, 1, 1), (1, 2, 2, 2), (2, 1, 3, 1)):
        sketch.addConstraint(
            Sketcher.Constraint("Coincident", first, first_end, second, second_end)
        )
    sketch.addConstraint(Sketcher.Constraint("Coincident", 3, 2, 0, 1))
    pad = body.newObject("PartDesign::Pad", "Protrusion")
    pad.Profile = sketch
    pad.Length = thickness
    doc.recompute()
    return body


def shaped(source: Any, mark: str = "") -> Any:
    """Pièce en bois de ``source`` (document recalculé par la fabrique)."""
    return api.make_shaped_part(source, mark=mark)


def void_block(doc: Any, name: str = "Vide") -> Any:
    """Bloc 200 x 100 x 50 dont le bout x > 140 est enlevé : un vide dans la boîte."""
    block = Part.makeBox(200, 100, 50).cut(Part.makeBox(60, 100, 50, App.Vector(140, 0, 0)))
    return imported(doc, block, name=name)


def notched_block(doc: Any, name: str = "Encoche") -> Any:
    """Bloc 200 x 100 x 50 dont le chant y = 100 est creusé d'une encoche cylindrique de rayon 30
    centrée en x = 100 : une face courbe."""
    cylinder = Part.makeCylinder(30, 50, App.Vector(100, 100, 0), UP)
    return imported(doc, Part.makeBox(200, 100, 50).cut(cylinder), name=name)


def placed(frame: Any, x: float, y: float, z: float, degrees: float) -> Any:
    """Placement local (x, y, z), tourné de ``degrees`` autour de Z, dans le repère ``frame``."""
    local = App.Placement(App.Vector(x, y, z), App.Rotation(UP, degrees))
    return frame.multiply(local)


def wood_at(doc: Any, size: tuple[float, float, float], where: Any, mark: str = "") -> Any:
    """Pièce de bois de chêne de cotes ``size`` au placement ``where``."""
    part = api.make_wood_part(*size, "chene", mark=mark, doc=doc)
    part.Placement = where
    doc.recompute()
    return part


def box_volume(part: Any) -> float:
    """Volume de la boîte d'encombrement de ``part``."""
    return float(part.Length.Value * part.Width.Value * part.Thickness.Value)


def machined_volume(part: Any) -> float:
    """Volume de la pièce usinée de ``part``."""
    return float(api.machined_part_of(part).Shape.Volume)


def twin_gains(doc: Any, host: Any, guest: Any, **params: object) -> tuple[float, float]:
    """Mêmes assemblage et mêmes pièces en pièces de bois (boîtes aux mêmes cotes et placements,
    décalées de ``SHIFT``) : volume ajouté (+) ou enlevé (-) à la boîte de l'hôte et de l'invitée.
    Le tenon-mortaise ne dépend que des boîtes : c'est ce que doit faire une pièce en bois dont la
    matière est là."""
    boxes = [
        wood_at(
            doc,
            (part.Length.Value, part.Width.Value, part.Thickness.Value),
            SHIFT.multiply(part.Placement),
        )
        for part in (host, guest)
    ]
    api.make_mortise_tenon(*boxes, **params)
    return tuple(machined_volume(box) - box_volume(box) for box in boxes)  # type: ignore[return-value]


def expected_volume(part: Any, gain: float) -> float:
    """Volume attendu de la pièce usinée de la pièce en bois ``part`` : sa forme plus ``gain``."""
    return float(part.Shape.Volume + gain)


def mixed_montage(doc: Any, scenario: Scenario, shaped_roles: tuple[bool, bool]) -> Montage:
    """Montage de référence de ``scenario`` dont l'hôte et/ou l'invitée (selon ``shaped_roles``)
    sont des pièces en bois qui ont la forme de la boîte : mêmes volumes attendus que le montage
    en pièces de bois."""
    parts = []
    for (size, pose), is_shaped, mark in zip(
        (scenario.host, scenario.guest), shaped_roles, ("H", "I"), strict=True
    ):
        if is_shaped:
            part = api.make_shaped_part(box(doc, size, f"Boite{mark}"), mark=mark)
            local = pose if isinstance(pose, App.Placement) else placement(*pose)
            part.Placement = FRAME.multiply(local)
            part.Label = mark
        else:
            part = wood(doc, mark, size, pose, FRAME)
        parts.append(part)
    doc.recompute()
    return assemble(scenario, *parts)
