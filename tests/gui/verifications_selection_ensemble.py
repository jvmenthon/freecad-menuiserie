# SPDX-License-Identifier: LGPL-2.1-or-later
"""Vérifications d'interface de la sélection par ensemble dans la vue 3D (ADR 0048) : clic simple
(ensemble de plus haut niveau), double-clic (descente jusqu'à la pièce) et double-clic dans le
vide (remontée). Les évènements de souris ne sont pas envoyés (FreeCAD plante hors écran) : les
fonctions du filtre sont appelées avec le point écran de la pièce. Module importé par
``verifier_atelier.py``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import FreeCADGui as Gui
from PySide import QtCore, QtGui

from freecad.menuiserie.gui import click_select, double_click
from tests.gui.verifications_debit import avec_bureau
from tests.gui.verifications_double_clic import ATELIER, vue_3d_active
from tests.gui.verifications_panneau import ecarts
from tests.integration.bureau import Bureau


def _selection() -> list[str]:
    return [obj.Name for obj in Gui.Selection.getSelection()]


def _selection_par_ensemble(bureau: Bureau) -> list[str]:
    Gui.activateWorkbench(ATELIER)
    piece = bureau.shown("P")
    viewport = vue_3d_active(bureau.doc)
    view = Gui.activeView()
    if viewport is None or not hasattr(view, "getObjectInfo"):
        return ["vue 3D du document non active"]
    view.fitAll()
    x, y = (int(v) for v in view.getPointOnScreen(piece.Shape.BoundBox.Center))
    point = double_click.view_point(viewport, x, viewport.height() - 1 - y)
    ensemble = bureau.furniture.Name
    problemes = [
        *ecarts("filtre de sélection posé", click_select.installed(), True),
        *ecarts(
            "pièce sous le point",
            getattr(click_select.picked_object(view, point), "Name", ""),
            piece.Name,
        ),
    ]
    if problemes:
        return problemes
    # Clic simple : la sélection native (la pièce) est remplacée par l'ensemble.
    Gui.Selection.clearSelection()
    click_select.retarget_click(piece, None)
    problemes += ecarts("clic simple : l'ensemble", _selection(), [ensemble])
    click_select.retarget_click(piece, bureau.furniture)
    problemes += ecarts("clic simple dans l'ensemble : inchangé", _selection(), [ensemble])
    # Double-clic : descente jusqu'à la pièce, puis plus de changement (le panneau s'ouvre).
    problemes += ecarts("descente : consommé", click_select.descend_at(view, point), True)
    problemes += ecarts("descente : la pièce", _selection(), [piece.Name])
    problemes += ecarts(
        "pièce : double-clic non consommé", click_select.descend_at(view, point), False
    )
    problemes += ecarts("pièce : clic simple inchangé", _selection(), [piece.Name])
    # Double-clic dans le vide : remontée (la sélection native vide est remplacée par l'avant-clic).
    vide = (1, 1)
    problemes += ecarts("vide : consommé", click_select.descend_at(view, vide), True)
    problemes += ecarts("vide : l'ensemble", _selection(), [ensemble])
    problemes += ecarts("vide au sommet : inchangé", click_select.descend_at(view, vide), False)
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(bureau.doc.Name, piece.Name)
    Gui.Selection.clearSelection()
    problemes += ecarts(
        "vide après clic natif vide : repli avant-clic",
        click_select.descend_at(view, vide, bureau.parts["P"]),
        True,
    )
    problemes += ecarts("repli : l'ensemble", _selection(), [ensemble])
    Gui.Selection.clearSelection()
    return problemes


def _souris(viewport: Any, kind: Any, x: int, y: int) -> Any:
    """Évènement de souris gauche au point Qt ``(x, y)`` de la zone d'affichage (passé
    directement au filtre : FreeCAD plante hors écran sur les clics qu'il traite lui-même)."""
    buttons = (
        QtCore.Qt.NoButton if kind == QtCore.QEvent.MouseButtonRelease else QtCore.Qt.LeftButton
    )
    return QtGui.QMouseEvent(
        kind,
        QtCore.QPointF(x, y),
        QtCore.QPointF(viewport.mapToGlobal(QtCore.QPoint(x, y))),
        QtCore.Qt.LeftButton,
        buttons,
        QtCore.Qt.NoModifier,
    )


def _releve_du_double_clic(bureau: Bureau) -> list[str]:
    """Non-régression (jv, 2026-11-11) : le relâchement qui suit un double-clic consommé ne doit
    pas revenir à FreeCAD, qui resélectionnait le Std Part de l'ensemble."""
    Gui.activateWorkbench(ATELIER)
    piece = bureau.shown("P")
    viewport = vue_3d_active(bureau.doc)
    view = Gui.activeView()
    filtre = click_select.current_filter()
    if viewport is None or filtre is None:
        return ["vue 3D ou filtre de sélection absent"]
    view.fitAll()
    x, y = (int(v) for v in view.getPointOnScreen(piece.Shape.BoundBox.Center))
    qy = viewport.height() - 1 - y
    Gui.Selection.clearSelection()
    click_select.retarget_click(piece, None)  # clic simple : l'ensemble
    problemes = list(ecarts("clic simple : l'ensemble", _selection(), [bureau.furniture.Name]))
    filtre.swallow_release = False
    filtre.eventFilter(viewport, _souris(viewport, QtCore.QEvent.MouseButtonDblClick, x, qy))
    problemes += ecarts("double-clic : la pièce", _selection(), [piece.Name])
    problemes += ecarts("double-clic : relâchement à consommer", filtre.swallow_release, True)
    if not filtre.swallow_release:
        return problemes  # le relâchement irait à FreeCAD : plantage hors écran
    consomme = filtre.eventFilter(
        viewport, _souris(viewport, QtCore.QEvent.MouseButtonRelease, x, qy)
    )
    problemes += ecarts("relâchement consommé", consomme, True)
    problemes += ecarts("relâchement : la pièce reste", _selection(), [piece.Name])
    problemes += ecarts("relâchement suivant rendu", filtre.swallow_release, False)
    Gui.Selection.clearSelection()
    return problemes


def verifier_releve_du_double_clic() -> list[str]:
    """Le relâchement d'un double-clic de descente est consommé : la pièce reste sélectionnée."""
    return avec_bureau("VerifSelectionEnsembleReleve", _releve_du_double_clic)


def verifier_selection_par_ensemble() -> list[str]:
    """Clic simple, descente et remontée sur le bureau regroupé en ensemble."""
    return avec_bureau("VerifSelectionEnsemble", _selection_par_ensemble)


VERIFICATIONS_SELECTION_ENSEMBLE: tuple[Callable[[], list[str]], ...] = (
    verifier_selection_par_ensemble,
    verifier_releve_du_double_clic,
)
