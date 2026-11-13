# SPDX-License-Identifier: LGPL-2.1-or-later
"""Ensemble comme cible d'un glissement (EN-c, ADR 0038, critères C1 à C3).

:class:`FurnitureTarget` habille l'ensemble sélectionné seul (ou dont le panneau est ouvert) de sa
boîte en transparence, de six doubles flèches de face (taille), de trois flèches de déplacement
et de trois anneaux de rotation. Les écritures viennent de ``features/furniture_drag`` : la
taille par ``resize_furniture_to`` (brutes seules, cote refusée = arrêt à la dernière valeur
permise), le déplacement et la rotation par le ``Placement`` du Std Part propre à l'ensemble.
Sans Std Part propre (ancien document, Std Part partagé, formule de l'utilisateur sur son
placement), ni flèches de déplacement ni anneaux : les faces avant, gauche et basse sont refusées
par la taille avec le message de ``turn_refusal``. Un sous-ensemble lié par son parent garde
flèches et anneaux : le geste met ses liaisons de côté et le parent les repose au relâchement.
"""

from __future__ import annotations

from itertools import product
from typing import Final

import FreeCAD as App

from freecad.menuiserie.core.furniture import MIN_FURNITURE_MM, furniture_layout, resized_by
from freecad.menuiserie.core.geometry import Box, Matrix3, Vec3
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.magnet import Guide, Handle, ResizeResult
from freecad.menuiserie.core.rotation import Ring
from freecad.menuiserie.core.snap import Frame
from freecad.menuiserie.features.drag_joints import JointChoice
from freecad.menuiserie.features.freecad_types import expressions_of
from freecad.menuiserie.features.furniture_bindings import workshop_expressions
from freecad.menuiserie.features.furniture_container import guide_container, own_std_part
from freecad.menuiserie.features.furniture_drag import (
    FurnitureMemento,
    begin_furniture_drag,
    end_furniture_drag,
    furniture_box,
    furniture_frame,
    furniture_placement,
    move_furniture_by,
    resize_furniture_to,
    restore,
    rotate_furniture_by,
)
from freecad.menuiserie.features.magnet_guides import collect_guides, neighbor_rotations
from freecad.menuiserie.features.solids import rigid_transform
from freecad.menuiserie.gui.drag.geometry import HANDLE_RATIO, Layout
from freecad.menuiserie.gui.drag.rings import build_rings
from freecad.menuiserie.gui.drag.target import Memento, Step, Target

__all__ = [
    "MOVE_TRANSACTION",
    "RESIZE_TRANSACTION",
    "ROTATE_TRANSACTION",
    "FurnitureTarget",
]

MOVE_TRANSACTION: Final = QT_TRANSLATE_NOOP("Menuiserie", "Déplacer l'ensemble")
RESIZE_TRANSACTION: Final = QT_TRANSLATE_NOOP("Menuiserie", "Redimensionner l'ensemble")
ROTATE_TRANSACTION: Final = QT_TRANSLATE_NOOP("Menuiserie", "Tourner l'ensemble")
_NAMES: Final = {
    "move": MOVE_TRANSACTION,
    "resize": RESIZE_TRANSACTION,
    "rotate": ROTATE_TRANSACTION,
}
_NO_VOLUME: Final = "FurnitureTarget : ensemble sans volume, rien à dessiner"


def _furniture(memento: Memento) -> FurnitureMemento:
    if not isinstance(memento, FurnitureMemento):
        raise TypeError("FurnitureTarget : mémento d'un ensemble attendu")
    return memento


