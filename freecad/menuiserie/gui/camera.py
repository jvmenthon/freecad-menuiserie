# SPDX-License-Identifier: LGPL-2.1-or-later
"""Conservation de la caméra de la vue 3D pendant une création (planche, ensemble).

FreeCAD recadre parfois la vue quand un objet apparaît. La vue de l'utilisateur est rétablie
aussitôt après la création et encore une fois à la fin de la boucle d'événements (le recadrage
peut être différé), sauf pour la première création d'un document vide : le recadrage de FreeCAD
reste alors utile.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager, suppress
from typing import Any

import FreeCADGui as Gui
from PySide import QtCore

from freecad.menuiserie.features.freecad_types import Document

__all__ = ["keep_camera"]


def _view_3d() -> Any | None:
    """Vue 3D active, ``None`` s'il n'y en a pas (feuille de calcul, page d'accueil…)."""
    view = Gui.activeView()
    if view is None or not hasattr(view, "getCamera") or not hasattr(view, "setCamera"):
        return None
    return view


def _restore(view: Any, camera: str) -> None:
    with suppress(RuntimeError, ReferenceError):  # vue fermée entre-temps
        view.setCamera(camera)


@contextmanager
def keep_camera(doc: Document) -> Iterator[None]:
    """Rétablit la caméra de la vue active à la sortie, sauf si ``doc`` était vide (première
    planche ou premier ensemble : le cadrage de FreeCAD est conservé)."""
    view = _view_3d()
    if view is None or not doc.Objects:
        yield
        return
    camera = view.getCamera()
    try:
        yield
    finally:
        _restore(view, camera)
        QtCore.QTimer.singleShot(0, lambda: _restore(view, camera))
