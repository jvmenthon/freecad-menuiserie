# SPDX-License-Identifier: LGPL-2.1-or-later
"""Attente des lignes cachées des vues TechDraw (issue #153, retour de jv du 2026-11-13).

Avec l'interface, TechDraw calcule la géométrie d'une vue (HLR) en tâche de fond : tant qu'elle
n'est pas prête, une cote posée sur un point de la vue fait planter FreeCAD. Une commande de
plan donne donc à l'atelier une attente (``DrawingOptions.settle``) qui laisse tourner la boucle
d'événements de Qt, sans les saisies de l'utilisateur (la transaction du plan est ouverte), avec
le curseur d'attente, jusqu'à ce que chaque vue ait ses arêtes. Une seule échéance de
``TIMEOUT_S`` secondes vaut pour toute la commande : au-delà, les cotes sont omises et
l'utilisateur en est averti.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from typing import Final

from PySide import QtCore, QtGui

from freecad.menuiserie.features import drawing_dims
from freecad.menuiserie.features.freecad_types import DocumentObject

__all__ = ["TIMEOUT_S", "HlrWait"]

TIMEOUT_S: Final = 20.0
_STEP_S: Final = 0.05


class HlrWait:
    """Attente de la géométrie des vues pour une commande de plan (échéance commune)."""

    def __init__(self, timeout: float = TIMEOUT_S) -> None:
        self._deadline = time.monotonic() + timeout

    def __call__(self, views: Sequence[DocumentObject]) -> None:
        """Rend la main quand toutes les ``views`` ont leur géométrie, ou à l'échéance."""
        if all(drawing_dims.has_geometry(view) for view in views):
            return
        QtGui.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
        try:
            while not all(drawing_dims.has_geometry(view) for view in views):
                if time.monotonic() > self._deadline:
                    return
                QtCore.QCoreApplication.processEvents(QtCore.QEventLoop.ExcludeUserInputEvents)
                time.sleep(_STEP_S)
        finally:
            QtGui.QApplication.restoreOverrideCursor()
