# SPDX-License-Identifier: LGPL-2.1-or-later
"""Vérifications d'interface de la coplanarité (jv, 2026-11-14, ADR 0058) : pendant un glissement,
la face au ras d'une face d'un autre meuble s'y aimante et les deux sont allumées ; dans le
panneau « Répéter », les faces des copies au ras d'une voisine sont tracées dans la vue 3D, dès
l'ouverture d'une répétition existante, et les flèches du pas s'aimantent à 1 mm (jv, 2026-11-16).

Module importé par ``verifier_atelier.py`` (lancé par FreeCAD hors écran) : comme
``verifications_souris``, il appelle la session directement, jamais ``sendEvent``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui

from freecad.menuiserie.api import make_wood_part
from freecad.menuiserie.features.repeat import is_repeat
from freecad.menuiserie.gui.task_panels import repeat_coplanar
from freecad.menuiserie.gui.task_panels.repeat import start_editing
from tests.gui.verifications_panneau import avec_document, ecarts, piece_validee, saisir, valeur
from tests.gui.verifications_panneau_assemblage import widget
from tests.gui.verifications_repetition import panneau, repeter, source
from tests.gui.verifications_souris import (
    place,
    preparer,
    proche,
    px_en_mm,
    selection_dessinee,
    sur_la_fleche,
    tirer,
)
from tests.gui.verifications_souris import (
    saisir as saisir_fleche,
)


def _plan_allume(session: Any, axe: int, position: float) -> bool:
    return any(g.axis == axe and abs(g.position(axe) - position) < 1e-6 for g in session.lit)


def _glissement_au_ras(doc: Any) -> list[str]:
    session = preparer(doc)
    piece = piece_validee(doc)  # 800 mm sur X, à l'origine
    loin = make_wood_part(300, 200, 22, "chene", doc=doc)
    loin.Placement = App.Placement(App.Vector(850, 2000, 0), App.Rotation())  # autre meuble
    doc.recompute()
    Gui.activeView().fitAll()
    selection_dessinee(piece)
    tolerance = float(session.port.mm(session.layout.frame.origin, 10.0))
    pas = px_en_mm(session)
    demande = 50.0 - 0.4 * tolerance  # le bout (800) à moins de la tolérance du plan x = 850
    saisie = saisir_fleche(session, sur_la_fleche(session, 0, 40.0))
    problemes = ecarts("flèche saisie", saisie, True)
    voulu = tirer(session, demande)
    problemes += [
        *proche("au ras de l'autre meuble", place(piece)[0], 50.0, 0.01),
        *ecarts("plan voisin allumé", _plan_allume(session, 0, 850.0), True),
        *ecarts("face de la pièce allumée", len(session.lit) >= 2, True),
    ]
    tirer(session, demande, shift=True)
    problemes += [
        *proche("Maj : pas d'aimant", place(piece)[0], demande, 3 * pas),
        *ecarts("Maj : rien au ras", len(session.lit), 0),
    ]
    session.release(voulu)
    doc.undo()
    return problemes


def verifier_coplanarite_glissement() -> list[str]:
    """Pièce tirée près du plan d'une pièce d'un autre meuble (hors de portée) : elle s'y met au
    ras, le plan et sa face sont allumés ; Maj coupe l'aimant."""
    return avec_document("VerifCoplanariteGlissement", _glissement_au_ras)


def noeuds_coplanaires() -> int:
    """Nombre d'incrustations de la coplanarité du panneau dans la vue 3D active."""
    from pivy import coin

    recherche = coin.SoSearchAction()
    recherche.setName(repeat_coplanar.NODE_NAME)
    recherche.setInterest(coin.SoSearchAction.ALL)
    recherche.apply(Gui.activeView().getSceneGraph())
    return int(recherche.getPaths().getLength())


