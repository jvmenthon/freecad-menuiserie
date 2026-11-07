# SPDX-License-Identifier: LGPL-2.1-or-later
"""Arêtes de la finition des chants désignées dans la vue 3D (issue #5, C3, ADR 0029).

Une face, une arête ou un sommet de la pièce (brute ou usinée) désigne ses arêtes : la face
donne ses 4 arêtes, l'arête elle-même, le sommet les 3 arêtes du coin. On rapproche le centre
de l'élément de la boîte brute (:func:`~freecad.menuiserie.core.edges.edges_at`) ; seuls les
codes sont transmis. Lecture de la sélection à l'ouverture du panneau, puis un observateur de
sélection posé **seulement pendant que le panneau est ouvert** (ADR 0007, § 3 : rien de
permanent).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from freecad.menuiserie.core.edges import edges_at
from freecad.menuiserie.core.geometry import Vec3
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.machined_part import machined_part_of
from freecad.menuiserie.features.wood_part_record import dimensions_of

__all__ = ["EdgePicker", "selected_codes"]

_KINDS = ("Face", "Edge", "Vertex")


def _codes_of(part: DocumentObject, target: DocumentObject, sub: str) -> list[str]:
    """Codes des arêtes désignées par l'élément ``sub`` (``"Face3"``…) de ``target`` (la pièce
    ou sa pièce usinée) ; vide pour tout autre élément."""
    kind = sub.rstrip("0123456789")
    if kind not in _KINDS or target not in (part, machined_part_of(part)):
        return []
    element = target.Shape.getElement(sub)
    center = element.Point if kind == "Vertex" else element.CenterOfMass
    point = part.Placement.inverse().multVec(center)
    return [e.code for e in edges_at(dimensions_of(part), kind, Vec3(point.x, point.y, point.z))]


def selected_codes(part: DocumentObject) -> list[str]:
    """Codes des arêtes désignées par la sélection courante (faces, arêtes, sommets de ``part``),
    sans doublon, dans l'ordre de sélection."""
    codes: list[str] = []
    for item in Gui.Selection.getSelectionEx():
        for sub in item.SubElementNames:
            codes += [c for c in _codes_of(part, item.Object, sub) if c not in codes]
    return codes


class EdgePicker:
    """Observateur de sélection qui transmet les arêtes d'un élément cliqué de ``part``."""

    def __init__(self, part: DocumentObject, on_edges: Callable[[list[str]], None]) -> None:
        self._part_name: str = part.Name
        self._document_name: str = part.Document.Name
        self._on_edges = on_edges
        self._active = False

    @property
    def active(self) -> bool:
        """Vrai tant que l'observateur est posé."""
        return self._active

    def start(self) -> None:
        """Pose l'observateur (idempotent)."""
        if not self._active:
            Gui.Selection.addObserver(self)
            self._active = True

    def stop(self) -> None:
        """Retire l'observateur (idempotent)."""
        if self._active:
            self._active = False
            Gui.Selection.removeObserver(self)

    def addSelection(self, doc: str, obj: str, sub: str, pos: Any) -> None:
        """Rappel de FreeCAD : un élément a été sélectionné. Seul un élément de la pièce compte ;
        la sélection est alors vidée (la pièce n'est pas laissée en surbrillance) et les codes
        transmis hors du rappel."""
        del pos
        if not self._active or doc != self._document_name:
            return
        document = App.getDocument(self._document_name)
        part, target = document.getObject(self._part_name), document.getObject(obj)
        if part is None or target is None:
            return
        codes = _codes_of(part, target, sub)
        if codes:
            QtCore.QTimer.singleShot(0, lambda: self._deliver(codes))

    def _deliver(self, codes: list[str]) -> None:
        Gui.Selection.clearSelection()
        if self._active:
            self._on_edges(codes)
