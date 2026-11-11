# SPDX-License-Identifier: LGPL-2.1-or-later
"""Cibles de la finition des chants désignées dans la vue 3D (issue #5, C3, ADR 0029).

Une pièce (brute ou usinée), une face, une arête ou un sommet désigne la pièce et, selon
l'élément, des arêtes : une face donne ses 4 arêtes, une arête elle-même, un sommet les 3 arêtes
du coin ; une pièce seule ne désigne aucune arête. On rapproche le centre de l'élément de la
boîte brute (:func:`~freecad.menuiserie.core.edges.edges_at`) ; seuls les codes sont transmis.
Lecture de la sélection à l'ouverture du panneau, puis un observateur de sélection posé
**seulement pendant que le panneau est ouvert** (ADR 0007, § 3 : rien de permanent).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, NamedTuple

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from freecad.menuiserie.core.edges import edges_at, face_at
from freecad.menuiserie.core.geometry import Vec3
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.machined_part import is_machined_part
from freecad.menuiserie.features.wood_part import is_wood_part
from freecad.menuiserie.features.wood_part_record import dimensions_of

__all__ = ["EdgePicker", "Pick", "selected_pick"]

_KINDS = ("Face", "Edge", "Vertex")


class Pick(NamedTuple):
    """Cibles désignées : la pièce de bois (brute), les faces choisies (codes ``"Z+"``) et les
    codes d'arêtes qu'elles ou les arêtes et sommets choisis désignent."""

    part: DocumentObject
    faces: tuple[str, ...]
    codes: tuple[str, ...]


def _part_of(target: DocumentObject) -> DocumentObject | None:
    """Pièce de bois (brute) que ``target`` désigne : elle-même, ou la brute de sa pièce usinée."""
    if is_machined_part(target):
        target = target.Base
    return target if is_wood_part(target) else None


def _pick_of(target: DocumentObject, sub: str) -> Pick | None:
    """Cibles de l'élément ``sub`` (``"Face3"``, ``""`` pour la pièce entière) de ``target``."""
    part = _part_of(target)
    if part is None:
        return None
    kind = sub.rstrip("0123456789")
    if kind not in _KINDS:
        return Pick(part, (), ()) if not sub else None
    element = target.Shape.getElement(sub)
    center = element.Point if kind == "Vertex" else element.CenterOfMass
    local = part.Placement.inverse().multVec(center)
    point, dimensions = Vec3(local.x, local.y, local.z), dimensions_of(part)
    faces = (face_at(dimensions, point),) if kind == "Face" else ()
    return Pick(part, faces, tuple(e.code for e in edges_at(dimensions, kind, point)))


def selected_pick(part: DocumentObject | None = None) -> Pick | None:
    """Cibles de la sélection courante, fusionnées : la pièce est celle de ``part`` ou, sans elle,
    la première pièce de bois sélectionnée ; les éléments d'autres pièces sont ignorés."""
    merged: Pick | None = None if part is None else Pick(part, (), ())
    for item in Gui.Selection.getSelectionEx():
        for sub in item.SubElementNames or [""]:
            pick = _pick_of(item.Object, sub)
            if pick is None or (merged is not None and pick.part != merged.part):
                continue
            base = merged or Pick(pick.part, (), ())
            merged = Pick(
                base.part,
                base.faces + tuple(f for f in pick.faces if f not in base.faces),
                base.codes + tuple(c for c in pick.codes if c not in base.codes),
            )
    return merged


class EdgePicker:
    """Observateur de sélection qui transmet les cibles d'un élément cliqué : celles de ``part``
    ou, tant qu'elle est ``None``, de la première pièce de bois cliquée du document."""

    def __init__(
        self,
        document: App.Document,
        part: DocumentObject | None,
        on_pick: Callable[[Pick], None],
    ) -> None:
        self._document_name: str = document.Name
        self._part_name: str | None = None if part is None else part.Name
        self._on_pick = on_pick
        self._active = False

    @property
    def active(self) -> bool:
        """Vrai tant que l'observateur est posé."""
        return self._active

    def bind(self, part: DocumentObject) -> None:
        """Les clics suivants ne comptent que pour ``part``."""
        self._part_name = part.Name

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
        """Rappel de FreeCAD : un élément a été sélectionné. Seul un élément d'une pièce de bois
        compte ; la sélection est alors vidée (la pièce n'est pas laissée en surbrillance) et les
        cibles transmises hors du rappel."""
        del pos
        if not self._active or doc != self._document_name:
            return
        target = App.getDocument(self._document_name).getObject(obj)
        if target is None:
            return
        pick = _pick_of(target, sub)
        if pick is None or (self._part_name is not None and pick.part.Name != self._part_name):
            return
        QtCore.QTimer.singleShot(0, lambda: self._deliver(pick))

    def _deliver(self, pick: Pick) -> None:
        Gui.Selection.clearSelection()
        if self._active:
            self._on_pick(pick)
