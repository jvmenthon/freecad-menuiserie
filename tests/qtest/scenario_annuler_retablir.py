# SPDX-License-Identifier: LGPL-2.1-or-later
"""Scénario QTest S1 : annuler puis rétablir de bout en bout.

L'angle à queue d'aronde est construit (``angle_a_queues.py``), puis Ctrl+Z jusqu'au document
vide et Ctrl+Y jusqu'à la fin, par les commandes « Annuler » et « Rétablir » de FreeCAD. Attrape
les transactions mal fermées, les objets orphelins et les états d'affichage restés dans
l'historique.
"""

from __future__ import annotations

import unittest
from typing import Any, ClassVar

from tests.gui.verifications_assemblages import usinee_de
from tests.qtest.aides import activer_faulthandler, fermer, lancer, preparer
from tests.qtest.angle_a_queues import (
    TOLERANCE_MM3,
    VOLUME_BRUT,
    controler_le_document,
    jouer,
    volumes_usines,
)

ANNULER, RETABLIR = "Std_Undo", "Std_Redo"


def setUpModule() -> None:
    unittest.addModuleCleanup(activer_faulthandler())


def etat(doc: Any) -> dict[str, tuple[str, float]]:
    """Nom de chaque objet -> (type, volume arrondi au mm³) : ce que l'annulation doit rendre."""
    return {obj.Name: (obj.TypeId, volume(obj)) for obj in doc.Objects}


def volume(obj: Any) -> float:
    """Volume arrondi au mm³ ; 0 pour un objet sans forme (l'assemblage n'en a pas)."""
    forme = getattr(obj, "Shape", None)
    return 0.0 if forme is None or forme.isNull() else float(round(forme.Volume))


class AnnulerRetablir(unittest.TestCase):
    """Les étapes s'enchaînent sur le même document : méthodes numérotées, jouées dans l'ordre."""

    doc: ClassVar[Any]
    pieces: ClassVar[tuple[Any, Any]]
    nom_assemblage: ClassVar[str]
    etat_final: ClassVar[dict[str, tuple[str, float]]]
    entrees: ClassVar[list[str]]

    @classmethod
    def setUpClass(cls) -> None:
        cls.doc = preparer("ScenarioAnnulerRetablir")
        cls.addClassCleanup(fermer, cls.doc)
        hote, invitee, assemblage = jouer(cls.doc)
        cls.pieces = (hote, invitee)
        cls.nom_assemblage = assemblage.Name
        cls.etat_final = etat(cls.doc)
        cls.entrees = list(cls.doc.UndoNames)

    def test_1_annuler_l_assemblage(self) -> None:
        """Un Ctrl+Z : l'assemblage et les deux pièces usinées disparaissent, les brutes restent
        entières."""
        lancer(ANNULER)
        self.assertIsNone(self.doc.getObject(self.nom_assemblage))
        self.assertEqual(self.doc.Objects, list(self.pieces))
        for piece in self.pieces:
            self.assertAlmostEqual(piece.Shape.Volume, VOLUME_BRUT, delta=TOLERANCE_MM3)
            self.assertTrue(piece.ViewObject.Visibility, f"{piece.Label} restée masquée")
        controler_le_document(self, self.doc)

    def test_2_annuler_jusqu_au_document_vide(self) -> None:
        for _ in self.entrees[1:]:
            lancer(ANNULER)
        self.assertEqual(self.doc.Objects, [])
        self.assertEqual(self.doc.UndoNames, [])
        self.assertEqual(self.doc.RedoNames, self.entrees[::-1])

    def test_3_retablir_jusqu_a_la_fin(self) -> None:
        for _ in self.entrees:
            lancer(RETABLIR)
        self.doc.recompute()
        self.assertEqual(self.doc.UndoNames, self.entrees)
        self.assertEqual(self.doc.RedoNames, [])
        self.assertEqual(etat(self.doc), self.etat_final)
        controler_le_document(self, self.doc)

    def test_4_pieces_usinees_retablies(self) -> None:
        """Les objets rétablis sont de nouveau reliés : brutes masquées par leurs pièces usinées,
        mêmes volumes qu'avant l'annulation."""
        hote, invitee = (self.doc.getObject(piece.Name) for piece in self.pieces)
        usines = volumes_usines(hote, invitee)
        for piece in (hote, invitee):
            self.assertFalse(piece.ViewObject.Visibility, f"{piece.Label} brute affichée")
            self.assertTrue(usinee_de(piece).ViewObject.Visibility)
        self.assertAlmostEqual(sum(usines), 2 * VOLUME_BRUT, delta=TOLERANCE_MM3)
        self.assertNotAlmostEqual(usines[0], VOLUME_BRUT, delta=TOLERANCE_MM3)
