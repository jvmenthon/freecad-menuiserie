# SPDX-License-Identifier: LGPL-2.1-or-later
"""Objets et formes simulés pour les tests de la pièce en bois (sans FreeCAD)."""

from __future__ import annotations

import types
from typing import Any


class FakeSolid:
    """Solide simulé : volume, aire, inertie, centre de masse, validité."""

    def __init__(
        self,
        volume: float = 1000.0,
        *,
        valid: bool = True,
        inertia: tuple[float, float, float] = (1.0, 2.0, 3.0),
        center: tuple[float, float, float] = (5.0, 6.0, 7.0),
    ) -> None:
        self.Volume = volume
        self.Area = volume / 10.0
        self.valid = valid
        values = [0.0] * 16
        values[0], values[5], values[10] = inertia
        self.MatrixOfInertia = types.SimpleNamespace(A=values)
        self.CenterOfMass = types.SimpleNamespace(x=center[0], y=center[1], z=center[2])

    def isValid(self) -> bool:  # nom imposé par FreeCAD
        return self.valid


class FakeShape:
    """Forme simulée : copie, placement, solides, arêtes, fils."""

    def __init__(
        self,
        solids: tuple[FakeSolid, ...] = (),
        *,
        null: bool = False,
        edges: int = 0,
        wires: tuple[Any, ...] = (),
        z_length: float = 0.0,
    ) -> None:
        self.Solids = list(solids)
        self.null = null
        self.Edges = [object()] * edges
        self.Wires = list(wires)
        self.BoundBox = types.SimpleNamespace(ZLength=z_length)
        self.Placement: Any = None

    def isNull(self) -> bool:  # nom imposé par FreeCAD
        return self.null

    def copy(self) -> FakeShape:
        return self


class FakeWire:
    """Contour simulé, fermé ou non."""

    def __init__(self, closed: bool = True) -> None:
        self.closed = closed

    def isClosed(self) -> bool:  # nom imposé par FreeCAD
        return self.closed


class FakeSource:
    """Objet du document simulé : type, parents, forme, proxy."""

    def __init__(
        self,
        shape: FakeShape | None = None,
        *,
        type_id: str = "Part::Feature",
        derived: tuple[str, ...] = ("Part::Feature",),
        label: str = "Source",
        proxy: object | None = None,
        **links: Any,
    ) -> None:
        """``links`` : ``out_list`` (dépendances), ``geo_parent`` (conteneur géométrique) et
        ``group_parent`` (groupe)."""
        self.Shape = shape
        self.TypeId = type_id
        self.derived = derived
        self.Label = label
        self.OutList = list(links.get("out_list", ()))
        self.InList: list[Any] = []
        self.geo_parent = links.get("geo_parent")
        self.group_parent = links.get("group_parent")
        self.Visibility = True
        if proxy is not None:
            self.Proxy = proxy

    def isDerivedFrom(self, type_name: str) -> bool:  # nom imposé par FreeCAD
        return type_name in self.derived

    def getParentGeoFeatureGroup(self) -> Any:  # nom imposé par FreeCAD
        return self.geo_parent

    def getParentGroup(self) -> Any:  # nom imposé par FreeCAD
        return self.group_parent


def workshop_proxy(module: str = "freecad.menuiserie.features.wood_part") -> object:
    """Proxy d'un objet de l'atelier : sa classe vient de ``freecad.menuiserie``."""
    return type("Proxy", (), {"__module__": module})()


def body(shape: FakeShape, label: str = "Body") -> FakeSource:
    """Corps PartDesign simulé."""
    derived = ("PartDesign::Body", "Part::Feature")
    return FakeSource(shape, type_id="PartDesign::Body", derived=derived, label=label)


def sketch(shape: FakeShape, label: str = "Sketch") -> FakeSource:
    """Esquisse simulée."""
    derived = ("Sketcher::SketchObject", "Part::Part2DObject", "Part::Feature")
    return FakeSource(shape, type_id="Sketcher::SketchObject", derived=derived, label=label)
