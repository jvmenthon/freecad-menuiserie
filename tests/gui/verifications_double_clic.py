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

from freecad.menuiserie.gui import double_click
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


def vue_3d_active(doc: Any) -> Any:
    """Sous-fenêtre de la vue 3D de ``doc`` (titre « <document> : 1 ») rendue active, puis sa
    zone d'affichage ; hors écran, la page d'accueil peut s'ouvrir par-dessus. (Dans
    l'interface, le clic dans une vue la rend active.)"""
    QtGui.QApplication.processEvents()  # page d'accueil éventuelle ouverte d'abord
    mdi = Gui.getMainWindow().findChild(QtGui.QMdiArea)
    for fenetre in mdi.subWindowList():
        if fenetre.windowTitle().startswith(f"{doc.Label} :"):
            mdi.setActiveSubWindow(fenetre)
    zones = double_click.viewports_3d(mdi, current_only=True)
    return zones[0] if zones else None


def double_clic_envoye(viewport: Any, x: int, y: int) -> bool:
    """Double-clic gauche envoyé au point Qt ``(x, y)`` de la zone d'affichage (sans bouger le
    curseur) ; vrai si un panneau s'ouvre. Seulement quand le filtre doit le consommer : hors
    écran, FreeCAD plante en traitant lui-même un clic ou un mouvement de souris (le cube de
    navigation exige un contexte OpenGL)."""
    evenement = QtGui.QMouseEvent(
        QtCore.QEvent.MouseButtonDblClick,
        QtCore.QPointF(x, y),
        QtCore.QPointF(viewport.mapToGlobal(QtCore.QPoint(x, y))),
        QtCore.Qt.LeftButton,
        QtCore.Qt.LeftButton,
        QtCore.Qt.NoModifier,
    )
    QtGui.QApplication.sendEvent(viewport, evenement)
    QtGui.QApplication.processEvents()
    return bool(Gui.Control.activeDialog())


def _double_clic_dans_la_vue(doc: Any) -> list[str]:
    # Une vérification précédente a pu changer d'atelier (feuille de calcul ouverte…).
    Gui.activateWorkbench(ATELIER)
    piece = piece_validee(doc)
    viewport = vue_3d_active(doc)
    view = Gui.activeView()
    if viewport is None or not hasattr(view, "getObjectInfo"):
        return ["vue 3D du document non active"]
    view.fitAll()
    x, y = (int(v) for v in view.getPointOnScreen(piece.Shape.BoundBox.Center))
    qx, qy = x, viewport.height() - 1 - y  # rapport de pixels 1 hors écran
    info = view.getObjectInfo(double_click.view_point(viewport, qx, qy)) or {}
    problemes = [
        *ecarts("conversion du point", double_click.view_point(viewport, qx, qy), (x, y)),
        *ecarts("pièce sous le point", info.get("Object"), piece.Name),
        *ecarts("vide : rien", double_click.open_at(view, (1, 1)), False),
        *ecarts("filtre posé", double_click.installed(), True),
    ]
    if problemes:
        return problemes
    ouvert = double_clic_envoye(viewport, qx, qy)
    problemes += ecarts("pièce : panneau ouvert", ouvert, True)
    problemes += ecarts("pièce : son formulaire", formulaire() is not None, True)
    if ouvert:
        annuler()
    Gui.activateWorkbench(AUCUN_ATELIER)
    try:
        problemes += ecarts("atelier quitté : filtre retiré", double_click.installed(), False)
    finally:
        Gui.activateWorkbench(ATELIER)
    return [*problemes, *ecarts("atelier repris : filtre posé", double_click.installed(), True)]


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
