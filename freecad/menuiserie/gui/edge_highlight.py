# SPDX-License-Identifier: LGPL-2.1-or-later
"""Mise en valeur, dans la vue 3D, des arêtes choisies du panneau « Finition des chants »
(issue #5).

Chaque pièce garde la couleur de sa carte : arêtes choisies en trait épais, faces dont les
quatre arêtes sont choisies teintées. Le dessin est une incrustation Coin (:class:`~freecad.
menuiserie.gui.drag.overlay.Overlay`) posée sur la vue pendant que le panneau est ouvert puis
retirée : rien n'est écrit dans le document ni dans son historique d'annulation, les couleurs des
pièces ne sont jamais modifiées.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Final

import FreeCAD as App
import FreeCADGui as Gui

from freecad.menuiserie.core.edges import (
    FACE_CODES,
    edge_ends,
    face_corners,
    loop_edges,
    parse_edge,
)
from freecad.menuiserie.core.geometry import Vec3
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.wood_part_record import dimensions_of
from freecad.menuiserie.gui.drag.geometry import Drawing, Solid, Stroke
from freecad.menuiserie.gui.drag.overlay import Overlay

__all__ = ["NODE_NAME", "EdgeHighlight", "highlight_drawing", "rgb"]

NODE_NAME: Final = "MenuiserieEdgeFinish"
_LINE_PX: Final = 5.0
_FACE_TRANSPARENCY: Final = 0.55
Color = tuple[float, float, float]


def rgb(color: str) -> Color:
    """Couleur ``"#rrggbb"`` en composantes de 0 à 1."""
    value = color.lstrip("#")
    red, green, blue = (int(value[i : i + 2], 16) / 255 for i in (0, 2, 4))
    return red, green, blue


def _to_global(part: DocumentObject) -> Any:
    placement = part.getGlobalPlacement()

    def convert(point: Vec3) -> Vec3:
        moved = placement.multVec(_vector(point))
        return Vec3(moved.x, moved.y, moved.z)

    return convert


def _vector(point: Vec3) -> Any:
    return App.Vector(point.x, point.y, point.z)


def highlight_drawing(entries: Sequence[tuple[DocumentObject, Sequence[str], str]]) -> Drawing:
    """Dessin des arêtes choisies ``(pièce, codes, couleur "#rrggbb")`` dans le repère global."""
    strokes: list[Stroke] = []
    solids: list[Solid] = []
    for part, codes, color in entries:
        if not codes:
            continue
        dimensions, convert, shade = dimensions_of(part), _to_global(part), rgb(color)
        chosen = set(codes)
        lines = tuple(
            tuple(convert(end) for end in edge_ends(dimensions, parse_edge(code))) for code in codes
        )
        strokes.append(Stroke(shade, _LINE_PX, lines))
        faces = tuple(
            tuple(convert(corner) for corner in face_corners(dimensions, face))
            for face in FACE_CODES
            if {edge.code for edge in loop_edges(face)} <= chosen
        )
        if faces:
            solids.append(Solid(shade, faces, _FACE_TRANSPARENCY))
    return Drawing(strokes=tuple(strokes), solids=tuple(solids))


class EdgeHighlight:
    """Incrustation de la vue du document ``document``, posée au premier dessin, retirée par
    :meth:`remove`."""

    def __init__(self, document: Any) -> None:
        self._document_name: str = document.Name
        self._overlay: Any = None

    def show(self, entries: Sequence[tuple[DocumentObject, Sequence[str], str]]) -> None:
        """Remplace la mise en valeur par celle de ``entries`` (sans vue 3D : rien)."""
        if self._overlay is None:
            root = _scene_graph(self._document_name)
            if root is None:
                return
            self._overlay = Overlay(root, NODE_NAME)
        self._overlay.draw(highlight_drawing(entries))

    def remove(self) -> None:
        """Retire l'incrustation (idempotent)."""
        overlay, self._overlay = self._overlay, None
        if overlay is not None:
            overlay.remove()


def _scene_graph(document_name: str) -> Any:
    """Racine Coin de la vue 3D active du document, ``None`` sans vue 3D."""
    gui_document = Gui.getDocument(document_name)
    view = None if gui_document is None else gui_document.ActiveView
    if view is None or not hasattr(view, "getSceneGraph"):
        return None
    return view.getSceneGraph()
