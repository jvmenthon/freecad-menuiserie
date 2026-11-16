# SPDX-License-Identifier: LGPL-2.1-or-later
"""Scénario QTest S10 : assemblages entre pièces en biais (issues #114, #78, #169).

Une traverse en biais de 15° contre le chant d'un montant : tenon-mortaise par la commande et son
panneau, chaque référence du biais choisie dans la liste, puis la traverse tournée à 45° et
élargie par son panneau : l'assemblage suit. Mi-bois : refusé avec une explication quand les
pièces ne se chevauchent pas, accepté quand elles sont dessinées à cheval.

Non simulée : la rotation de la traverse à la souris (son placement est écrit par le script,
dans une transaction).
"""

from __future__ import annotations

import unittest
from typing import Any, ClassVar

from PySide import QtGui

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
    refus_signale,
    selectionner,
    taper,
    vider_la_vue_rapport,
    vue_rapport,
)
from tests.qtest.angle_a_queues import (
    PANNEAU_ASSEMBLAGE,
    PANNEAU_PIECE,
    controler_le_document,
    double_cliquer,
)
from tests.qtest.pieces import assemblages, deplacer, erreurs_python, piece, placement_de
from tests.unit.aides_biais import tilted_rail

TENON_MORTAISE = "Menuiserie_MortiseTenon"
MI_BOIS = "Menuiserie_HalfLap"
MONTANT = (600.0, 60.0, 22.0)
TRAVERSE = (280.0, 60.0, 22.0)
BIAIS, GRAND_BIAIS = 15.0, 45.0
LARGEUR_RETOUCHEE = 80.0
TOLERANCE_MM3 = 1e-3


def setUpModule() -> None:
    unittest.addModuleCleanup(activer_faulthandler())


def montant_et_traverse_en_biais(doc: Any, degres: float, mode: Any) -> tuple[Any, Any]:
    """Montant à plat et traverse tournée de ``degres`` contre son chant ; ``mode`` dit comment
    son bout est dessiné : la pointe contre la face, hors tout, ou à cheval sur le montant."""
    montant = piece(doc, MONTANT, repere="M")
    traverse = piece(doc, TRAVERSE, repere="T")
    traverse.Placement = placement_de(tilted_rail(degres, mode))
    doc.recompute()
    return montant, traverse