def _repetition_au_ras(doc: Any) -> list[str]:
    barreau = source(doc)  # 300 mm sur X, à l'origine
    voisin = doc.addObject("Part::Box", "Voisin")
    voisin.Length = voisin.Width = voisin.Height = 100
    voisin.Placement = App.Placement(App.Vector(1000, 500, 0), App.Rotation())  # x 1000 à 1100
    doc.recompute()
    preparer(doc)
    repeter(barreau)
    form = panneau()
    if form is None:
        return ["panneau « Répéter » non ouvert"]
    saisir(widget(form, "stepX"), 400.0)  # 2e copie de 800 à 1100 : au ras du voisin
    problemes = ecarts("pas de 400 : faces au ras tracées", noeuds_coplanaires(), 1)
    saisir(widget(form, "stepX"), 333.0)  # 999 à 1299 : rien au ras
    problemes += ecarts("pas de 333 : rien de tracé", noeuds_coplanaires(), 0)
    saisir(widget(form, "stepX"), 350.0)  # 2e copie de 700 à 1000 : au ras de l'autre face
    problemes += ecarts("pas de 350 : faces au ras tracées", noeuds_coplanaires(), 1)
    Gui.Control.activeTaskDialog().reject()
    return [*problemes, *ecarts("panneau fermé : dessin retiré", noeuds_coplanaires(), 0)]


def verifier_coplanarite_repetition() -> list[str]:
    """Panneau « Répéter » : le pas qui met une copie au ras d'une voisine trace les faces ; un
    autre pas les efface ; la fermeture retire le dessin."""
    return avec_document("VerifCoplanariteRepetition", _repetition_au_ras)


def _fleche_haut(champ: Any) -> None:
    """Touche « flèche haut » envoyée au champ : un pas, comme un clic sur sa flèche."""
    touche = QtGui.QKeyEvent(QtCore.QEvent.KeyPress, QtCore.Qt.Key_Up, QtCore.Qt.NoModifier)
    QtGui.QApplication.sendEvent(champ, touche)
    QtGui.QApplication.processEvents()  # fin du pas (minuterie du filtre)


def _modification_au_ras(doc: Any) -> list[str]:
    barreau = source(doc)
    voisin = doc.addObject("Part::Box", "Voisin")
    voisin.Length = voisin.Width = voisin.Height = 100
    voisin.Placement = App.Placement(App.Vector(1000, 500, 0), App.Rotation())  # x 1000 à 1100
    doc.recompute()
    preparer(doc)
    repeter(barreau)
    form = panneau()
    if form is None:
        return ["panneau « Répéter » non ouvert"]
    saisir(widget(form, "stepX"), 400.0)  # 2e copie au ras du voisin
    Gui.Control.activeTaskDialog().accept()
    repetitions = [obj for obj in doc.Objects if is_repeat(obj)]
    if len(repetitions) != 1 or not start_editing(repetitions[0]):
        return [f"répétition non rouverte : {len(repetitions)} répétition(s)"]
    form = panneau()
    if form is None:
        return ["panneau de modification non ouvert"]
    problemes = ecarts("ouverture en modification : faces au ras tracées", noeuds_coplanaires(), 1)
    champ = widget(form, "stepX")
    pas = float(champ.property("singleStep") or 1.0)
    depart = round(350.0 - 0.8 * pas, 6)  # un pas plus loin : 350 franchi, à moins de 1 mm
    saisir(champ, depart)
    problemes += ecarts("saisie au clavier inchangée", round(valeur(champ), 6), depart)
    _fleche_haut(champ)
    problemes += ecarts("flèche : pas aimanté au ras (350)", round(valeur(champ), 6), 350.0)
    problemes += ecarts("flèche : faces au ras tracées", noeuds_coplanaires(), 1)
    Gui.Control.activeTaskDialog().reject()
    return [*problemes, *ecarts("panneau fermé : dessin retiré", noeuds_coplanaires(), 0)]


def verifier_coplanarite_modification() -> list[str]:
    """Modification d'une répétition : le cadre est tracé dès l'ouverture ; une saisie reste telle
    quelle ; la flèche qui franchit un pas au ras, à moins de 1 mm, s'y arrête."""
    return avec_document("VerifCoplanariteModification", _modification_au_ras)


VERIFICATIONS_COPLANARITE: tuple[Callable[[], list[str]], ...] = (
    verifier_coplanarite_glissement,
    verifier_coplanarite_repetition,
    verifier_coplanarite_modification,
)
