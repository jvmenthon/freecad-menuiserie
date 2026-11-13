# SPDX-License-Identifier: LGPL-2.1-or-later
"""Aligner deux faces : tourner puis plaquer une pièce (AL-b, ADR 0054).

:class:`FaceAlign` lit deux faces planes de deux objets (cibles de ``core/snap``), choisit la pièce
de l'atelier qui bouge (la brute, comme « Définir une distance » : ``DistanceMove``), calcule le
mouvement avec ``core/align`` et l'écrit dans le ``Placement`` de la brute par ``part_drag``
(membre d'ensemble relié ensuite, assemblages défaits proposés à l'appelant). Les objets des
autres ateliers ne bougent jamais (ADR 0007). Un ``Placement`` piloté par une formule refuse la
rotation. Aucun import de ``FreeCADGui`` ; la transaction est l'affaire de l'appelant.
"""

from __future__ import annotations

import math
from typing import Final

import FreeCAD as App

from freecad.menuiserie.core.align import NO_OFFSET, Alignment, AlignMode, align
from freecad.menuiserie.core.geometry import Vec3
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.snap import FaceTarget
from freecad.menuiserie.features.distance_move import moving_index_of, targets_of
from freecad.menuiserie.features.drag_joints import JointChoice
from freecad.menuiserie.features.freecad_types import DocumentObject, placement_expression
from freecad.menuiserie.features.i18n import translated, translated_errors
from freecad.menuiserie.features.part_drag import (
    DragMemento,
    begin_drag,
    end_drag,
    raw_part,
    restore,
    write_placement,
)
from freecad.menuiserie.features.picked import PickedElement

__all__ = ["FaceAlign", "global_motion"]

_NOT_FACES: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Choisissez deux faces (une sur chaque objet) pour les aligner."
)
_SAME_OBJECT: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Choisissez deux faces de deux objets différents."
)
_DRIVEN: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "« {label} » : sa position est pilotée par une formule, elle ne peut pas bouger."
)
_NOT_STARTED: Final = "begin() doit précéder preview() et finish()"
_FROM_ABOVE: Final = Vec3(0.0, 0.0, 1.0)


def global_motion(alignment: Alignment) -> App.Placement:
    """Le mouvement ``alignment`` en ``Placement`` global (rotation autour du pivot, puis shift)."""
    rows = alignment.rotation
    matrix = App.Matrix(*rows[0], 0.0, *rows[1], 0.0, *rows[2], 0.0, 0.0, 0.0, 0.0, 1.0)
    rotation = App.Placement(matrix).Rotation
    pivot = App.Vector(alignment.pivot.x, alignment.pivot.y, alignment.pivot.z)
    shift = App.Vector(alignment.shift.x, alignment.shift.y, alignment.shift.z)
    return App.Placement(pivot - rotation.multVec(pivot) + shift, rotation)


