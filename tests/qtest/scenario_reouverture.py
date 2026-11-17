# SPDX-License-Identifier: LGPL-2.1-or-later
"""Scénario QTest S2 : enregistrer, fermer, rouvrir, puis modifier l'assemblage.

L'angle à queue d'aronde (``angle_a_queues.py``) est enregistré dans un dossier temporaire, fermé
et rouvert ; l'assemblage est ensuite modifié par double-clic (angle 10° -> 14° tapé au clavier,
bouton OK). Attrape les proxys non restaurés, un document « modifié » dès l'ouverture, un
assemblage qui ne se recalcule plus après relecture.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Any, ClassVar

import FreeCAD as App
import FreeCADGui as Gui

from tests.qtest.aides import (
    Etapes,
    activer_faulthandler,
    bouton_ok,
    cliquer,
    enfant,
    formulaire,
    preparer,
    taper,
    traiter_les_evenements,
)
from tests.qtest.angle_a_queues import (
    PANNEAU_ASSEMBLAGE,
    TOLERANCE_MM,
    TOLERANCE_MM3,
    VOLUME_BRUT,
    VOLUME_QUEUES,
    controler_le_document,
    double_cliquer,
    jouer,
    volume_des_queues,
    volumes_usines,
)

NOUVEL_ANGLE = 14.0


def setUpModule() -> None:
    unittest.addModuleCleanup(activer_faulthandler())


def fermer_le_document_actif() -> None:
    """Le document rouvert n'est pas celui du début : on ferme celui qui est actif."""
    if Gui.Control.activeDialog():
        Gui.Control.activeTaskDialog().reject()
    Gui.Selection.clearSelection()
    if App.ActiveDocument is not None:
        App.closeDocument(App.ActiveDocument.Name)
    traiter_les_evenements()


class Reouverture(Etapes):
    """Étapes numérotées, jouées dans l'ordre sur le document rouvert."""

    doc: ClassVar[Any]
    hote: ClassVar[Any]
    invitee: ClassVar[Any]
    assemblage: ClassVar[Any]

    @classmethod
    def setUpClass(cls) -> None:
        dossier = tempfile.TemporaryDirectory()
        cls.addClassCleanup(dossier.cleanup)
        doc = preparer("ScenarioReouverture")
        cls.addClassCleanup(fermer_le_document_actif)
        noms = [obj.Name for obj in jouer(doc)]
        chemin = Path(dossier.name) / "angle.FCStd"
        doc.saveAs(str(chemin))
        App.closeDocument(doc.Name)
        traiter_les_evenements()
        cls.doc = App.openDocument(str(chemin))
        traiter_les_evenements()
        cls.hote, cls.invitee, cls.assemblage = (cls.doc.getObject(nom) for nom in noms)

    def test_1_document_rouvert_intact(self) -> None:
        self.assertFalse(Gui.getDocument(self.doc.Name).Modified, "modifié dès l'ouverture")
        self.assertEqual(len(self.doc.Objects), 5)
        self.assertEqual(self.assemblage.TailCount, 3)
        self.assertAlmostEqual(self.assemblage.PinWidth.Value, 30.0, delta=TOLERANCE_MM)
        self.assertAlmostEqual(self.assemblage.Angle.Value, 10.0, delta=TOLERANCE_MM)
        self.assertEqual(
            (self.assemblage.HostPart, self.assemblage.GuestPart), (self.hote, self.invitee)
        )
        hote, invitee = volumes_usines(self.hote, self.invitee)
        self.assertAlmostEqual(hote, VOLUME_BRUT - VOLUME_QUEUES, delta=TOLERANCE_MM3)
        self.assertAlmostEqual(invitee, VOLUME_BRUT + VOLUME_QUEUES, delta=TOLERANCE_MM3)
        controler_le_document(self, self.doc)

    def test_2_modifier_l_assemblage_par_double_clic(self) -> None:
        double_cliquer(self.assemblage)
        form = formulaire(PANNEAU_ASSEMBLAGE)
        angle = enfant(form, "Angle")
        self.assertFalse(enfant(form, "AngleAuto").isChecked())
        self.assertAlmostEqual(float(angle.property("rawValue")), 10.0, delta=TOLERANCE_MM)
        taper(angle, f"{NOUVEL_ANGLE:g}")
        cliquer(bouton_ok())
        self.assertAlmostEqual(self.assemblage.Angle.Value, 14.0, delta=TOLERANCE_MM)
        self.assertEqual(self.doc.UndoNames, ["Modifier un assemblage"])
        queues = volume_des_queues(NOUVEL_ANGLE)
        hote, invitee = volumes_usines(self.hote, self.invitee)
        self.assertAlmostEqual(hote, VOLUME_BRUT - queues, delta=TOLERANCE_MM3)
        self.assertAlmostEqual(invitee, VOLUME_BRUT + queues, delta=TOLERANCE_MM3)
        controler_le_document(self, self.doc)
