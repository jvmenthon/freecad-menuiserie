# SPDX-License-Identifier: LGPL-2.1-or-later
"""Incrustation Coin des flèches, poignées et guides aimantés (SM-c, ADR 0021).

Un seul nœud (``SoAnnotation`` nommé :data:`NODE_NAME`) est posé sur la racine de la vue puis
retiré ; rien n'est écrit dans le document. Il est invisible pour la sélection de FreeCAD
(``SoPickStyle.UNPICKABLE``). C'est le seul module du glissement qui importe pivy.
"""

from __future__ import annotations

from typing import Any, Final

from pivy import coin

from freecad.menuiserie.gui.drag.geometry import Dots, Drawing, Solid, Stroke

__all__ = ["NODE_NAME", "Overlay"]

NODE_NAME: Final = "MenuiserieDrag"
SoNode = Any


def _stroke_node(stroke: Stroke) -> SoNode:
    node = coin.SoSeparator()
    color = coin.SoBaseColor()
    color.rgb.setValue(*stroke.color)
    style = coin.SoDrawStyle()
    style.lineWidth = stroke.width
    points = [p for line in stroke.lines for p in line]
    coordinates = coin.SoCoordinate3()
    coordinates.point.setValues(0, len(points), [(p.x, p.y, p.z) for p in points])
    lines = coin.SoLineSet()
    lines.numVertices.setValues(0, len(stroke.lines), [len(line) for line in stroke.lines])
    for child in (color, style, coordinates, lines):
        node.addChild(child)
    return node


def _dots_node(dots: Dots) -> SoNode:
    node = coin.SoSeparator()
    color = coin.SoBaseColor()
    color.rgb.setValue(*dots.color)
    style = coin.SoDrawStyle()
    style.pointSize = dots.size
    coordinates = coin.SoCoordinate3()
    coordinates.point.setValues(0, len(dots.points), [(p.x, p.y, p.z) for p in dots.points])
    for child in (color, style, coordinates, coin.SoPointSet()):
        node.addChild(child)
    return node


def _solid_node(solid: Solid) -> SoNode:
    node = coin.SoSeparator()
    color = coin.SoBaseColor()
    color.rgb.setValue(*solid.color)
    points = [p for face in solid.faces for p in face]
    coordinates = coin.SoCoordinate3()
    coordinates.point.setValues(0, len(points), [(p.x, p.y, p.z) for p in points])
    faces = coin.SoFaceSet()
    faces.numVertices.setValues(0, len(solid.faces), [len(face) for face in solid.faces])
    for child in (color, coordinates, faces):
        node.addChild(child)
    return node


class Overlay:
    """Incrustation posée sur la racine ``root`` d'une vue 3D (ou sur un nœud qui la place, comme
    le repère de la pièce en bois) ; son nœud porte le nom ``name`` ; :meth:`remove` la retire."""

    def __init__(self, root: SoNode, name: str = NODE_NAME) -> None:
        self._root: SoNode | None = root
        self._node = coin.SoAnnotation()
        self._node.setName(name)
        pick = coin.SoPickStyle()
        pick.style = coin.SoPickStyle.UNPICKABLE
        light = coin.SoLightModel()
        light.model = coin.SoLightModel.BASE_COLOR
        self._node.addChild(pick)
        self._node.addChild(light)
        root.addChild(self._node)

    def draw(self, drawing: Drawing) -> None:
        """Remplace le dessin par ``drawing``."""
        while self._node.getNumChildren() > 2:
            self._node.removeChild(2)
        for stroke in drawing.strokes:
            self._node.addChild(_stroke_node(stroke))
        for dots in drawing.dots:
            self._node.addChild(_dots_node(dots))
        for solid in drawing.solids:
            self._node.addChild(_solid_node(solid))

    def remove(self) -> None:
        """Retire l'incrustation de la vue (sans effet si elle n'y est plus)."""
        root, self._root = self._root, None
        if root is not None and root.findChild(self._node) >= 0:
            root.removeChild(self._node)

    def shows(self) -> bool:
        """Vrai si l'incrustation est posée et porte un dessin."""
        return self._root is not None and self._node.getNumChildren() > 2
