# SPDX-License-Identifier: LGPL-2.1-or-later
"""Scénario QTest S3 : un panneau annulé ne laisse aucune trace.

Chaque panneau est ouvert, une valeur y est tapée (le document change, l'aperçu est recalculé),
puis il est refermé par le bouton « Annuler » ou par la touche Échap. Le document doit revenir
exactement à son état d'avant : mêmes objets, mêmes cotes et volumes, même historique
d'annulation, aucune transaction ouverte, affichage rétabli (transparence d'édition, visibilité).
"""

from __future__ import annotations

import unittest
from collections.abc import Callable
from typing import Any, ClassVar

from tests.qtest.aides import (
    activer_faulthandler,
    appuyer_sur_echap,
    bouton_annuler,
    cliquer,
    enfant,
    fermer,
    formulaire,
    lancer,
    panneau_ouvert,
    preparer,
    selectionner,
    taper,
)
from tests.qtest.angle_a_queues import (
    PANNEAU_ASSEMBLAGE,
    PANNEAU_PIECE,
    PIECE_EN_BOIS,
    QUEUE_D_ARONDE,
    affichage,
    controler_le_document,
    deux_pieces,
    double_cliquer,
    jouer,
    regler,
)
from tests.qtest.pieces import volume

Etat = dict[str, object]


def setUpModule() -> None:
    unittest.addModuleCleanup(activer_faulthandler())


def etat(doc: Any) -> Etat:
    """Tout ce qu'un panneau annulé doit laisser intact."""
    objets = {}
    for obj in doc.Objects:
        objets[obj.Name] = (volume(obj), str(getattr(obj, "Placement", "")))
    return {
        "objets": objets,
        "affichage": affichage(doc),
        "annuler": list(doc.UndoNames),
        "retablir": list(doc.RedoNames),
    }


def verifier_le_retour(test: unittest.TestCase, doc: Any, avant: Etat) -> None:
    test.assertFalse(panneau_ouvert(), "panneau resté ouvert")
    test.assertEqual(etat(doc), avant)
    controler_le_document(test, doc)


def annuler_par_le_bouton(_champ: Any) -> None:
    cliquer(bouton_annuler())


FERMETURES: dict[str, Callable[[Any], None]] = {
    "bouton Annuler": annuler_par_le_bouton,
    "touche Échap": appuyer_sur_echap,
}


class AnnulationDesPanneaux(unittest.TestCase):
    """Les panneaux de création, sur un document de deux pièces en angle."""

    doc: ClassVar[Any]
    pieces: ClassVar[tuple[Any, Any]]

    @classmethod
    def setUpClass(cls) -> None:
        cls.doc = preparer("ScenarioAnnulationCreation")
        cls.addClassCleanup(fermer, cls.doc)
        cls.pieces = deux_pieces(cls.doc)

    def test_creation_d_une_piece_annulee(self) -> None:
        for nom, fermeture in FERMETURES.items():
            with self.subTest(fermeture=nom):
                avant = etat(self.doc)
                selectionner()
                lancer(PIECE_EN_BOIS)
                champ = enfant(formulaire(PANNEAU_PIECE), "lengthEdit")
                taper(champ, "300 mm")
                self.assertEqual(len(self.doc.Objects), 3, "pièce en cours de création absente")
                fermeture(champ)
                verifier_le_retour(self, self.doc, avant)

    def test_creation_d_un_assemblage_annulee(self) -> None:
        hote, invitee = self.pieces
        for nom, fermeture in FERMETURES.items():
            with self.subTest(fermeture=nom):
                avant = etat(self.doc)
                selectionner(invitee, hote)
                lancer(QUEUE_D_ARONDE)
                form = formulaire(PANNEAU_ASSEMBLAGE)
                regler(form, "Angle", "20")
                self.assertEqual(len(self.doc.Objects), 5, "aperçu de l'assemblage absent")
                fermeture(enfant(form, "Angle"))
                selectionner()
                verifier_le_retour(self, self.doc, avant)


class AnnulationDesModifications(unittest.TestCase):
    """Les panneaux de modification, sur l'angle à queue d'aronde déjà assemblé."""

    doc: ClassVar[Any]
    hote: ClassVar[Any]
    assemblage: ClassVar[Any]

    @classmethod
    def setUpClass(cls) -> None:
        cls.doc = preparer("ScenarioAnnulationModification")
        cls.addClassCleanup(fermer, cls.doc)
        cls.hote, _invitee, cls.assemblage = jouer(cls.doc)

    def test_modification_d_un_assemblage_annulee(self) -> None:
        for nom, fermeture in FERMETURES.items():
            with self.subTest(fermeture=nom):
                avant = etat(self.doc)
                double_cliquer(self.assemblage)
                champ = enfant(formulaire(PANNEAU_ASSEMBLAGE), "Angle")
                taper(champ, "20")
                self.assertAlmostEqual(self.assemblage.Angle.Value, 20.0)
                fermeture(champ)
                self.assertAlmostEqual(self.assemblage.Angle.Value, 10.0)
                verifier_le_retour(self, self.doc, avant)

    def test_modification_d_une_piece_assemblee_annulee(self) -> None:
        for nom, fermeture in FERMETURES.items():
            with self.subTest(fermeture=nom):
                avant = etat(self.doc)
                double_cliquer(self.hote)
                champ = enfant(formulaire(PANNEAU_PIECE), "widthEdit")
                taper(champ, "300 mm")
                self.assertAlmostEqual(self.hote.Width.Value, 300.0)
                fermeture(champ)
                self.assertAlmostEqual(self.hote.Width.Value, 200.0)
                verifier_le_retour(self, self.doc, avant)
