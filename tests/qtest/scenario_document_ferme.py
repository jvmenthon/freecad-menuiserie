# SPDX-License-Identifier: LGPL-2.1-or-later
"""Scénario QTest S6 : changer de document ou le fermer pendant qu'un panneau est ouvert.

- Un autre document est créé pendant la création d'un assemblage : le panneau continue d'éditer
  son document, les commandes de l'atelier restent inactives, « OK » valide dans le bon document.
- Le document est fermé pendant la modification d'un assemblage, puis pendant la création d'une
  pièce : le panneau se ferme de lui-même, sans erreur Python dans la vue rapport.
"""

from __future__ import annotations

import unittest
from typing import Any

import FreeCAD as App
import FreeCADGui as Gui

from tests.gui.verifications_double_clic import vue_3d_active
from tests.qtest.aides import (
    activer_faulthandler,
    attendre,
    bouton_ok,
    cliquer,
    enfant,
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
    PANNEAU_ASSEMBLAGE,
    PANNEAU_PIECE,
    PIECE_EN_BOIS,
    QUEUE_D_ARONDE,
    TYPE_QUEUE_D_ARONDE,
    controler_le_document,
    deux_pieces,
    double_cliquer,
    jouer,
    regler,
)


def setUpModule() -> None:
    unittest.addModuleCleanup(activer_faulthandler())


def fermer_tous_les_documents() -> None:
    if panneau_ouvert():
        Gui.Control.activeTaskDialog().reject()
    for nom in list(App.listDocuments()):
        App.closeDocument(nom)
    traiter_les_evenements()


def fermer_pendant_le_panneau(doc: Any) -> None:
    """Fichier > Fermer pendant qu'un panneau est ouvert ; laisse passer les fins différées."""
    App.closeDocument(doc.Name)
    attendre(lambda: not panneau_ouvert())
    traiter_les_evenements()


class DocumentFermeOuChange(unittest.TestCase):
    def setUp(self) -> None:
        self.addCleanup(fermer_tous_les_documents)
        vider_la_vue_rapport()

    def assert_aucune_erreur_python(self) -> None:
        rapport = vue_rapport()
        self.assertNotIn("Traceback", rapport)
        self.assertNotIn("Error", rapport)

    def test_autre_document_pendant_la_creation_d_un_assemblage(self) -> None:
        doc = preparer("ScenarioPanneauPremierDocument")
        hote, invitee = deux_pieces(doc)
        selectionner(invitee, hote)
        lancer(QUEUE_D_ARONDE)
        form = formulaire(PANNEAU_ASSEMBLAGE)
        regler(form, "Angle", "20")
        autre = App.newDocument("ScenarioPanneauAutreDocument")
        traiter_les_evenements()
        self.assertEqual(App.ActiveDocument.Name, autre.Name)
        self.assertTrue(panneau_ouvert(), "panneau fermé par le changement de document")
        for commande in (PIECE_EN_BOIS, QUEUE_D_ARONDE):
            self.assertFalse(Gui.Command.get(commande).isActive(), f"{commande} active")
        taper(enfant(form, "Angle"), "15")
        cliquer(bouton_ok())
        self.assertFalse(panneau_ouvert())
        self.assertEqual(autre.Objects, [], "le panneau a écrit dans l'autre document")
        (assemblage,) = (
            obj for obj in doc.Objects if getattr(obj.Proxy, "TYPE", "") == TYPE_QUEUE_D_ARONDE
        )
        self.assertAlmostEqual(assemblage.Angle.Value, 15.0)
        self.assertEqual(doc.UndoNames[0], "Créer un assemblage à queue d'aronde")
        controler_le_document(self, doc)
        self.assert_aucune_erreur_python()

    def test_document_ferme_pendant_la_modification_d_un_assemblage(self) -> None:
        doc = preparer("ScenarioFermetureModification")
        _hote, _invitee, assemblage = jouer(doc)
        double_cliquer(assemblage)
        taper(enfant(formulaire(PANNEAU_ASSEMBLAGE), "Angle"), "12")
        fermer_pendant_le_panneau(doc)
        self.assertFalse(panneau_ouvert(), "panneau resté ouvert sur un document fermé")
        self.assertEqual(list(App.listDocuments()), [])
        self.assert_aucune_erreur_python()

    def test_document_ferme_pendant_la_creation_d_une_piece(self) -> None:
        doc = preparer("ScenarioFermetureCreation")
        selectionner()
        lancer(PIECE_EN_BOIS)
        taper(enfant(formulaire(PANNEAU_PIECE), "lengthEdit"), "300 mm")
        fermer_pendant_le_panneau(doc)
        self.assertFalse(panneau_ouvert(), "panneau resté ouvert sur un document fermé")
        self.assert_aucune_erreur_python()

    def test_l_atelier_reste_utilisable_ensuite(self) -> None:
        """Après une fermeture forcée, un nouveau document accepte de nouveau les commandes."""
        doc = preparer("ScenarioFermetureAvant")
        selectionner()
        lancer(PIECE_EN_BOIS)
        fermer_pendant_le_panneau(doc)
        suivant = preparer("ScenarioFermetureApres")
        vue_3d_active(suivant)
        jouer(suivant)
        controler_le_document(self, suivant)
        self.assert_aucune_erreur_python()
