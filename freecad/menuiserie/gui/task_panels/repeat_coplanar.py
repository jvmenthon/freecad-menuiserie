# SPDX-License-Identifier: LGPL-2.1-or-later
"""Faces coplanaires montrées par le panneau « Répéter » (jv, 2026-11-14, ADR 0058).

Les faces des copies au ras d'une face voisine (et ces voisines) sont tracées en magenta, comme
les guides aimantés du glissement, dans une incrustation de la vue 3D posée le temps du panneau.
Les voisines sont lues une fois, à la première copie ; rien n'est écrit dans le document.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any

import FreeCADGui as Gui

from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.repeat import copies_of
from freecad.menuiserie.features.repeat_coplanar import RepeatPlanes
from freecad.menuiserie.gui.drag.geometry import Drawing, guides_drawing
from freecad.menuiserie.gui.drag.overlay import Overlay
from freecad.menuiserie.gui.drag.parts import frame_of
from freecad.menuiserie.gui.task_panels.repeat_preview import copy_parts, shown_parts

__all__ = ["NODE_NAME", "CoplanarCues"]

NODE_NAME = "MenuiserieRepeatCoplanar"


def _scene_graph(doc_name: str) -> Any:
    """Racine Coin de la vue 3D du document, ``None`` sans vue 3D."""
    try:
        return Gui.getDocument(doc_name).ActiveView.getSceneGraph()
    except (AttributeError, RuntimeError, KeyError):
        return None


class CoplanarCues:
    """Incrustation des faces coplanaires des copies d'une répétition ; :meth:`close` la retire."""

    def __init__(self) -> None:
        self._planes: RepeatPlanes | None = None
        self._overlay: Overlay | None = None

    def show(
        self, repeat: DocumentObject | None, sources: Sequence[DocumentObject], axes: Iterable[int]
    ) -> None:
        """Faces des copies de ``repeat`` normales aux ``axes`` répétés (0, 1, 2) et coplanaires à
        une voisine ; rien sans répétition. Une erreur de lecture efface simplement le dessin."""
        if repeat is None or not sources:
            self.clear()
            return
        try:
            copies = copy_parts(repeat)
            if self._planes is None:
                excluded = [*copies_of(repeat), *copies, *shown_parts(sources)]
                self._planes = RepeatPlanes(sources, excluded)
            guides = self._planes.coplanar(copies, axes)
            strokes = guides_drawing(guides, frame_of(self._planes.origin))[0]
            self._draw(repeat.Document.Name, strokes)
        except Exception:  # repère visuel seulement : il ne doit jamais casser l'aperçu
            self.clear()

    def _draw(self, doc_name: str, strokes: Sequence[Any]) -> None:
        if not strokes:
            self.clear()
            return
        if self._overlay is None:
            root = _scene_graph(doc_name)
            if root is None:
                return
            self._overlay = Overlay(root, NODE_NAME)
        self._overlay.draw(Drawing(tuple(strokes)))

    def clear(self) -> None:
        """Retire le dessin (les voisines lues restent en mémoire pour la saisie suivante)."""
        overlay, self._overlay = self._overlay, None
        if overlay is not None:
            overlay.remove()

    def close(self) -> None:
        """Fin du panneau : dessin retiré, voisines oubliées."""
        self.clear()
        self._planes = None
