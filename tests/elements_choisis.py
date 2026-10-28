# SPDX-License-Identifier: LGPL-2.1-or-later
"""Choix d'un élément (face, arête, sommet) d'un objet par sa position, pour les tests qui
sélectionnent des éléments sans clic de souris (intégration et interface).

Importable sans FreeCAD ; ``element_name`` demande FreeCAD (``Vector``) à l'appel.
"""

from __future__ import annotations

from typing import Any

Point = tuple[float, float, float]


def element_name(obj: Any, kind: str, near: Point) -> str:
    """Nom (``Face3``, ``Edge1``, ``Vertex5``) de l'élément de ``obj`` de type ``kind`` (``Face``,
    ``Edge`` ou ``Vertex``) dont le centre est le plus proche de ``near`` (coordonnées
    globales)."""
    import FreeCAD as App

    shape = obj.Shape
    elements = {"Face": shape.Faces, "Edge": shape.Edges, "Vertex": shape.Vertexes}[kind]
    target = App.Vector(*near)

    def distance(element: Any) -> float:
        centre = element.Point if kind == "Vertex" else element.CenterOfMass
        return float((centre - target).Length)

    return f"{kind}{elements.index(min(elements, key=distance)) + 1}"