class FurnitureTarget(Target):
    """Un ensemble (``Furniture``) : boîte ``Origin`` à ``Origin`` + cotes, dans le repère de son
    Std Part."""

    resize_rate = 10  # les brutes de tout l'ensemble sont recalculées : 10 Hz au plus (B2)
    min_size = MIN_FURNITURE_MM
    shows_size = True

    def transaction(self, kind: str) -> str:
        return _NAMES[kind]

    def frame(self) -> Frame:
        return furniture_frame(self.obj)

    def box(self) -> Box:
        return furniture_box(self.obj)

    def _rings(self, box: Box) -> tuple[Ring, ...]:
        """Anneaux autour des axes fixes du conteneur du Std Part propre (comme la pièce, B5)."""
        part = own_std_part(self.obj)
        if part is None:
            return ()
        container = part.getGlobalPlacement() * part.Placement.inverse()
        return build_rings(box, rigid_transform(part.Placement), rigid_transform(container))

    def _free(self) -> bool:
        """Vrai si l'ensemble a un Std Part propre dont aucune formule de l'utilisateur ne pilote le
        ``Placement`` : flèches et anneaux sont proposés. Les liaisons de l'atelier d'un
        sous-ensemble ne comptent pas : le geste les met de côté et le parent les repose (B5)."""
        part = own_std_part(self.obj)
        if part is None:
            return False
        workshop = workshop_expressions(self.obj)
        return all(
            path.split(".")[0] != "Placement" or path in workshop for path in expressions_of(part)
        )

    def layout(self, size_mm: float, panel_shown: bool) -> Layout:
        del panel_shown  # les poignées sont là dès la sélection
        frame, box = self.frame(), self.box()
        found = furniture_layout(box, frame, size_mm)
        # is_empty est une propriété : faux positif de Semgrep (méthode non appelée).
        # nosemgrep: python.lang.maintainability.is-function-without-parentheses
        if found.is_empty:
            raise ValueError(_NO_VOLUME)
        free = self._free()
        return Layout(
            frame,
            box,
            found.arrows if free else (),
            tuple((handle.handle, handle.point) for handle in found.handles),
            HANDLE_RATIO * size_mm,
            self._rings(box) if free else (),
            double_handles=True,
            shows_box=True,
        )

    def begin(self) -> Memento:
        return begin_furniture_drag(self.obj)

    def guides(self) -> tuple[Guide, ...]:
        """Objets voisins : tout ce qui n'est pas dans le Std Part de l'ensemble (ses pièces ne le
        guident pas)."""
        box, to_global = self.box(), self.frame().to_transform()
        reference = App.BoundBox()
        for bits in product((0, 1), repeat=3):
            point = to_global.apply(Vec3.of([(box.lo(i), box.hi(i))[bits[i]] for i in range(3)]))
            reference.add(App.Vector(point.x, point.y, point.z))
        skip = {self.obj.Name}
        part = self.obj.getParentGeoFeatureGroup()
        if part is not None:
            skip.add(part.Name)
        return collect_guides(
            self.obj,
            guide_container(self.obj),
            origin=furniture_placement(self.obj),
            skip=skip,
            reference=reference,
        )

    def neighbor_rotations(self) -> tuple[Matrix3, ...]:
        skip = {self.obj.Name}
        part = self.obj.getParentGeoFeatureGroup()
        if part is not None:
            skip.add(part.Name)
        return neighbor_rotations(self.obj, guide_container(self.obj), skip)

    def move(self, memento: Memento, delta: Vec3) -> None:
        move_furniture_by(_furniture(memento), delta)

    def resize(self, memento: Memento, handle: Handle, result: ResizeResult) -> Step:
        found = _furniture(memento)
        step = resize_furniture_to(found, resized_by(found.box, handle, result))
        return Step(step.box.size(handle.axis), step.message)

    def rotate(self, memento: Memento, axis: int, angle: float) -> bool:
        return rotate_furniture_by(_furniture(memento), axis, angle)

    def restore(self, memento: Memento) -> None:
        restore(_furniture(memento))

    def end_move(self, memento: Memento, choose: JointChoice) -> list[str]:
        del choose  # pas d'assemblage à défaire : l'ensemble garde ses pièces
        return end_furniture_drag(_furniture(memento))

    def end_rotation(self, memento: Memento, choose: JointChoice) -> list[str]:
        return self.end_move(memento, choose)