class TenonEnBiais(Etapes):
    """Étapes jouées dans l'ordre sur le même document."""

    doc: ClassVar[Any]
    montant: ClassVar[Any]
    traverse: ClassVar[Any]

    @classmethod
    def setUpClass(cls) -> None:
        cls.doc = preparer("ScenarioBiais")
        cls.addClassCleanup(fermer, cls.doc)
        cls.montant, cls.traverse = montant_et_traverse_en_biais(cls.doc, BIAIS, "hors tout")
        cls.doc.clearUndos()
        vider_la_vue_rapport()

    def volumes(self) -> tuple[float, float]:
        return usinee_de(self.montant).Shape.Volume, usinee_de(self.traverse).Shape.Volume

    def controler_l_assemblage(self) -> None:
        """Assemblage valide, chaque pièce en un seul solide, mortaise creusée, et les deux
        pièces usinées ne se traversent pas."""
        (assemblage,) = assemblages(self.doc)
        self.assertTrue(assemblage.isValid(), assemblage.getStatusString())
        controler_le_document(self, self.doc)
        formes = [usinee_de(brute).Shape for brute in (self.montant, self.traverse)]
        for forme in formes:
            self.assertEqual(len(forme.Solids), 1)
        self.assertLess(formes[0].Volume, self.montant.Shape.Volume - 1.0, "pas de mortaise")
        self.assertAlmostEqual(formes[0].common(formes[1]).Volume, 0.0, delta=TOLERANCE_MM3)

    def empreinte(self) -> tuple[float, ...]:
        """Volumes et centres de gravité des deux pièces usinées, arrondis : changent dès que
        l'usinage change."""
        formes = [usinee_de(brute).Shape for brute in (self.montant, self.traverse)]
        centres = [cote for forme in formes for cote in forme.Solids[0].CenterOfMass]
        return tuple(round(valeur, 2) for valeur in (*self.volumes(), *centres))

    def liste_des_references(self) -> Any:
        return formulaire(PANNEAU_ASSEMBLAGE).findChild(QtGui.QComboBox, "ObliqueReference")

    def test_1_tenon_mortaise_a_15_degres(self) -> None:
        selectionner(self.traverse, self.montant)
        lancer(TENON_MORTAISE)
        self.assertTrue(enfant(formulaire(PANNEAU_ASSEMBLAGE), "errorLabel").isHidden())
        cliquer(bouton_ok())
        self.assertFalse(panneau_ouvert())
        self.controler_l_assemblage()
        self.assertEqual(len(self.doc.UndoNames), 1, self.doc.UndoNames)

    def test_2_chaque_reference_du_biais(self) -> None:
        """Double-clic, puis chaque ligne de la liste « référence du biais » : écrite dans la
        propriété, et l'usinage change à chaque fois."""
        (assemblage,) = assemblages(self.doc)
        double_cliquer(assemblage)
        liste = self.liste_des_references()
        self.assertTrue(liste.isVisible() and liste.isEnabled())
        vus: dict[str, tuple[float, ...]] = {}
        for rang in reversed(range(liste.count())):
            with self.subTest(reference=liste.itemText(rang)):
                choisir(self.liste_des_references(), rang)
                self.assertTrue(enfant(formulaire(PANNEAU_ASSEMBLAGE), "errorLabel").isHidden())
                vus[str(assemblage.ObliqueReference)] = self.empreinte()
        self.assertEqual(len(vus), liste.count(), "référence non écrite dans la propriété")
        self.assertEqual(len(set(vus.values())), liste.count(), vus)
        cliquer(bouton_ok())
        self.controler_l_assemblage()
        self.assertEqual(len(self.doc.UndoNames), 2, self.doc.UndoNames)

    def test_3_traverse_tournee_a_45_degres(self) -> None:
        avant = self.volumes()
        deplacer(self.doc, self.traverse, placement_de(tilted_rail(GRAND_BIAIS, "hors tout")))
        self.controler_l_assemblage()
        self.assertNotAlmostEqual(self.volumes()[0], avant[0], delta=1.0, msg="mortaise inchangée")

    def test_4_traverse_elargie_au_panneau(self) -> None:
        """Issue #169 : la pièce en biais redimensionnée garde son assemblage."""
        avant = self.volumes()
        annulations = len(self.doc.UndoNames)
        double_cliquer(self.traverse)
        taper(enfant(formulaire(PANNEAU_PIECE), "widthEdit"), f"{LARGEUR_RETOUCHEE:g} mm")
        cliquer(bouton_ok())
        self.assertFalse(panneau_ouvert())
        self.assertAlmostEqual(self.traverse.Width.Value, LARGEUR_RETOUCHEE)
        self.controler_l_assemblage()
        self.assertGreater(self.volumes()[1], avant[1] + 1.0)
        self.assertEqual(len(self.doc.UndoNames), annulations + 1, self.doc.UndoNames)

    def test_5_tout_annuler(self) -> None:
        for _ in self.doc.UndoNames:
            lancer("Std_Undo")
        self.assertEqual(self.doc.Objects, [self.montant, self.traverse])
        self.assertAlmostEqual(self.traverse.Width.Value, TRAVERSE[1])
        self.doc.recompute()  # l'annulation de FreeCAD laisse la pièce « à recalculer »
        controler_le_document(self, self.doc)
        self.assertEqual(erreurs_python(vue_rapport()), [])


class MiBoisEnBiais(unittest.TestCase):
    """Mi-bois à 15° et 45° : il faut que les pièces se chevauchent."""

    def jouer(self, degres: float, mode: str) -> tuple[Any, str]:
        """Commande sur les deux pièces ; renvoie le document et le refus affiché (« » si le
        panneau s'est ouvert)."""
        doc = preparer("ScenarioMiBoisEnBiais")
        self.addCleanup(fermer, doc)
        montant, traverse = montant_et_traverse_en_biais(doc, degres, mode)
        doc.clearUndos()
        vider_la_vue_rapport()
        selectionner(traverse, montant)
        lancer(MI_BOIS)
        return doc, refus_signale()

    def test_refuse_sans_chevauchement(self) -> None:
        for degres in (BIAIS, GRAND_BIAIS):
            with self.subTest(degres=degres):
                doc, refus = self.jouer(degres, "pointe")
                self.assertIn("chevauchent", refus)
                self.assertFalse(panneau_ouvert())
                self.assertEqual(assemblages(doc), [])
                self.assertEqual(doc.UndoNames, [])
                self.assertIn("chevauchent", vue_rapport())
                self.assertEqual(erreurs_python(vue_rapport()), [])

    def test_accepte_a_cheval(self) -> None:
        for degres in (BIAIS, GRAND_BIAIS):
            with self.subTest(degres=degres):
                doc, refus = self.jouer(degres, "cheval")
                self.assertEqual(refus, "")
                cliquer(bouton_ok())
                self.assertFalse(panneau_ouvert())
                (assemblage,) = assemblages(doc)
                self.assertTrue(assemblage.isValid(), assemblage.getStatusString())
                controler_le_document(self, doc)
                formes = [usinee_de(a).Shape for a in (assemblage.HostPart, assemblage.GuestPart)]
                self.assertAlmostEqual(formes[0].common(formes[1]).Volume, 0.0, delta=TOLERANCE_MM3)
                self.assertEqual(len(doc.UndoNames), 1, doc.UndoNames)
