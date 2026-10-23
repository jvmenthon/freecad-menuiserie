# SPDX-License-Identifier: LGPL-2.1-or-later
"""Vérifications d'interface du double-clic (issue #76, ADR 0018) : dans la vue 3D, il ouvre le
panneau de l'objet de l'atelier sous le curseur, seulement quand l'atelier est actif ; sur la
liste de débit vivante, il ouvre l'aperçu sur la portée de la liste, sans modifier le document,
et ne fait rien tant qu'un panneau de tâche est ouvert. Module importé par ``verifier_atelier.py``
(lancé par FreeCAD hors écran).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import FreeCADGui as Gui
from PySide import QtCore, QtGui

from tests.gui.verifications_assemblages import selectionner
from tests.gui.verifications_debit import (
    LISTE,
    avec_bureau,
    etat_du_document,
    fermer_les_apercus,
    widgets_apercu,
)
from tests.gui.verifications_panneau import (
    annuler,
    avec_document,
    ecarts,
    formulaire,
    piece_validee,
)
from tests.gui.verifications_panneau_ensemble import ouvrir
from tests.integration.bureau import Bureau

ATELIER = "MenuiserieWorkbench"
AUCUN_ATELIER = "NoneWorkbench"


def double_clic_3d(view: Any, x: int, y: int) -> bool:
    """Curseur placé au point ``(x, y)`` de la vue (coordonnées de FreeCAD, origine en bas à
    gauche) puis double-clic gauche envoyé à sa zone d'affichage ; vrai si un panneau s'ouvre."""
    viewport = view.graphicsView().viewport()
    point = QtCore.QPoint(x, viewport.height() - 1 - y)
    QtGui.QCursor.setPos(viewport.mapToGlobal(point))
    QtGui.QApplication.processEvents()
    evenement = QtGui.QMouseEvent(
        QtCore.QEvent.MouseButtonDblClick,
        QtCore.QPointF(point),
        QtCore.Qt.LeftButton,
        QtCore.Qt.LeftButton,
        QtCore.Qt.NoModifier,
    )
    QtGui.QApplication.sendEvent(viewport, evenement)
    QtGui.QApplication.processEvents()
    return bool(Gui.Control.activeDialog())


def _double_clic_dans_la_vue(doc: Any) -> list[str]:
    piece = piece_validee(doc)
    view = Gui.activeView()
    view.viewIsometric()
    view.fitAll()
    Gui.updateGui()
    x, y = (int(v) for v in view.getPointOnScreen(piece.Shape.BoundBox.Center))
    info = view.getObjectInfo((x, y)) or {}
    problemes = ecarts("pièce sous le point", info.get("Object"), piece.Name)
    problemes += ecarts("vide : aucun panneau", double_clic_3d(view, 1, 1), False)
    ouvert = double_clic_3d(view, x, y)
    problemes += ecarts("pièce : panneau ouvert", ouvert, True)
    problemes += ecarts("pièce : son formulaire", formulaire() is not None, True)
    if ouvert:
        annuler()
    Gui.activateWorkbench(AUCUN_ATELIER)
    try:
        problemes += ecarts("atelier quitté : aucun panneau", double_clic_3d(view, x, y), False)
    finally:
        if Gui.Control.activeDialog():
            annuler()
        Gui.activateWorkbench(ATELIER)
    return problemes


def verifier_double_clic_dans_la_vue_3d() -> list[str]:
    """Double-clic sur la pièce dans la vue 3D : son panneau ; dans le vide : rien ; atelier
    quitté : rien (le filtre est retiré)."""
    return avec_document("VerifDoubleClic3D", _double_clic_dans_la_vue)


def liste_vivante(bureau: Bureau) -> Any:
    """Objet ``CutList`` créé par la commande « Liste de débit » (``None`` s'il manque)."""
    Gui.Command.get(LISTE).run()
    return bureau.doc.getObject("CutList")


def double_clic(obj: Any) -> bool:
    vobj = obj.ViewObject
    return bool(vobj.Proxy.doubleClicked(vobj))


def _apercu_au_double_clic(bureau: Bureau) -> list[str]:
    doc = bureau.doc
    selectionner(bureau.shown("V"))
    liste = liste_vivante(bureau)
    if liste is None:
        return ["liste vivante absente"]
    Gui.Selection.clearSelection()  # la portée vient de la liste, pas de la sélection
    doc.clearUndos()
    avant = etat_du_document(doc)
    accepte = double_clic(liste)
    trouves = widgets_apercu()
    texte = trouves["navigateur"].toPlainText() if "navigateur" in trouves else ""
    problemes = [
        *ecarts("double-clic accepté", accepte, True),
        *ecarts("aperçu ouvert", "fenetre" in trouves, True),
        *ecarts("portée de la liste : voile", "Voile" in texte, True),
        *ecarts("portée de la liste : plateau absent", "Plateau" in texte, False),
        *ecarts("document inchangé", etat_du_document(doc), avant),
    ]
    del trouves
    fermer_les_apercus()
    return problemes


def verifier_apercu_au_double_clic() -> list[str]:
    """Double-clic sur la liste vivante : aperçu limité à sa portée (ici le voile choisi à la
    création), document et sélection inchangés."""
    return avec_bureau("VerifDoubleClicListe", _apercu_au_double_clic)


def _double_clic_pendant_un_panneau(bureau: Bureau) -> list[str]:
    liste = liste_vivante(bureau)
    if liste is None:
        return ["liste vivante absente"]
    if ouvrir(bureau.furniture) is None:
        return ["panneau de l'ensemble non ouvert"]
    accepte = double_clic(liste)
    problemes = [
        *ecarts("double-clic refusé", accepte, False),
        *ecarts("aucun aperçu", "fenetre" in widgets_apercu(), False),
    ]
    annuler()
    fermer_les_apercus()
    return problemes


def verifier_double_clic_pendant_un_panneau() -> list[str]:
    """Un panneau de tâche est ouvert : le double-clic sur la liste ne fait rien (le recalcul de
    l'aperçu validerait la transaction du panneau)."""
    return avec_bureau("VerifDoubleClicListePanneau", _double_clic_pendant_un_panneau)


VERIFICATIONS_DOUBLE_CLIC: tuple[Callable[[], list[str]], ...] = (
    verifier_double_clic_dans_la_vue_3d,
    verifier_apercu_au_double_clic,
    verifier_double_clic_pendant_un_panneau,
)
