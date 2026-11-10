# SPDX-License-Identifier: LGPL-2.1-or-later
"""Vérifications d'interface du panneau « Structure » (ADR 0046, lot 2) : rafraîchissement,
sélection dans les deux sens, double-clic, détachement des observateurs. Module importé par
``verifier_atelier.py`` (lancé par FreeCAD hors écran) ; chaque vérification renvoie la liste de
ses problèmes. Les minuteries à 0 ms sont exécutées par ``processEvents``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import FreeCADGui as Gui
from PySide import QtGui

from freecad.menuiserie.gui.structure_panel import DOCK_NAME, TREE_NAME, show_panel
from freecad.menuiserie.gui.structure_sync import StructureSync
from freecad.menuiserie.gui.structure_tree_widget import item_for, selected_keys
from tests.gui.verifications_debit import avec_bureau
from tests.gui.verifications_panneau import ecarts
from tests.integration.bureau import Bureau


def _traiter() -> None:
    for _ in range(3):
        QtGui.QApplication.processEvents()


def _panneau() -> tuple[Any, Any, StructureSync]:
    show_panel()
    _traiter()
    fenetre = Gui.getMainWindow()
    dock = fenetre.findChild(QtGui.QDockWidget, DOCK_NAME)
    return dock, dock.findChild(QtGui.QTreeWidget, TREE_NAME), dock.findChild(StructureSync)


def _noms_selectionnes() -> list[str]:
    return [objet.Name for objet in Gui.Selection.getSelection()]


def _avec_panneau(
    verification: Callable[[Bureau, Any, Any, StructureSync], list[str]],
) -> list[str]:
    def corps(bureau: Bureau) -> list[str]:
        dock, arbre, synchro = _panneau()
        try:
            return verification(bureau, dock, arbre, synchro)
        finally:
            Gui.Control.closeDialog()
            dock.hide()
            _traiter()

    return avec_bureau("structure", corps)


def _verifier_lignes_et_selection(
    bureau: Bureau, _dock: Any, arbre: Any, _synchro: StructureSync
) -> list[str]:
    piece = bureau.shown("P").Name
    ligne = item_for(arbre, piece)
    problemes = [] if ligne is not None else [f"aucune ligne pour {piece}"]
    if ligne is None:
        return problemes
    # panneau -> FreeCAD
    ligne.setSelected(True)
    _traiter()
    problemes += ecarts("clic sur une ligne", _noms_selectionnes(), [piece])
    # FreeCAD -> panneau, par la brute (une seule ligne pour la brute et la pièce usinée)
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(bureau.doc.Name, bureau.parts["JG"].Name)
    _traiter()
    problemes += ecarts("sélection côté FreeCAD", selected_keys(arbre), [bureau.shown("JG").Name])
    # pas de rétroaction : la sélection de FreeCAD n'a pas été remplacée
    problemes += ecarts("pas d'écho", _noms_selectionnes(), [bureau.parts["JG"].Name])
    Gui.Selection.clearSelection()
    _traiter()
    return problemes + ecarts("sélection vidée", selected_keys(arbre), [])


def _verifier_rafraichissement(
    bureau: Bureau, _dock: Any, arbre: Any, _synchro: StructureSync
) -> list[str]:
    piece = bureau.shown("P")
    bureau.parts["P"].Label = "Dessus de test"
    bureau.doc.recompute()
    _traiter()
    ligne = item_for(arbre, piece.Name)
    texte = ligne.text(0) if ligne is not None else None
    return ecarts("libellé suivi", texte, "Dessus de test")


def _verifier_double_clic(
    bureau: Bureau, _dock: Any, arbre: Any, _synchro: StructureSync
) -> list[str]:
    ligne = item_for(arbre, bureau.shown("P").Name)
    if ligne is None:
        return ["ligne du plateau absente"]
    arbre.itemDoubleClicked.emit(ligne, 0)
    _traiter()
    return ecarts("panneau de tâche ouvert", bool(Gui.Control.activeDialog()), True)


def _verifier_detachement(
    bureau: Bureau, dock: Any, arbre: Any, synchro: StructureSync
) -> list[str]:
    problemes = ecarts("observateurs posés", synchro.attached, True)
    dock.hide()
    _traiter()
    problemes += ecarts("observateurs retirés à la fermeture", synchro.attached, False)
    bureau.parts["P"].Label = "Après fermeture"
    _traiter()
    ligne = item_for(arbre, bureau.shown("P").Name)
    texte = ligne.text(0) if ligne is not None else None
    problemes += [] if texte != "Après fermeture" else ["panneau fermé mais encore mis à jour"]
    show_panel()
    _traiter()
    return problemes + ecarts("observateurs reposés", synchro.attached, True)


def verifier_structure_selection() -> list[str]:
    return _avec_panneau(_verifier_lignes_et_selection)


def verifier_structure_rafraichissement() -> list[str]:
    return _avec_panneau(_verifier_rafraichissement)


def verifier_structure_double_clic() -> list[str]:
    return _avec_panneau(_verifier_double_clic)


def verifier_structure_detachement() -> list[str]:
    return _avec_panneau(_verifier_detachement)


VERIFICATIONS_STRUCTURE: tuple[Callable[[], list[str]], ...] = (
    verifier_structure_selection,
    verifier_structure_rafraichissement,
    verifier_structure_double_clic,
    verifier_structure_detachement,
)
