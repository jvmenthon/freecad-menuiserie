# SPDX-License-Identifier: LGPL-2.1-or-later
"""Scénario QTest S7 : supprimer une pièce assemblée, un assemblage, une brute, un ensemble.

Sélection puis commande « Supprimer » de FreeCAD (touche Suppr), avec la réponse de l'utilisateur
aux boîtes de message. Attrape les plantages à la suppression récursive d'un ensemble, les
assemblages orphelins, les boîtes en trop, les erreurs Python de l'interface, et vérifie que
Ctrl+Z rend tout.
"""

from __future__ import annotations

import unittest
from typing import Any

from tests.gui.verifications_assemblages import usinee_de
from tests.qtest.aides import (
    OUI,
    ReponseAuxBoites,
    activer_faulthandler,
    fermer,
    lancer,
    preparer,
    selectionner,
    vider_la_vue_rapport,
    vue_rapport,
)
from tests.qtest.angle_a_queues import (
    TOLERANCE_MM3,
    VOLUME_BRUT,
    VOLUME_QUEUES,
    controler_le_document,
    jouer,
    volumes_usines,
)

SUPPRIMER, ANNULER = "Std_Delete", "Std_Undo"
ENSEMBLE = "Menuiserie_Furniture"
ASSEMBLAGE_LIE = "Menuiserie : assemblage lié"
INCOMPLET = "Assemblage incomplet"


def setUpModule() -> None:
    unittest.addModuleCleanup(activer_faulthandler())


def supprimer(obj: Any, reponse: Any) -> list[str]:
    """Sélectionne ``obj``, lance « Supprimer » et répond ``reponse`` ; renvoie les titres des
    boîtes ouvertes. Les boîtes de FreeCAD (titre selon la langue) sont comptées, pas nommées."""
    selectionner(obj)
    with ReponseAuxBoites(reponse) as boites:
        lancer(SUPPRIMER)
    return [titre for titre, _texte in boites.vues]


class Suppression(unittest.TestCase):
    """Chaque test repart d'un angle à queue d'aronde neuf, dans son propre document."""

    doc: Any
    hote: Any
    invitee: Any
    assemblage: Any

    def setUp(self) -> None:
        self.doc = preparer("ScenarioSuppression")
        self.addCleanup(fermer, self.doc)
        self.hote, self.invitee, self.assemblage = jouer(self.doc)
        self.doc.clearUndos()
        vider_la_vue_rapport()

    def noms(self) -> list[str]:
        return sorted(obj.Name for obj in self.doc.Objects)

    def assert_angle_intact(self) -> None:
        hote, invitee = volumes_usines(self.hote, self.invitee)
        self.assertAlmostEqual(hote, VOLUME_BRUT - VOLUME_QUEUES, delta=TOLERANCE_MM3)
        self.assertAlmostEqual(invitee, VOLUME_BRUT + VOLUME_QUEUES, delta=TOLERANCE_MM3)
        controler_le_document(self, self.doc)

    def annuler_et_verifier(self, avant: list[str]) -> None:
        lancer(ANNULER)
        self.doc.recompute()
        self.assertEqual(self.noms(), avant)
        self.assert_angle_intact()

    def test_piece_usinee_gardee_si_on_annule_la_boite(self) -> None:
        avant = self.noms()
        boites = supprimer(usinee_de(self.hote), "Annuler")
        self.assertEqual(boites, [ASSEMBLAGE_LIE])
        self.assertEqual(self.noms(), avant)
        self.assertEqual(self.doc.UndoNames, [])
        self.assert_angle_intact()

    def test_piece_usinee_supprimee_avec_son_assemblage(self) -> None:
        """La pièce, sa brute et l'assemblage disparaissent ; l'autre pièce redevient une brute
        entière et visible ; Ctrl+Z rend tout."""
        avant = self.noms()
        boites = supprimer(usinee_de(self.hote), "Supprimer")
        self.assertEqual(boites, [ASSEMBLAGE_LIE])
        self.assertEqual(self.doc.Objects, [self.invitee])
        self.assertTrue(self.invitee.ViewObject.Visibility, "pièce restante masquée")
        self.assertAlmostEqual(self.invitee.Shape.Volume, VOLUME_BRUT, delta=TOLERANCE_MM3)
        controler_le_document(self, self.doc)
        self.assertNotIn("Traceback", vue_rapport())
        self.annuler_et_verifier(avant)

    def test_assemblage_supprime(self) -> None:
        """Aucune boîte ; les pièces usinées restent, recalculées sans l'assemblage (spec J3,
        O11) ; Ctrl+Z le rend."""
        avant = self.noms()
        self.assertEqual(supprimer(self.assemblage, "Supprimer"), [])
        self.assertEqual(len(self.doc.Objects), 4)
        for volume in volumes_usines(self.hote, self.invitee):
            self.assertAlmostEqual(volume, VOLUME_BRUT, delta=TOLERANCE_MM3)
        controler_le_document(self, self.doc)
        self.assertNotIn("Traceback", vue_rapport())
        self.annuler_et_verifier(avant)

    def test_brute_supprimee_malgre_l_avertissement(self) -> None:
        """Brute supprimée depuis l'arbre, « Oui » à l'avertissement de FreeCAD (dépendances) :
        l'assemblage passe en erreur avec un message clair, l'interface ne lève rien d'autre ;
        Ctrl+Z répare."""
        avant = self.noms()
        self.assertEqual(len(supprimer(self.hote, OUI)), 1)
        self.doc.recompute()
        self.assertIn("Invalid", self.assemblage.State)
        rapport = vue_rapport()
        self.assertIn(INCOMPLET, rapport)
        # Le panneau « Structure » se rafraîchit sans erreur : seule la trace de l'assemblage
        # incomplet (``ValueError``) est admise.
        self.assertNotIn("TypeError", rapport)
        self.assertNotIn("structure_", rapport)
        self.annuler_et_verifier(avant)

    def test_ensemble_supprime_avec_son_contenu(self) -> None:
        """Ensemble créé autour des deux pièces, puis son Std Part supprimé avec « Oui » à
        « supprimer le contenu » : une seule boîte, tout disparaît sans plantage, Ctrl+Z rend
        tout."""
        selectionner(usinee_de(self.hote), usinee_de(self.invitee))
        lancer(ENSEMBLE)
        selectionner()
        self.doc.clearUndos()
        avant = self.noms()
        (groupe,) = (obj for obj in self.doc.Objects if obj.TypeId == "App::Part")
        self.assertEqual(len(supprimer(groupe, OUI)), 1)
        self.assertEqual(self.doc.Objects, [])
        self.assertNotIn("Traceback", vue_rapport())
        self.annuler_et_verifier(avant)
