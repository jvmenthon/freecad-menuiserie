# SPDX-License-Identifier: LGPL-2.1-or-later
"""Attente des lignes cachées des vues TechDraw (issue #153, retour de jv du 2026-11-13).

Avec l'interface, TechDraw calcule la géométrie d'une vue (HLR) en tâche de fond : tant qu'elle
n'est pas prête, une cote posée sur un point de la vue fait planter FreeCAD. Les plans de
l'atelier attendent donc, en laissant tourner la boucle d'événements de Qt, que chaque vue ait
ses arêtes, au plus ``TIMEOUT_S`` secondes (au-delà, les cotes de détail sont omises).
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from typing import Final

from PySide import QtCore

from freecad.menuiserie.features import drawing_dims
from freecad.menuiserie.features.freecad_types import DocumentObject

__all__ = ["TIMEOUT_S", "install", "wait_for_views"]

TIMEOUT_S: Final = 20.0
_STEP_MS: Final = 50


def wait_for_views(views: Sequence[DocumentObject]) -> None:
    """Rend la main quand toutes les ``views`` ont leur géométrie, ou après ``TIMEOUT_S``."""
    deadline = time.monotonic() + TIMEOUT_S
    while not all(drawing_dims.has_geometry(view) for view in views):
        if time.monotonic() > deadline:
            return
        QtCore.QCoreApplication.processEvents()
        time.sleep(_STEP_MS / 1000)


def install() -> None:
    """Branche l'attente sur les plans de l'atelier (à l'enregistrement des commandes)."""
    drawing_dims.set_geometry_waiter(wait_for_views)
