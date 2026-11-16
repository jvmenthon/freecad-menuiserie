# SPDX-License-Identifier: LGPL-2.1-or-later
"""Scénario QTest S19 : passer par d'autres ateliers en plein travail, puis revenir (ADR 0007).

L'angle à queue d'aronde est construit, le panneau de l'assemblage reste ouvert pendant un
passage par l'atelier Part, puis un cube est créé et supprimé par les commandes de Part, une
page TechDraw reçoit une vue de la pièce usinée, et de retour dans l'atelier tout marche comme
avant. Attrape un observateur de l'atelier qui gêne les autres ateliers, ou qui ne survit pas
au changement.

Non simulés : le choix de l'atelier dans la liste déroulante de FreeCAD
(``Gui.activateWorkbench``) et la création de la page TechDraw (objets créés par le script).
"""

from __future__ import annotations

import unittest
from pathlib import Path
from typing import Any, ClassVar

import FreeCAD as App
import FreeCADGui as Gui

from tests.gui.verifications_assemblages import usinee_de
from tests.qtest.aides import (
    ATELIER,
    Etapes,
    activer_faulthandler,
    attendre,
    bouton_ok,
    cliquer,
    enfant,
    fermer,
    formulaire,
    lancer,
    panneau_ouvert,
    preparer,
    selectionner,
    taper,
    traiter_les_evenements,
    vider_la_vue_rapport,
    vue_rapport,
)
from tests.qtest.angle_a_queues import (
    ANGLE,
    PANNEAU_ASSEMBLAGE,
    controler_le_document,
    double_cliquer,
    jouer,
    volumes_usines,
)
from tests.qtest.pieces import erreurs_python

PART, TECHDRAW = "PartWorkbench", "TechDrawWorkbench"
GABARIT = "Default_Template_A4_Landscape.svg"
ANGLE_RETOUCHE = 12.0
DELAI_VUE_MS = 20000  # TechDraw calcule les arêtes cachées dans un fil à part


def setUpModule() -> None:
    unittest.addModuleCleanup(activer_faulthandler())


def activer(atelier: str) -> None:
    Gui.activateWorkbench(atelier)
    traiter_les_evenements()
    if Gui.activeWorkbench().name() != atelier:
        raise AssertionError(f"atelier {atelier} non activé")


class AutresAteliers(Etapes):
    """Étapes jouées dans l'ordre sur le même document."""

    doc: ClassVar[Any]
    hote: ClassVar[Any]
    invitee: ClassVar[Any]
    assemblage: ClassVar[Any]

    @classmethod
    def setUpClass(cls) -> None:
        cls.doc = preparer("ScenarioAutresAteliers")
        cls.addClassCleanup(fermer, cls.doc)
        cls.addClassCleanup(Gui.activateWorkbench, ATELIER)
        cls.hote, cls.invitee, cls.assemblage = jouer(cls.doc)
        vider_la_vue_rapport()

    def test_1_panneau_ouvert_pendant_un_passage_par_part(self) -> None:
        annulations = len(self.doc.UndoNames)
        double_cliquer(self.assemblage)
        activer(PART)
        self.assertTrue(panneau_ouvert(), "panneau fermé par le changement d'atelier")
        taper(enfant(formulaire(PANNEAU_ASSEMBLAGE), "Angle"), f"{ANGLE_RETOUCHE:g}")
        self.assertAlmostEqual(self.assemblage.Angle.Value, ANGLE_RETOUCHE)
        activer(ATELIER)
        self.assertTrue(panneau_ouvert())
        cliquer(bouton_ok())
        self.assertFalse(panneau_ouvert())
        self.assertEqual(len(self.doc.UndoNames), annulations + 1, self.doc.UndoNames)
        controler_le_document(self, self.doc)

    def test_2_commandes_de_part(self) -> None:
        """Un cube créé puis supprimé par les commandes de Part, pièces de l'atelier à côté :
        elles ne bougent pas."""
        volumes = volumes_usines(self.hote, self.invitee)
        objets = len(self.doc.Objects)
        activer(PART)
        selectionner()
        lancer("Part_Box")
        (cube,) = (obj for obj in self.doc.Objects if obj.TypeId == "Part::Box")
        selectionner(cube)
        lancer("Std_Delete")
        self.assertEqual(len(self.doc.Objects), objets)
        self.assertEqual(volumes_usines(self.hote, self.invitee), volumes)
        controler_le_document(self, self.doc)

    def test_3_vue_techdraw_de_la_piece_usinee(self) -> None:
        activer(TECHDRAW)
        gabarit = Path(App.getResourceDir()) / "Mod" / "TechDraw" / "Templates" / GABARIT
        if not gabarit.is_file():
            self.skipTest(f"gabarit TechDraw absent : {gabarit}")
        page = self.doc.addObject("TechDraw::DrawPage", "Page")
        modele = self.doc.addObject("TechDraw::DrawSVGTemplate", "Gabarit")
        modele.Template = str(gabarit)
        page.Template = modele
        vue = self.doc.addObject("TechDraw::DrawViewPart", "Vue")
        page.addView(vue)
        vue.Source = [usinee_de(self.invitee)]
        vue.Direction = App.Vector(0, -1, 0)
        self.doc.recompute()
        self.assertTrue(
            attendre(lambda: len(vue.getVisibleEdges()) > 0, DELAI_VUE_MS), "vue TechDraw vide"
        )
        # Trois queues en trapèze : bien plus d'arêtes que le rectangle d'une pièce brute.
        self.assertGreater(len(vue.getVisibleEdges()), 4)
        self.assertTrue(vue.isValid(), vue.getStatusString())

    def test_4_retour_dans_l_atelier(self) -> None:
        activer(ATELIER)
        selectionner()
        double_cliquer(self.assemblage)
        champ = enfant(formulaire(PANNEAU_ASSEMBLAGE), "Angle")
        self.assertAlmostEqual(champ.property("rawValue"), ANGLE_RETOUCHE)
        taper(champ, f"{ANGLE:g}")
        cliquer(bouton_ok())
        self.assertFalse(panneau_ouvert())
        self.assertAlmostEqual(self.assemblage.Angle.Value, ANGLE)
        self.doc.recompute()
        controler_le_document(self, self.doc)
        self.assertEqual(erreurs_python(vue_rapport()), [])