class FaceAlign:
    """Alignement de la face ``first`` (référence) et de la face ``second`` (celle de la pièce
    qui bouge par défaut). ``ValueError`` traduite si la sélection ne convient pas (pas deux
    faces planes, même objet, aucune pièce de l'atelier)."""

    def __init__(
        self,
        first: PickedElement,
        second: PickedElement,
        moving: PickedElement | None = None,
        toward_observer: Vec3 = _FROM_ABOVE,
    ) -> None:
        if not all(item.element.startswith("Face") for item in (first, second)):
            raise ValueError(translated(_NOT_FACES))
        self.elements = (first, second)
        if first.owner() == second.owner():
            raise ValueError(translated(_SAME_OBJECT))
        targets = targets_of(self.elements, toward_observer)
        self._faces = (targets[0], targets[1])
        if not all(isinstance(face, FaceTarget) for face in self._faces):
            raise ValueError(translated(_NOT_FACES))
        self.moving_index, self._pieces = moving_index_of(self.elements, moving)
        self._memento: DragMemento | None = None
        self._start: App.Placement | None = None
        if self._pieces[0] is not None and self._pieces[0] == self._pieces[1]:
            raise ValueError(translated(_SAME_OBJECT))

    @property
    def moving_part(self) -> DocumentObject:
        """Brute que l'alignement bouge."""
        part = self._pieces[self.moving_index]
        if part is None:  # exclu par moving_index_of
            raise ValueError(translated(_NOT_FACES))
        return part

    def plan(self, mode: AlignMode = AlignMode.AUTO, offset: Vec3 = NO_OFFSET) -> Alignment:
        """Le mouvement qui aligne (lecture seule). ``ValueError`` traduite si une face n'est pas
        plane."""
        fixed, moving = self._faces[1 - self.moving_index], self._faces[self.moving_index]
        if not (isinstance(fixed, FaceTarget) and isinstance(moving, FaceTarget)):
            raise ValueError(translated(_NOT_FACES))
        with translated_errors():
            return align(fixed, moving, mode, offset)

    @property
    def can_swap(self) -> bool:
        """Vrai si l'autre face est aussi celle d'une pièce de l'atelier (bouton Inverser)."""
        return self._pieces[1 - self.moving_index] is not None

    def swap(self) -> None:
        """Inverse la pièce pilotée et la pièce pilotante : la pièce déjà déplacée revient d'abord.
        Sans effet si l'autre face n'est pas d'une pièce de l'atelier."""
        if not self.can_swap:
            return
        self.cancel()
        self.moving_index = 1 - self.moving_index

    def begin(self) -> None:
        """Début d'une séance (panneau) : mémorise la brute et met de côté les liaisons d'un
        membre d'ensemble. ``ValueError`` traduite si son ``Placement`` est piloté par une
        formule."""
        self.cancel()
        raw = raw_part(self.moving_part)
        if placement_expression(raw) is not None:
            raise ValueError(translated(_DRIVEN, {"label": str(raw.Label)}))
        self._memento = begin_drag(raw)
        self._start = raw.getGlobalPlacement()

    def preview(self, mode: AlignMode = AlignMode.AUTO, offset: Vec3 = NO_OFFSET) -> Alignment:
        """Place la pièce d'après le début de la séance (écriture absolue, sans recalcul du
        document) et renvoie le mouvement. ``ValueError`` traduite si une face n'est pas plane."""
        memento, start = self._memento, self._start
        if memento is None or start is None:
            raise RuntimeError(_NOT_STARTED)
        alignment = self.plan(mode, offset)
        raw = memento.part
        container = start.multiply(memento.placement.inverse())
        placed = container.inverse().multiply(global_motion(alignment).multiply(start))
        if not all(math.isfinite(v) for v in (*placed.Base, *placed.Rotation.Q)):
            raise ValueError(translated(_NOT_FACES))
        write_placement(raw, placed)
        return alignment

    def finish(self, choose: JointChoice | None = None) -> list[str]:
        """Fin de la séance : relie l'ensemble, propose les assemblages défaits à ``choose`` et
        recalcule le document. Au moindre échec la pièce revient (``DragCancelledError``
        comprise) et l'erreur est relancée. Renvoie les avertissements."""
        memento, self._memento, self._start = self._memento, None, None
        if memento is None:
            raise RuntimeError(_NOT_STARTED)
        try:
            return end_drag(memento, choose)
        except BaseException:
            restore(memento)
            raise

    def cancel(self) -> None:
        """Remet la pièce où elle était au début (sans effet avant :meth:`begin`)."""
        if self._memento is not None:
            restore(self._memento)
        self._memento = None
        self._start = None

    def apply(
        self,
        mode: AlignMode = AlignMode.AUTO,
        choose: JointChoice | None = None,
        offset: Vec3 = NO_OFFSET,
    ) -> tuple[Alignment, list[str]]:
        """:meth:`begin`, :meth:`preview` puis :meth:`finish` d'un seul geste (script, ``api``) ;
        au moindre refus la pièce revient avant que l'erreur soit relancée."""
        self.plan(mode, offset)  # refus (face non plane) avant de toucher à la pièce
        self.begin()
        try:
            alignment = self.preview(mode, offset)
            return alignment, self.finish(choose)
        except BaseException:
            self.cancel()
            raise
