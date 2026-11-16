# SPDX-License-Identifier: LGPL-2.1-or-later
"""Scénario QTest S12 : une traverse assemblée, répétée le long de son montant.

Commande « Répéter » et son panneau (mode « Nombre et pas », nombre, pas), puis « Modifier la
répétition » depuis une copie (nombre, puis pas), « Dissocier la copie », la recopie des
assemblages décochée et un tenon-mortaise posé à la main sur une copie, qui doit tenir quand le
pas change encore (PR #260).
"""

from __future__ import annotations

import unittest
from typing import Any, ClassVar

from tests.gui.verifications_assemblages import usinee_de
from tests.qtest.aides import (
    Etapes,
    activer_faulthandler,
    bouton_ok,
    choisir,
    cliquer,
    enfant,
    fermer,
    formulaire,
    lancer,
    panneau_ouvert,
    preparer,
    selectionner,
    taper,
    vider_la_vue_rapport,
    vue_rapport,
)
from tests.qtest.angle_a_queues import controler_le_document
from tests.qtest.pieces import (
    assemblages,
    commande_active,
    du_type,
    erreurs_python,
    retablir_tout,
    tenon_mortaise,
)

TENON_MORTAISE = "Menuiserie_MortiseTenon"
REPETER = "Menuiserie_Repeat"
MODIFIER = "Menuiserie_RepeatEdit"
DISSOCIER = "Menuiserie_RepeatDissociate"
PANNEAU_REPETITION = "RepeatTaskPanel"
TYPE_PIECE = "Menuiserie::WoodPart"
NOMBRE_ET_PAS = 0  # première ligne de la liste « mode de saisie »
DEPART = 60.0  # abscisse de la traverse d'origine
TOLERANCE_MM = 1e-6


def setUpModule() -> None:
    unittest.addModuleCleanup(activer_faulthandler())


