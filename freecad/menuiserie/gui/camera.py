# SPDX-License-Identifier: LGPL-2.1-or-later
"""Cadrage de la vue 3D après la création d'une pièce ou d'un ensemble.

FreeCAD recadre parfois la vue de façon imprévisible quand un objet apparaît (zoom excessif sur
un objet encore vide, déplacement). Une fois la création faite, toute la vue est recadrée sur le
contenu du document pour inclure la nouvelle pièce, sans changer l'orientation de la caméra ;
le recadrage est refait à la fin de la boucle d'événements (celui de FreeCAD peut être différé).
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager, suppress
from typing import Any

import FreeCADGui as Gui
from PySide import QtCore

__all__ = ["frame_view"]


def _view_3d() -> Any | None:
    """Vue 3D active, ``None`` s'il n'y en a pas (feuille de calcul, page d'accueil…)."""
    view = Gui.activeView()
    return view if view is not None and hasattr(view, "fitAll") else None


def _fit(view: Any) -> None:
    with suppress(RuntimeError, ReferenceError):  # vue fermée entre-temps
        view.fitAll()


@contextmanager
def frame_view() -> Iterator[None]:
    """Recadre la vue active sur tout son contenu à la sortie (orientation conservée)."""
    view = _view_3d()
    try:
        yield
    finally:
        if view is not None:
            _fit(view)
            QtCore.QTimer.singleShot(0, lambda: _fit(view))
