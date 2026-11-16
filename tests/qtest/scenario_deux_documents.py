# SPDX-License-Identifier: LGPL-2.1-or-later
"""Scénario QTest S21 : le même travail mené dans deux documents ouverts, en alternance.

L'angle à queue d'aronde de ``angle_a_queues.py`` est construit geste par geste dans deux
documents, en passant de l'un à l'autre à chaque étape (clic sur l'onglet), puis les deux sont
comparés : mêmes pièces, mêmes volumes, chacun son historique d'annulation. Attrape un état
partagé entre documents (panneau, sélection, caches, sessions de glissement).
"""

from __future__ import annotations

import unittest
from typing import Any, ClassVar

import FreeCAD as App

from tests.qtest.aides import (
    Etapes,
    activer_faulthandler,
    bouton_ok,
    cliquer,
    enfant,
    fermer,
    formulaire,
    lancer,
    panneau_ouvert,
    passer_a,
    preparer,
    selectionner,
    taper,
    vider_la_vue_rapport,
    vue_rapport,
)
from tests.qtest.angle_a_queues import (
    ANGLE,
    EPAISSEUR,
    LARGEUR_GRIFFE,
    LONGUEUR,
    PANNEAU_ASSEMBLAGE,
    QUEUE_D_ARONDE,
    QUEUES,
    TOLERANCE_MM3,
    VOLUME_BRUT,
    VOLUME_QUEUES,
    controler_le_document,
    creer_une_piece,
    double_cliquer,
    poser,
    regler,
    volumes_usines,
)
from tests.qtest.pieces import assemblages, erreurs_python

ANGLE_RETOUCHE = 12.0


def setUpModule() -> None:
    unittest.addModuleCleanup(activer_faulthandler())


class DeuxDocuments(Etapes):
    """Étapes jouées dans l'ordre ; à chaque étape, le geste est fait dans un document puis
    dans l'autre."""

    docs: ClassVar[list[Any]]
    hotes: ClassVar[dict[str, Any]]
    invitees: ClassVar[dict[str, Any]]

    @classmethod
    def setUpClass(cls) -> None:
        cls.docs = []
        for nom in ("ScenarioDeuxDocumentsA", "ScenarioDeuxDocumentsB"):
            doc = preparer(nom)
            cls.addClassCleanup(fermer, doc)
            cls.docs.append(doc)
        cls.hotes, cls.invitees = {}, {}
        vider_la_vue_rapport()

    def test_1_piece_a_plat_dans_chacun(self) -> None:
        for doc in self.docs:
            passer_a(doc)
            self.hotes[doc.Name] = creer_une_piece(doc)
        for doc in self.docs:
            self.assertEqual(len(doc.Objects), 1, doc.Name)
            self.assertIs(self.hotes[doc.Name].Document, doc)

    def test_2_piece_debout_dans_chacun(self) -> None:
        for doc in reversed(self.docs):
            passer_a(doc)
            invitee = creer_une_piece(doc, angle_y=90.0)
            poser(doc, invitee, App.Vector(LONGUEUR - EPAISSEUR, 0, EPAISSEUR + LONGUEUR))
            self.invitees[doc.Name] = invitee
        for doc in self.docs:
            self.assertEqual(len(doc.Objects), 2, doc.Name)

    def test_3_panneau_ouvert_dans_l_un_pendant_qu_on_regarde_l_autre(self) -> None:
        """Le panneau de la queue d'aronde reste celui du premier document pendant un
        aller-retour vers le second, où rien n'a été créé."""
        premier, second = self.docs
        passer_a(premier)
        selectionner(self.invitees[premier.Name], self.hotes[premier.Name])
        lancer(QUEUE_D_ARONDE)
        form = formulaire(PANNEAU_ASSEMBLAGE)
        regler(form, "TailCount", str(QUEUES))
        passer_a(second)
        self.assertEqual(assemblages(second), [])
        self.assertEqual(len(second.Objects), 2)
        passer_a(premier)
        self.assertTrue(panneau_ouvert(), "panneau fermé par l'aller-retour")
        form = formulaire(PANNEAU_ASSEMBLAGE)
        regler(form, "PinWidth", f"{LARGEUR_GRIFFE:g} mm")
        regler(form, "Angle", f"{ANGLE:g}")
        cliquer(bouton_ok())
        self.assertFalse(panneau_ouvert())
        self.assertEqual(len(assemblages(premier)), 1)
        self.assertEqual(assemblages(second), [])

    def test_4_meme_assemblage_dans_le_second(self) -> None:
        second = self.docs[1]
        passer_a(second)
        selectionner(self.invitees[second.Name], self.hotes[second.Name])
        lancer(QUEUE_D_ARONDE)
        form = formulaire(PANNEAU_ASSEMBLAGE)
        regler(form, "TailCount", str(QUEUES))
        regler(form, "PinWidth", f"{LARGEUR_GRIFFE:g} mm")
        regler(form, "Angle", f"{ANGLE:g}")
        cliquer(bouton_ok())
        self.assertFalse(panneau_ouvert())

    def test_5_les_deux_documents_sont_identiques(self) -> None:
        for doc in self.docs:
            with self.subTest(document=doc.Name):
                (assemblage,) = assemblages(doc)
                self.assertTrue(assemblage.isValid(), assemblage.getStatusString())
                self.assertIs(assemblage.HostPart.Document, doc)
                griffes, queues = volumes_usines(self.hotes[doc.Name], self.invitees[doc.Name])
                self.assertAlmostEqual(griffes, VOLUME_BRUT - VOLUME_QUEUES, delta=TOLERANCE_MM3)
                self.assertAlmostEqual(queues, VOLUME_BRUT + VOLUME_QUEUES, delta=TOLERANCE_MM3)
                controler_le_document(self, doc)
        premier, second = self.docs
        self.assertEqual(premier.UndoNames, second.UndoNames)
        self.assertEqual(
            [obj.TypeId for obj in premier.Objects], [obj.TypeId for obj in second.Objects]
        )

    def test_6_modifier_l_un_ne_touche_pas_l_autre(self) -> None:
        premier, second = self.docs
        passer_a(second)
        (assemblage,) = assemblages(second)
        double_cliquer(assemblage)
        taper(enfant(formulaire(PANNEAU_ASSEMBLAGE), "Angle"), f"{ANGLE_RETOUCHE:g}")
        cliquer(bouton_ok())
        self.assertAlmostEqual(assemblage.Angle.Value, ANGLE_RETOUCHE)
        self.assertAlmostEqual(assemblages(premier)[0].Angle.Value, ANGLE)
        self.assertEqual(len(second.UndoNames), len(premier.UndoNames) + 1)
        passer_a(premier)
        lancer("Std_Undo")
        self.assertEqual(assemblages(premier), [], "Ctrl+Z n'a pas agi sur le document actif")
        self.assertEqual(len(assemblages(second)), 1)
        self.assertAlmostEqual(assemblage.Angle.Value, ANGLE_RETOUCHE)
        lancer("Std_Redo")
        premier.recompute()
        for doc in self.docs:
            controler_le_document(self, doc)
        self.assertEqual(erreurs_python(vue_rapport()), [])