class Repetition(Etapes):
    """Étapes jouées dans l'ordre sur le même document."""

    doc: ClassVar[Any]
    montant: ClassVar[Any]
    traverse: ClassVar[Any]
    dissociee: ClassVar[Any]
    une_mortaise: ClassVar[float] = 0.0

    @classmethod
    def setUpClass(cls) -> None:
        cls.doc = preparer("ScenarioRepetition")
        cls.addClassCleanup(fermer, cls.doc)
        cls.montant, cls.traverse = tenon_mortaise(cls.doc)
        vider_la_vue_rapport()

    def copies(self) -> list[Any]:
        """Les traverses créées par la répétition, dans l'ordre de création."""
        return [
            brute
            for brute in du_type(self.doc, TYPE_PIECE)
            if brute not in (self.montant, self.traverse)
        ]

    def abscisses(self) -> list[float]:
        return [round(copie.Placement.Base.x, 6) for copie in self.copies()]

    def controler_les_assemblages(self, nombre: int) -> None:
        """``nombre`` assemblages valides, et autant de mortaises dans le montant resté en un
        seul solide."""
        tous = assemblages(self.doc)
        self.assertEqual(len(tous), nombre, [a.Label for a in tous])
        for assemblage in tous:
            self.assertTrue(assemblage.isValid(), assemblage.Label)
        usine = usinee_de(self.montant).Shape
        self.assertEqual(len(usine.Solids), 1)
        mortaise = self.montant.Shape.Volume - usine.Volume
        self.assertGreater(mortaise, 0.0)
        if not self.une_mortaise:
            type(self).une_mortaise = mortaise / nombre
        self.assertAlmostEqual(mortaise, nombre * type(self).une_mortaise, delta=1.0)
        controler_le_document(self, self.doc)

    def ouvrir_la_modification(self) -> Any:
        selectionner(self.copies()[0])
        lancer(MODIFIER)
        return formulaire(PANNEAU_REPETITION)

    def test_1_repeter_quatre_fois(self) -> None:
        selectionner(self.traverse)
        self.assertFalse(commande_active(DISSOCIER), "« Dissocier » actif sur l'original")
        lancer(REPETER)
        form = formulaire(PANNEAU_REPETITION)
        choisir(enfant(form, "spacing"), NOMBRE_ET_PAS)
        taper(enfant(form, "countX"), "4")
        taper(enfant(form, "stepX"), "100 mm")
        self.assertTrue(enfant(form, "errorLabel").isHidden(), enfant(form, "errorLabel").text())
        cliquer(bouton_ok())
        self.assertFalse(panneau_ouvert())
        self.assertEqual(self.abscisses(), [DEPART + 100.0, DEPART + 200.0, DEPART + 300.0])
        self.controler_les_assemblages(4)
        self.assertEqual(len(self.doc.UndoNames), 1, self.doc.UndoNames)

    def test_2_changer_le_nombre_puis_le_pas(self) -> None:
        form = self.ouvrir_la_modification()
        self.assertEqual(enfant(form, "countX").value(), 4)
        self.assertAlmostEqual(enfant(form, "stepX").property("rawValue"), 100.0)
        taper(enfant(form, "countX"), "5")
        taper(enfant(form, "stepX"), "120 mm")
        cliquer(bouton_ok())
        self.assertFalse(panneau_ouvert())
        self.assertEqual(self.abscisses(), [DEPART + 120.0 * rang for rang in range(1, 5)])
        self.controler_les_assemblages(5)
        self.assertEqual(len(self.doc.UndoNames), 2, self.doc.UndoNames)

    def test_3_dissocier_la_derniere_copie(self) -> None:
        derniere = self.copies()[-1]
        type(self).dissociee = derniere
        selectionner(derniere)
        self.assertTrue(commande_active(MODIFIER))
        lancer(DISSOCIER)
        self.assertEqual(len(self.doc.UndoNames), 3, self.doc.UndoNames)
        selectionner()
        selectionner(derniere)
        # Redevenue une pièce ordinaire : on peut la répéter, plus la dissocier.
        self.assertTrue(commande_active(REPETER))
        self.assertFalse(commande_active(DISSOCIER), "« Dissocier » resté actif")
        self.assertFalse(commande_active(MODIFIER))
        self.controler_les_assemblages(5)

    def test_4_le_pas_change_sans_la_copie_dissociee(self) -> None:
        place = self.dissociee.Placement.Base.x
        form = self.ouvrir_la_modification()
        taper(enfant(form, "stepX"), "130 mm")
        cliquer(bouton_ok())
        self.assertAlmostEqual(self.dissociee.Placement.Base.x, place, delta=TOLERANCE_MM)
        liees = [x for x in self.abscisses() if abs(x - place) > TOLERANCE_MM]
        self.assertEqual(len(liees), 3, self.abscisses())
        self.assertEqual(liees, [DEPART + 130.0 * rang for rang in range(1, len(liees) + 1)])
        for assemblage in assemblages(self.doc):
            self.assertTrue(assemblage.isValid(), assemblage.Label)
        controler_le_document(self, self.doc)

    def test_5_assemblage_pose_a_la_main_sur_une_copie(self) -> None:
        """Recopie des assemblages décochée : les copies n'en ont plus ; un tenon-mortaise posé
        à la main sur la première tient quand le pas change (PR #260)."""
        form = self.ouvrir_la_modification()
        self.assertTrue(enfant(form, "copyJoints").isChecked())
        cliquer(enfant(form, "copyJoints"))
        cliquer(bouton_ok())
        gardes = {a.GuestPart for a in assemblages(self.doc)}
        self.assertEqual(gardes, {self.traverse, self.dissociee})
        copie = self.copies()[0]
        selectionner(copie, self.montant)
        lancer(TENON_MORTAISE)
        cliquer(bouton_ok())
        self.assertFalse(panneau_ouvert())
        (a_la_main,) = (a for a in assemblages(self.doc) if a.GuestPart is copie)
        self.assertTrue(a_la_main.isValid(), a_la_main.getStatusString())
        form = self.ouvrir_la_modification()
        taper(enfant(form, "stepX"), "110 mm")
        self.assertTrue(enfant(form, "errorLabel").isHidden(), enfant(form, "errorLabel").text())
        cliquer(bouton_ok())
        self.assertAlmostEqual(copie.Placement.Base.x, DEPART + 110.0, delta=TOLERANCE_MM)
        self.assertIn(a_la_main, assemblages(self.doc))
        self.assertTrue(a_la_main.isValid(), a_la_main.getStatusString())
        self.controler_les_assemblages(3)

    def test_6_tout_annuler(self) -> None:
        copies, abscisses = self.copies(), self.abscisses()
        for _ in self.doc.UndoNames:
            lancer("Std_Undo")
        self.doc.recompute()
        self.assertEqual(self.copies(), [])
        self.controler_les_assemblages(1)
        retablir_tout(self.doc)
        self.assertEqual(self.copies(), copies)
        self.assertEqual(self.abscisses(), abscisses)
        self.controler_les_assemblages(3)
        self.assertEqual(erreurs_python(vue_rapport()), [])
