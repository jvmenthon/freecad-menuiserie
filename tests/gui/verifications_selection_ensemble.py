# SPDX-License-Identifier: LGPL-2.1-or-later
"""Vérifications d'interface de la sélection par ensemble dans la vue 3D (ADR 0047) : clic simple
(ensemble de plus haut niveau), double-clic (descente jusqu'à la pièce) et double-clic dans le
vide (remontée). Les évènements de souris ne sont pas envoyés (FreeCAD plante hors écran) : les
fonctions du filtre sont appelées avec le point écran de la pièce. Module importé par
``verifier_atelier.py``.
"""

from __future__ import annotations

from collections.abc import Callable

import FreeCADGui as Gui

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


def verifier_selection_par_ensemble() -> list[str]:
    """Clic simple, descente et remontée sur le bureau regroupé en ensemble."""
    return avec_bureau("VerifSelectionEnsemble", _selection_par_ensemble)


VERIFICATIONS_SELECTION_ENSEMBLE: tuple[Callable[[], list[str]], ...] = (
    verifier_selection_par_ensemble,
)
