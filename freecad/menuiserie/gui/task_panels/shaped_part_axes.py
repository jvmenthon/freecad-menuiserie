# SPDX-License-Identifier: LGPL-2.1-or-later
"""Repère de la pièce en bois dans la vue 3D pendant l'édition (D3) : le dessin de
:mod:`.shaped_part_drawing` (trièdre L / l / e et flèche du fil) posé dans la vue 3D de FreeCAD,
sous un nœud ``SoTransform`` qui suit le ``Placement`` global de la pièce.

Le nœud est propre au panneau (nommé :data:`NODE_NAME`), invisible pour la sélection, et
:meth:`AxesView.remove` le retire à la fermeture du panneau ; rien n'est écrit dans le document.
"""

from __future__ import annotations

from typing import Any, Final

import FreeCADGui as Gui
from pivy import coin

from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.gui.drag.overlay import Overlay
from freecad.menuiserie.gui.task_panels.shaped_part_drawing import axes_drawing, grain_axis

__all__ = ["NODE_NAME", "AxesView"]

NODE_NAME: Final = "MenuiserieShapedAxes"


class AxesView:
    """Repère d'une pièce en bois posé dans la vue 3D du document de la pièce ; inactif (sans
    effet) sans vue 3D. :meth:`refresh` le remet à la place et à la taille de la pièce."""

    def __init__(self, part: DocumentObject) -> None:
        self._part = part
        self._root: Any = None
        self._group: Any = None
        self._transform: Any = None
        self._overlay: Overlay | None = None
        root = _scene_graph(part)
        if root is None:
            return
        self._root = root
        self._group = coin.SoSeparator()
        self._transform = coin.SoTransform()
        self._group.addChild(self._transform)
        self._overlay = Overlay(self._group, NODE_NAME)
        root.addChild(self._group)
        self.refresh()

    @property
    def active(self) -> bool:
        """Vrai si le repère est posé dans une vue 3D."""
        return self._overlay is not None

    def refresh(self) -> None:
        """Place le repère sur la pièce (``Placement`` global) et le redessine d'après ses cotes
        et son sens du fil ; sans effet une fois retiré ou si la pièce a disparu."""
        overlay = self._overlay
        if overlay is None:
            return
        try:
            part = self._part
            placement = part.getGlobalPlacement()
            extents = (part.Length.Value, part.Width.Value, part.Thickness.Value)
            grain = grain_axis(str(part.GrainDirection))
        except (ReferenceError, RuntimeError, AttributeError):  # pièce supprimée du document
            return
        base, quaternion = placement.Base, placement.Rotation.Q
        self._transform.translation.setValue(base.x, base.y, base.z)
        self._transform.rotation.setValue(coin.SbRotation(*quaternion))
        overlay.draw(axes_drawing(extents, grain))

    def remove(self) -> None:
        """Retire le repère de la vue (sans effet s'il n'y est plus)."""
        overlay, self._overlay = self._overlay, None
        root, self._root = self._root, None
        if overlay is not None:
            overlay.remove()
        if root is not None and root.findChild(self._group) >= 0:
            root.removeChild(self._group)


def _scene_graph(part: DocumentObject) -> Any:
    """Racine Coin de la vue 3D du document de ``part``, ``None`` sans vue 3D."""
    try:
        view = Gui.getDocument(part.Document.Name).ActiveView
        return view.getSceneGraph()
    except (AttributeError, RuntimeError, KeyError):
        return None
