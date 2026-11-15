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
import os
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui

from tests.gui.verifications_double_clic import vue_3d_active
from tests.gui.verifications_panneau import formulaire_nomme
from tests.qtest.qttest import QTest

ATELIER = "MenuiserieWorkbench"
PILE_EN_CAS_DE_PLANTAGE = "PILE_EN_CAS_DE_PLANTAGE"
DOSSIER_DES_CAPTURES = "CAPTURES_QTEST"
DELAI_MS = 5000
PAS_MS = 50

Widget = Any


def activer_faulthandler() -> Callable[[], None]:
    """Pile Python de tous les fils écrite si FreeCAD plante dans du code C++ (SIGSEGV…) ; renvoie
    la fonction qui l'arrête (à passer à ``unittest.addModuleCleanup``).

    La sortie standard de FreeCAD est une console Python sans descripteur de fichier : la pile
    va dans le fichier ``PILE_EN_CAS_DE_PLANTAGE`` s'il est défini (la CI l'affiche en cas
    d'échec), sinon dans la sortie d'erreur d'origine du processus."""
    chemin = os.environ.get(PILE_EN_CAS_DE_PLANTAGE)
    if not chemin:
        if sys.__stderr__ is not None:
            faulthandler.enable(file=sys.__stderr__, all_threads=True)
        return faulthandler.disable
    fichier = Path(chemin).open("w", encoding="utf-8")  # noqa: SIM115 (fermé par ``arreter``)
    faulthandler.enable(file=fichier, all_threads=True)

    def arreter() -> None:
        faulthandler.disable()
        fichier.close()

    return arreter


def traiter_les_evenements() -> None:
    QtGui.QApplication.processEvents()


def preparer(nom: str) -> Any:
    """Nouveau document avec annulation, atelier actif et vue 3D du document au premier plan ;
    le document est refermé si la préparation échoue."""
    doc = App.newDocument(nom)
    try:
        doc.UndoMode = 1
        Gui.activateWorkbench(ATELIER)
        traiter_les_evenements()
        vue_3d_active(doc)
        traiter_les_evenements()
    except Exception:
        App.closeDocument(doc.Name)
        raise
    return doc


def fermer(doc: Any) -> None:
    """Panneau éventuel annulé, sélection vidée, document fermé."""
    if Gui.Control.activeDialog():
        Gui.Control.activeTaskDialog().reject()
    Gui.Selection.clearSelection()
    App.closeDocument(doc.Name)
    traiter_les_evenements()


def formulaire(nom: str) -> Widget:
    """Formulaire ``nom`` du panneau de tâche ouvert ; échec explicite s'il n'y en a pas."""
    form = formulaire_nomme(nom)
    if form is None:
        raise LookupError(f"panneau {nom} non ouvert")
    return form


def enfant(form: Widget, nom: str) -> Widget:
    """L'unique widget ``nom`` du formulaire ``form``."""
    trouves = [w for w in form.findChildren(QtGui.QWidget) if w.objectName() == nom]
    if len(trouves) != 1:
        raise LookupError(
            f"{len(trouves)} widgets {nom} dans le panneau {form.objectName()} au lieu d'un"
        )
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


def bouton_du_panneau(role: Any) -> Widget:
    """L'unique bouton standard ``role`` visible dans la vue des tâches de FreeCAD.

    Plus strict que ``tests/gui/verifications_panneau_ensemble.bouton_ok`` (premier trouvé, ou
    ``None``) : le bouton va être cliqué, il doit être visible et le seul."""
    boutons = [
        boite.button(role)
        for boite in Gui.getMainWindow().findChildren(QtGui.QDialogButtonBox)
        if boite.isVisible() and boite.button(role) is not None
    ]
    if len(boutons) != 1:
        raise LookupError(f"{len(boutons)} boutons {role} visibles au lieu d'un")
    return boutons[0]


def bouton_ok() -> Widget:
    """Bouton « OK » du panneau de tâche ouvert."""
    return bouton_du_panneau(QtGui.QDialogButtonBox.StandardButton.Ok)


def bouton_annuler() -> Widget:
    """Bouton « Annuler » du panneau de tâche ouvert."""
    return bouton_du_panneau(QtGui.QDialogButtonBox.StandardButton.Cancel)


def appuyer_sur_echap(widget: Widget) -> None:
    """Touche Échap pressée dans ``widget`` (le champ qui a le focus)."""
    widget.setFocus(QtCore.Qt.FocusReason.OtherFocusReason)
    QTest.keyClick(widget, QtCore.Qt.Key.Key_Escape)
    traiter_les_evenements()


def panneau_ouvert() -> bool:
    return bool(Gui.Control.activeDialog())


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


def vue_rapport() -> str:
    """Texte de la vue rapport de FreeCAD : les erreurs Python d'un signal Qt y arrivent."""
    vues = [
        vue
        for vue in Gui.getMainWindow().findChildren(QtGui.QTextEdit)
        if vue.objectName() == "Report view"
    ]
    if len(vues) != 1:
        raise LookupError(f"{len(vues)} vues rapport au lieu d'une")
    return str(vues[0].toPlainText())


def vider_la_vue_rapport() -> None:
    for vue in Gui.getMainWindow().findChildren(QtGui.QTextEdit):
        if vue.objectName() == "Report view":
            vue.clear()


class ReponseAuxBoites:
    """Répond aux boîtes de message modales ouvertes pendant le bloc ``with``, comme
    l'utilisateur : clic sur le bouton dont le texte commence par ``reponse`` (sans le « & » du
    raccourci). ``vues`` garde le titre et le texte de chaque boîte. Une boîte modale bloque la
    boucle d'événements : la réponse part d'une minuterie, armée avant le geste qui l'ouvre.
    Une boîte sans ce bouton est refermée et le bloc échoue."""

    def __init__(self, reponse: str) -> None:
        self.reponse = reponse
        self.vues: list[tuple[str, str]] = []
        self._inattendues: list[str] = []
        self._minuterie = QtCore.QTimer()
        self._minuterie.setInterval(PAS_MS)
        self._minuterie.timeout.connect(self._repondre)

    def _repondre(self) -> None:
        boite = QtGui.QApplication.activeModalWidget()
        if boite is None:
            return
        if not isinstance(boite, QtGui.QMessageBox):
            self._inattendues.append(f"fenêtre modale {type(boite).__name__}")
            boite.close()
            return
        self.vues.append((str(boite.windowTitle()), str(boite.text())))
        boutons = [b for b in boite.buttons() if b.text().replace("&", "").startswith(self.reponse)]
        if len(boutons) != 1:
            textes = [b.text() for b in boite.buttons()]
            self._inattendues.append(f"boîte « {boite.windowTitle()} » : boutons {textes}")
            boite.reject()
            return
        QTest.mouseClick(boutons[0], QtCore.Qt.MouseButton.LeftButton)

    def __enter__(self) -> ReponseAuxBoites:
        self._minuterie.start()
        return self

    def __exit__(self, *_exc: object) -> None:
        QTest.qWait(4 * PAS_MS)  # une boîte ouverte en différé a encore sa réponse
        self._minuterie.stop()
        if self._inattendues:
            raise AssertionError("; ".join(self._inattendues))
