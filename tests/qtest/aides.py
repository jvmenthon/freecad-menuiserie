# SPDX-License-Identifier: LGPL-2.1-or-later
"""Aides des scénarios QTest : gestes de l'utilisateur sur les vrais widgets de FreeCAD.

Les champs sont remplis au clavier (``QTest.keyClicks``), les cases et boutons cliqués à la souris
(``QTest.mouseClick``) : ce sont les signaux de Qt qui déclenchent le code de l'atelier, comme pour
l'utilisateur. La vue 3D n'est jamais cliquée au pixel près : la sélection y passe par
``Gui.Selection``, l'équivalent d'un clic sur une pièce.

``QTest`` vient de ``tests/qtest/qttest.py`` (absent de la couche ``PySide`` de FreeCAD).
"""

from __future__ import annotations

import faulthandler
import gc
import os
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui

from tests.gui.verifications_double_clic import vue_3d_active
from tests.qtest.qttest import QTest

ATELIER = "MenuiserieWorkbench"
PILE_EN_CAS_DE_PLANTAGE = "PILE_EN_CAS_DE_PLANTAGE"
DOSSIER_DES_CAPTURES = "CAPTURES_QTEST"
DELAI_MS = 5000
PAS_MS = 50

Widget = Any

_journal_des_plantages: list[Any] = []


def activer_faulthandler() -> None:
    """Pile Python de tous les fils écrite si FreeCAD plante dans du code C++ (SIGSEGV…).

    La sortie standard de FreeCAD est une console Python sans descripteur de fichier : la pile
    va dans le fichier ``PILE_EN_CAS_DE_PLANTAGE`` s'il est défini (la CI l'affiche en cas
    d'échec), sinon dans la sortie d'erreur d'origine du processus."""
    chemin = os.environ.get(PILE_EN_CAS_DE_PLANTAGE)
    if chemin:
        fichier = Path(chemin).open("w", encoding="utf-8")  # noqa: SIM115 (ouvert jusqu'au bout)
        _journal_des_plantages.append(fichier)
        faulthandler.enable(file=fichier, all_threads=True)
    elif sys.__stderr__ is not None:
        faulthandler.enable(file=sys.__stderr__, all_threads=True)


def traiter_les_evenements() -> None:
    QtGui.QApplication.processEvents()


def preparer(nom: str) -> Any:
    """Nouveau document avec annulation, atelier actif et vue 3D du document au premier plan."""
    doc = App.newDocument(nom)
    doc.UndoMode = 1
    Gui.activateWorkbench(ATELIER)
    traiter_les_evenements()
    vue_3d_active(doc)
    traiter_les_evenements()
    return doc


def fermer(doc: Any) -> None:
    """Panneau éventuel annulé, sélection vidée, document fermé."""
    if Gui.Control.activeDialog():
        Gui.Control.activeTaskDialog().reject()
    Gui.Selection.clearSelection()
    App.closeDocument(doc.Name)
    traiter_les_evenements()


def widgets_nommes(nom: str) -> list[Widget]:
    """Widgets d'objectName ``nom`` (ramasse-miettes suspendu pendant le parcours, comme dans
    ``tests/gui/verifications_panneau.formulaire_nomme``)."""
    gc.collect()
    gc.disable()
    try:
        return [w for w in QtGui.QApplication.allWidgets() if w.objectName() == nom]
    finally:
        gc.enable()


def formulaire(nom: str) -> Widget:
    """Formulaire ``nom`` du panneau de tâche ouvert ; échec explicite s'il n'y en a pas."""
    trouves = widgets_nommes(nom) if Gui.Control.activeDialog() else []
    if not trouves:
        raise LookupError(f"panneau {nom} non ouvert")
    return trouves[0]


def enfant(form: Widget, nom: str) -> Widget:
    """Widget ``nom`` du formulaire ``form``."""
    trouves = [w for w in form.findChildren(QtGui.QWidget) if w.objectName() == nom]
    if not trouves:
        raise LookupError(f"widget {nom} absent du panneau {form.objectName()}")
    return trouves[0]


def taper(champ: Widget, texte: str) -> None:
    """Saisie au clavier : tout sélectionner, taper ``texte``, puis Tab pour quitter le champ
    (fin de saisie : ``editingFinished``). Entrée validerait le panneau (bouton OK par défaut)."""
    champ.setFocus(QtCore.Qt.FocusReason.OtherFocusReason)
    QTest.keyClick(champ, QtCore.Qt.Key.Key_A, QtCore.Qt.KeyboardModifier.ControlModifier)
    QTest.keyClicks(champ, texte)
    QTest.keyClick(champ, QtCore.Qt.Key.Key_Tab)
    traiter_les_evenements()


def cliquer(widget: Widget) -> None:
    """Clic gauche au centre de ``widget`` (case à cocher, bouton)."""
    QTest.mouseClick(widget, QtCore.Qt.MouseButton.LeftButton)
    traiter_les_evenements()


def bouton_ok() -> Widget:
    """Bouton « OK » du panneau de tâche ouvert, dans la vue des tâches de FreeCAD."""
    ok = QtGui.QDialogButtonBox.StandardButton.Ok
    boutons = [
        boite.button(ok)
        for boite in Gui.getMainWindow().findChildren(QtGui.QDialogButtonBox)
        if boite.isVisible() and boite.button(ok) is not None
    ]
    if len(boutons) != 1:
        raise LookupError(f"{len(boutons)} boutons OK visibles au lieu d'un")
    return boutons[0]


def attendre(condition: Callable[[], bool], delai_ms: int = DELAI_MS) -> bool:
    """Laisse tourner la boucle d'événements jusqu'à ``condition`` (au plus ``delai_ms``)."""
    restant = delai_ms
    while not condition() and restant > 0:
        QTest.qWait(PAS_MS)
        restant -= PAS_MS
    return bool(condition())


def lancer(commande: str) -> None:
    """Commande de l'atelier lancée comme depuis sa barre d'outils (son action Qt). FreeCAD ne
    rafraîchit l'état de ses boutons que périodiquement : on attend qu'il soit actif, comme
    l'utilisateur qui voit le bouton se dégriser."""
    action = Gui.Command.get(commande).getAction()[0]
    if not attendre(action.isEnabled):
        raise AssertionError(f"commande {commande} inactive")
    action.trigger()
    traiter_les_evenements()


def selectionner(*objets: Any) -> None:
    """Clics successifs sur ``objets`` dans la vue 3D (Ctrl + clic à partir du second)."""
    Gui.Selection.clearSelection()
    for obj in objets:
        Gui.Selection.addSelection(obj)
    traiter_les_evenements()


def capturer(nom: str) -> None:
    """Image de la vue 3D active dans le dossier ``CAPTURES_QTEST`` (rien s'il n'est pas défini) :
    la CI la joint au run, pour voir ce que le scénario a construit."""
    dossier = os.environ.get(DOSSIER_DES_CAPTURES)
    if not dossier:
        return
    Path(dossier).mkdir(parents=True, exist_ok=True)
    vue = Gui.activeView()
    vue.viewIsometric()
    vue.fitAll()
    traiter_les_evenements()
    vue.saveImage(str(Path(dossier) / f"{nom}.png"), 1200, 800, "White")
