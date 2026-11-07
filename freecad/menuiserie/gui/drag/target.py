# SPDX-License-Identifier: LGPL-2.1-or-later
"""Cible d'un glissement : pièce ou ensemble (EN-c, ADR 0038).

:class:`Target` (pattern Strategy) est ce que la session de glissement
(:class:`~freecad.menuiserie.gui.drag.session.DragSession`) et ses états demandent à l'objet qui
porte les flèches, les poignées et les anneaux : son repère, sa boîte, sa disposition, le début
d'un geste (Memento), les écritures et le relâchement. :class:`PartTarget` est la brute d'une
pièce, avec exactement le comportement d'avant l'ensemble (SM-c, RO-d) ; l'ensemble est
:class:`~freecad.menuiserie.gui.drag.furniture_target.FurnitureTarget`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, replace
from typing import Final

import FreeCAD as App

from freecad.menuiserie.core.geometry import Box, Vec3
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.magnet import Guide, Handle, ResizeResult
from freecad.menuiserie.core.snap import Frame
from freecad.menuiserie.features.drag_joints import JointChoice
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.furniture_container import guide_container
from freecad.menuiserie.features.furniture_drag_state import FurnitureMemento
from freecad.menuiserie.features.magnet_guides import collect_guides
from freecad.menuiserie.features.part_drag import (
    SIZE_PROPS,
    DragMemento,
    begin_drag,
    drag_limits,
    end_drag,
    move_part,
    resize_part,
    restore,
)
from freecad.menuiserie.features.part_rotate import end_rotation, rotate_by
from freecad.menuiserie.gui.drag.geometry import Layout, build_layout
from freecad.menuiserie.gui.drag.parts import box_of, frame_of, rings_of

__all__ = [
    "MOVE_TRANSACTION",
    "ROTATE_TRANSACTION",
    "Memento",
    "PartTarget",
    "Step",
    "Target",
]

MOVE_TRANSACTION: Final = QT_TRANSLATE_NOOP("Menuiserie", "Déplacer la pièce")
ROTATE_TRANSACTION: Final = QT_TRANSLATE_NOOP("Menuiserie", "Tourner la pièce")
Memento = DragMemento | FurnitureMemento


@dataclass(frozen=True)
class Step:
    """Résultat d'un pas de taille : cote **écrite** (mm) sur l'axe de la poignée et, si le pas
    est arrêté à la dernière valeur permise, le message (traduit) à montrer près de la souris."""

    size: float
    message: str = ""


class Target(ABC):
    """Objet que la session de glissement habille de flèches, de poignées et d'anneaux.

    ``obj`` porte le geste (la brute d'une pièce, un ensemble) ; ``resize_rate`` est la cadence
    maximale (par seconde) des recalculs pendant une poignée, ``min_size`` la cote minimale
    (mm) et ``shows_size`` dit si la cote tirée est écrite près de la souris."""

    resize_rate: int
    min_size: float
    shows_size: bool

    def __init__(self, obj: DocumentObject) -> None:
        self.obj = obj

    @property
    def document(self) -> App.Document:
        """Document de la cible."""
        return self.obj.Document

    @abstractmethod
    def transaction(self, kind: str) -> str:
        """Nom (à traduire) de la transaction du geste ``kind`` : ``"move"`` (flèche),
        ``"resize"`` (poignée) ou ``"rotate"`` (anneau)."""

    @abstractmethod
    def frame(self) -> Frame:
        """Repère (local vers global) de la boîte, d'après le placement actuel."""

    @abstractmethod
    def box(self) -> Box:
        """Boîte dans son repère, d'après les cotes actuelles."""

    @abstractmethod
    def layout(self, size_mm: float, panel_shown: bool) -> Layout:
        """Disposition (flèches de ``size_mm`` mm, poignées, anneaux) d'après l'état actuel ;
        ``panel_shown`` : le panneau de la cible est ouvert. ``ValueError`` si rien ne se
        dessine."""

    def center(self) -> Vec3:
        """Centre de la boîte, en coordonnées globales (échelle des flèches à l'écran)."""
        box = self.box()
        return self.frame().to_transform().apply(Vec3(*(box.center(i) for i in range(3))))

    @abstractmethod
    def begin(self) -> Memento:
        """Début du geste : état à garder (Memento), liaisons de l'atelier mises de côté."""

    @abstractmethod
    def guides(self) -> tuple[Guide, ...]:
        """Guides d'aimantation des objets voisins, dans le repère de la boîte."""

    @abstractmethod
    def move(self, memento: Memento, delta: Vec3) -> None:
        """Déplace de ``delta`` mm (repère de la boîte au début) depuis la position du début."""

    @abstractmethod
    def resize(self, memento: Memento, handle: Handle, result: ResizeResult) -> Step:
        """Écrit la cote ``result`` (face de ``handle``) depuis les cotes du début."""

    @abstractmethod
    def rotate(self, memento: Memento, axis: int, angle: float) -> bool:
        """Tourne de ``angle`` degrés autour de l'axe fixe ``axis`` depuis l'orientation du
        début ; faux, sans rien écrire, si la cible ne peut pas tourner."""

    @abstractmethod
    def restore(self, memento: Memento) -> None:
        """Échap : retour à l'état du début."""

    @abstractmethod
    def end_move(self, memento: Memento, choose: JointChoice) -> list[str]:
        """Relâchement d'une flèche ou d'une poignée : liaisons, recalcul, avertissements."""

    @abstractmethod
    def end_rotation(self, memento: Memento, choose: JointChoice) -> list[str]:
        """Relâchement d'un anneau."""


def _part(memento: Memento) -> DragMemento:
    if not isinstance(memento, DragMemento):
        raise TypeError("PartTarget : mémento d'une pièce attendu")
    return memento


class PartTarget(Target):
    """Brute d'une pièce : le comportement de la session avant l'ensemble (SM-c, RO-d)."""

    resize_rate = 30
    min_size = 1.0
    shows_size = False

    def transaction(self, kind: str) -> str:
        return ROTATE_TRANSACTION if kind == "rotate" else MOVE_TRANSACTION

    def frame(self) -> Frame:
        return frame_of(self.obj.getGlobalPlacement())

    def box(self) -> Box:
        return box_of(self.obj)

    def layout(self, size_mm: float, panel_shown: bool) -> Layout:
        limits = drag_limits(self.obj)
        resizable = limits.resizable_axes if panel_shown else frozenset()
        box = self.box()
        layout = build_layout(self.frame(), box, size_mm, limits.fixed_axes, resizable)
        return replace(layout, rings=rings_of(self.obj, box))

    def begin(self) -> Memento:
        return begin_drag(self.obj)

    def guides(self) -> tuple[Guide, ...]:
        return collect_guides(self.obj, guide_container(self.obj))

    def move(self, memento: Memento, delta: Vec3) -> None:
        move_part(_part(memento), delta)

    def resize(self, memento: Memento, handle: Handle, result: ResizeResult) -> Step:
        resize_part(_part(memento), SIZE_PROPS[handle.axis], result.size, result.origin_shift)
        return Step(result.size)

    def rotate(self, memento: Memento, axis: int, angle: float) -> bool:
        return rotate_by(_part(memento), axis, angle)

    def restore(self, memento: Memento) -> None:
        restore(_part(memento))

    def end_move(self, memento: Memento, choose: JointChoice) -> list[str]:
        return end_drag(_part(memento), choose)

    def end_rotation(self, memento: Memento, choose: JointChoice) -> list[str]:
        return end_rotation(_part(memento), choose)
