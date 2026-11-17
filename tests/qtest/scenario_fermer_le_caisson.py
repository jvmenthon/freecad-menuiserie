# SPDX-License-Identifier: LGPL-2.1-or-later
"""Scénario QTest S23 : « Fermer le caisson » (ADR 0064, critère FC8).

Une planche de 600 x 400 x 18 mm est sélectionnée, la commande ouvre son panneau : hauteur
retapée, élément coché par la case puis décoché par le schéma, avant retourné, assemblage changé ;
l'aperçu suit dans le document. « Annuler » rend un document identique ; « OK » ne laisse
qu'une seule
transaction « Fermer le caisson » et un ensemble « Caisson ».
"""

from __future__ import annotations

import unittest
from typing import Any, ClassVar

from freecad.menuiserie import api
from tests.qtest.aides import (
    Etapes,
    activer_faulthandler,
    bouton_annuler,
    bouton_ok,
    choisir,
    cliquer,
    cliquer_en,
    enfant,
    fermer,
    formulaire,
    lancer,
    panneau_ouvert,
    preparer,
    selectionner,
    taper,
)
from tests.qtest.angle_a_queues import controler_le_document
from tests.qtest.pieces import commande_active, du_type

COMMANDE = "Menuiserie_CloseCarcass"
PANNEAU = "ClosingTaskPanel"
TYPE_PIECE = "Menuiserie::WoodPart"
HAUTEUR = 300.0
TRANSACTION = "Fermer le caisson"


def setUpModule() -> None:
    unittest.addModuleCleanup(activer_faulthandler())


def empreinte(doc: Any) -> list[tuple[str, str]]:
    """Objets du document (nom, type), pour comparer avant et après une annulation."""
    return sorted((objet.Name, objet.TypeId) for objet in doc.Objects)


class FermerLeCaisson(Etapes):
    """Étapes jouées dans l'ordre sur le même document."""

    doc: ClassVar[Any]
    ancre: ClassVar[Any]
    avant: ClassVar[list[tuple[str, str]]]

    @classmethod
    def setUpClass(cls) -> None:
        cls.doc = preparer("ScenarioFermerLeCaisson")
        cls.addClassCleanup(fermer, cls.doc)
        cls.ancre = api.make_wood_part(600.0, 400.0, 18.0, doc=cls.doc)
        cls.avant = empreinte(cls.doc)

    def pieces(self) -> list[Any]:
        return du_type(self.doc, TYPE_PIECE)

    def test_1_commande_grisee_sans_selection(self) -> None:
        selectionner()
        self.assertFalse(commande_active(COMMANDE))
        selectionner(self.ancre)
        self.assertTrue(commande_active(COMMANDE))

    def test_2_apercu_suit_les_champs_puis_annuler(self) -> None:
        selectionner(self.ancre)
        lancer(COMMANDE)
        form = formulaire(PANNEAU)
        self.assertEqual(enfant(form, "errorLabel").text(), "")
        apercu = len(self.pieces())
        self.assertGreater(apercu, 1, "aucun aperçu")
        taper(enfant(form, "height"), f"{HAUTEUR:g} mm")
        self.assertEqual(enfant(form, "errorLabel").text(), "")
        # L'avant est coché par la case : une pièce de plus ; décoché par le schéma : une de moins.
        cliquer(enfant(form, "element_front"))
        self.assertEqual(len(self.pieces()), apercu + 1)
        schema = enfant(form, "closingSchema")
        point = schema.position_of("front")
        self.assertIsNotNone(point, "l'avant n'est pas cliquable dans le schéma")
        cliquer_en(schema, *point)
        self.assertEqual(len(self.pieces()), apercu)
        self.assertFalse(enfant(form, "element_front").isChecked())
        cliquer(enfant(form, "turnFront"))
        choisir(enfant(form, "joinery"), 1)
        self.assertEqual(enfant(form, "errorLabel").text(), "")
        cliquer(bouton_annuler())
        self.assertFalse(panneau_ouvert())
        self.assertEqual(empreinte(self.doc), self.avant, "l'annulation laisse des objets")
        self.assertEqual(self.doc.UndoNames, [])

    def test_3_ok_une_seule_transaction(self) -> None:
        selectionner(self.ancre)
        lancer(COMMANDE)
        form = formulaire(PANNEAU)
        taper(enfant(form, "height"), f"{HAUTEUR:g} mm")
        self.assertEqual(enfant(form, "errorLabel").text(), "")
        cliquer(bouton_ok())
        self.assertFalse(panneau_ouvert())
        self.assertEqual(self.doc.UndoNames, [TRANSACTION])
        ensembles = du_type(self.doc, "Menuiserie::Furniture")
        self.assertEqual([e.Template for e in ensembles], ["ClosedCarcass"])
        self.assertGreaterEqual(len(self.pieces()), 4)
        self.assertEqual(self.ancre.Length.Value, 600.0, "l'ancre a été redimensionnée")
        controler_le_document(self, self.doc)
        self.doc.undo()
        self.assertEqual(empreinte(self.doc), self.avant)
        self.doc.redo()


if __name__ == "__main__":
    unittest.main()
