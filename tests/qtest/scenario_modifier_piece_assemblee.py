# SPDX-License-Identifier: LGPL-2.1-or-later
"""Scénario QTest S4 : modifier les cotes d'une pièce déjà assemblée.

Sur l'angle à queue d'aronde (``angle_a_queues.py``), la pièce à griffes est rouverte par
double-clic et ses cotes retapées au clavier. L'assemblage doit suivre : pièces usinées
recalculées, pièce à queues reposée quand l'épaisseur de la pièce à griffes change.
"""

from __future__ import annotations

import unittest
from typing import Any, ClassVar

from tests.qtest.aides import (
    Etapes,
    activer_faulthandler,
    bouton_ok,
    cliquer,
    enfant,
    fermer,
    formulaire,
    lancer,
    preparer,
    taper,
)
from tests.qtest.angle_a_queues import (
    ANGLE,
    EPAISSEUR,
    LARGEUR,
    LONGUEUR,
    PANNEAU_PIECE,
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

MODIFICATION = "Modifier une pièce de bois"


def setUpModule() -> None:
    unittest.addModuleCleanup(activer_faulthandler())


def retaper(piece: Any, champ: str, texte: str) -> None:
    """Double-clic sur ``piece``, ``texte`` tapé dans ``champ``, bouton OK."""
    double_cliquer(piece)
    taper(enfant(formulaire(PANNEAU_PIECE), champ), texte)
    cliquer(bouton_ok())


class ModifierUnePieceAssemblee(Etapes):
    """Étapes numérotées, jouées dans l'ordre sur le même document."""

    doc: ClassVar[Any]
    hote: ClassVar[Any]
    invitee: ClassVar[Any]
    assemblage: ClassVar[Any]

    @classmethod
    def setUpClass(cls) -> None:
        cls.doc = preparer("ScenarioModifierPieceAssemblee")
        cls.addClassCleanup(fermer, cls.doc)
        cls.hote, cls.invitee, cls.assemblage = jouer(cls.doc)
        cls.doc.clearUndos()

    def test_1_elargir_la_piece_a_griffes(self) -> None:
        """Largeur 200 -> 300 : les queues ne changent pas, la pièce à griffes garde ses
        logements sur les 200 mm du contact."""
        retaper(self.hote, "widthEdit", "300 mm")
        self.assertAlmostEqual(self.hote.Width.Value, 300.0, delta=TOLERANCE_MM)
        hote, invitee = volumes_usines(self.hote, self.invitee)
        self.assertAlmostEqual(
            hote, LONGUEUR * 300.0 * EPAISSEUR - VOLUME_QUEUES, delta=TOLERANCE_MM3
        )
        self.assertAlmostEqual(invitee, VOLUME_BRUT + VOLUME_QUEUES, delta=TOLERANCE_MM3)
        self.assertEqual(self.doc.UndoNames, [MODIFICATION])
        controler_le_document(self, self.doc)

    def test_2_epaissir_la_piece_a_griffes(self) -> None:
        """Épaisseur 22 -> 30 : la pièce à queues, posée dessus, monte de 8 mm ; les queues
        traversent la nouvelle épaisseur."""
        retaper(self.hote, "thicknessEdit", "30 mm")
        self.assertAlmostEqual(self.hote.Thickness.Value, 30.0, delta=TOLERANCE_MM)
        self.assertAlmostEqual(self.invitee.Placement.Base.z, 30.0 + LONGUEUR, delta=TOLERANCE_MM)
        queues = volume_des_queues(ANGLE, epaisseur_hote=30.0)
        hote, invitee = volumes_usines(self.hote, self.invitee)
        self.assertAlmostEqual(hote, LONGUEUR * 300.0 * 30.0 - queues, delta=TOLERANCE_MM3)
        self.assertAlmostEqual(invitee, VOLUME_BRUT + queues, delta=TOLERANCE_MM3)
        controler_le_document(self, self.doc)

    def test_3_annuler_les_deux_modifications(self) -> None:
        """Deux Ctrl+Z : retour à l'angle du début, pièce à queues redescendue."""
        self.assertEqual(self.doc.UndoNames, [MODIFICATION, MODIFICATION])
        lancer("Std_Undo")
        lancer("Std_Undo")
        self.doc.recompute()
        self.assertAlmostEqual(self.hote.Width.Value, LARGEUR, delta=TOLERANCE_MM)
        self.assertAlmostEqual(self.hote.Thickness.Value, EPAISSEUR, delta=TOLERANCE_MM)
        self.assertAlmostEqual(
            self.invitee.Placement.Base.z, EPAISSEUR + LONGUEUR, delta=TOLERANCE_MM
        )
        hote, invitee = volumes_usines(self.hote, self.invitee)
        self.assertAlmostEqual(hote, VOLUME_BRUT - VOLUME_QUEUES, delta=TOLERANCE_MM3)
        self.assertAlmostEqual(invitee, VOLUME_BRUT + VOLUME_QUEUES, delta=TOLERANCE_MM3)
        controler_le_document(self, self.doc)
