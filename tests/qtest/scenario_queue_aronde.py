# SPDX-License-Identifier: LGPL-2.1-or-later
"""Scénario QTest : deux pièces de 20 cm de large, la seconde tournée de 90°, assemblées par une
queue d'aronde à 10° avec 4 griffes de 30 mm.

Lancé dans le vrai FreeCAD, par son mode test (unittest) :

    xvfb-run -a freecad -t tests.qtest.scenario_queue_aronde

Gestes joués sur les vrais widgets (clavier et souris de QTest) : commande « Pièce en bois » et
son panneau (largeur, longueur, angle autour de Y, bouton OK), commande « Queue d'aronde » et son
panneau (cases « Auto » décochées, nombre de queues, largeur des griffes, angle, bouton OK). Les
gestes sont dans ``angle_a_queues.py``, partagés avec les autres scénarios.
"""

from __future__ import annotations

import unittest
from typing import Any, ClassVar

import FreeCAD as App

from tests.gui.verifications_assemblages import usinee_de
from tests.qtest.aides import activer_faulthandler, capturer, fermer, preparer, selectionner
from tests.qtest.angle_a_queues import (
    DEPLACEMENT,
    EPAISSEUR,
    LONGUEUR,
    TOLERANCE_MM,
    TOLERANCE_MM3,
    TYPE_QUEUE_D_ARONDE,
    VOLUME_BRUT,
    VOLUME_QUEUES,
    controler_le_document,
    jouer,
)


def setUpModule() -> None:
    unittest.addModuleCleanup(activer_faulthandler())


class QueueDAronde(unittest.TestCase):
    """Le scénario complet, puis les vérifications sur le document obtenu."""

    doc: ClassVar[Any]
    hote: ClassVar[Any]
    invitee: ClassVar[Any]
    assemblage: ClassVar[Any]

    @classmethod
    def setUpClass(cls) -> None:
        cls.doc = preparer("ScenarioQueueDAronde")
        cls.addClassCleanup(fermer, cls.doc)
        cls.hote, cls.invitee, cls.assemblage = jouer(cls.doc)
        selectionner()
        capturer("queue-aronde")

    def test_dimensions_des_pieces(self) -> None:
        for piece in (self.hote, self.invitee):
            with self.subTest(piece=piece.Label):
                self.assertAlmostEqual(piece.Length.Value, LONGUEUR, delta=TOLERANCE_MM)
                self.assertAlmostEqual(piece.Width.Value, 200.0, delta=TOLERANCE_MM)  # 20 cm
                self.assertAlmostEqual(piece.Thickness.Value, EPAISSEUR, delta=TOLERANCE_MM)

    def test_placements(self) -> None:
        self.assertTrue(self.hote.Placement.isSame(App.Placement(), TOLERANCE_MM))
        attendu = App.Placement(
            App.Vector(LONGUEUR - EPAISSEUR, 0, EPAISSEUR + LONGUEUR),
            App.Rotation(App.Vector(0, 1, 0), 90),
        )
        self.assertTrue(
            self.invitee.Placement.isSame(attendu, TOLERANCE_MM), self.invitee.Placement
        )

    def test_parametres_de_l_assemblage(self) -> None:
        joint = self.assemblage
        self.assertEqual(joint.TypeId, "Part::FeaturePython")
        self.assertEqual(joint.Proxy.TYPE, TYPE_QUEUE_D_ARONDE)
        self.assertEqual((joint.HostPart, joint.GuestPart), (self.hote, self.invitee))
        # Valeurs de la demande écrites en clair : 4 griffes (donc 3 queues) de 30 mm, à 10°.
        self.assertEqual(joint.TailCount, 3)
        self.assertAlmostEqual(joint.PinWidth.Value, 30.0, delta=TOLERANCE_MM)
        self.assertAlmostEqual(joint.Angle.Value, 10.0, delta=TOLERANCE_MM)

    def test_assemblage_valide(self) -> None:
        controler_le_document(self, self.doc)

    def test_pieces_usinees(self) -> None:
        """Queues ajoutées à la pièce 2, logements enlevés dans la pièce 1 : solides valides,
        volumes attendus, aucune matière commune."""
        hote, invitee = (usinee_de(piece) for piece in (self.hote, self.invitee))
        for usinee in (hote, invitee):
            with self.subTest(piece=usinee.Label):
                self.assertTrue(usinee.Shape.isValid())
                self.assertEqual(len(usinee.Shape.Solids), 1)
        self.assertAlmostEqual(hote.Shape.Volume, VOLUME_BRUT - VOLUME_QUEUES, delta=TOLERANCE_MM3)
        self.assertAlmostEqual(
            invitee.Shape.Volume, VOLUME_BRUT + VOLUME_QUEUES, delta=TOLERANCE_MM3
        )
        self.assertAlmostEqual(hote.Shape.common(invitee.Shape).Volume, 0.0, delta=TOLERANCE_MM3)

    def test_annulation(self) -> None:
        """Une entrée d'annulation par geste de l'utilisateur (libellés sources de l'atelier,
        sauf « Déplacer une pièce », écrit par ce scénario)."""
        self.assertEqual(
            self.doc.UndoNames,
            [
                "Créer un assemblage à queue d'aronde",
                DEPLACEMENT,
                "Créer une pièce de bois",
                "Créer une pièce de bois",
            ],
        )
