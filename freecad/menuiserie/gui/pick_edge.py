# SPDX-License-Identifier: LGPL-2.1-or-later
"""Choix d'une arête dans la vue 3D pour la finition des chants (issue #5, C3, ADR 0029).

Un observateur de sélection est posé **seulement pendant que le bouton « Choisir dans la vue 3D »
est enfoncé**, puis retiré (ADR 0007, § 3 : rien de permanent). Un clic sur une arête de la pièce
(brute ou usinée) donne son milieu ; on le rapproche des douze arêtes de la boîte
(:func:`~freecad.menuiserie.core.edges.nearest_edge`) et seul le code est transmis.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from freecad.menuiserie.core.edges import nearest_edge
from freecad.menuiserie.core.geometry import Vec3
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.machined_part import machined_part_of
from freecad.menuiserie.features.wood_part_record import dimensions_of

__all__ = ["EdgePicker"]


class EdgePicker:
    """Observateur de sélection qui traduit un clic sur une arête de ``part`` en code d'arête."""

    def __init__(self, part: DocumentObject, on_edge: Callable[[str], None]) -> None:
        self._part_name: str = part.Name
        self._document_name: str = part.Document.Name
        self._on_edge = on_edge
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
        """Rappel de FreeCAD : un élément a été sélectionné. Seule une arête de la pièce compte ;
        la sélection est alors vidée (la pièce n'est pas laissée en surbrillance) et le code
        transmis hors du rappel."""
        del pos
        if not self._active or doc != self._document_name or not sub.startswith("Edge"):
            return
        code = self._code_of(obj, sub)
        if code is None:
            return
        QtCore.QTimer.singleShot(0, lambda: self._deliver(code))

    def _deliver(self, code: str) -> None:
        Gui.Selection.clearSelection()
        if self._active:
            self._on_edge(code)

    def _code_of(self, obj: str, sub: str) -> str | None:
        document = App.getDocument(self._document_name)
        part = document.getObject(self._part_name)
        target = document.getObject(obj)
        if part is None or target is None:
            return None
        if target not in (part, machined_part_of(part)):
            return None
        point = part.Placement.inverse().multVec(target.Shape.getElement(sub).CenterOfMass)
        return nearest_edge(dimensions_of(part), Vec3(point.x, point.y, point.z)).code
