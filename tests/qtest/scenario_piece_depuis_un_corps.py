# SPDX-License-Identifier: LGPL-2.1-or-later
"""Scénario QTest S17 : une pièce en bois faite d'un corps PartDesign, puis assemblée.

Un corps (une planche avec une encoche) converti par la commande « Convertir en pièce en bois »
et son panneau, un tenon-mortaise posé dessus, puis le corps allongé : la pièce et l'assemblage
suivent. Le corps à plusieurs solides (issue #257) viendra avec son lot.

Non simulé : le dessin du corps dans PartDesign (créé et modifié par le script).
"""

from __future__ import annotations

import unittest
from typing import Any, ClassVar

import FreeCAD as App

from tests.gui.verifications_assemblages import usinee_de
from tests.qtest.aides import (
    Etapes,
    activer_faulthandler,
    bouton_annuler,
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
    vider_la_vue_rapport,
    vue_rapport,
)
from tests.qtest.angle_a_queues import PANNEAU_ASSEMBLAGE, controler_le_document, double_cliquer
from tests.qtest.pieces import AXE_Z, SECTION, assemblages, erreurs_python, piece

CONVERTIR = "Menuiserie_ShapedPart"
TENON_MORTAISE = "Menuiserie_MortiseTenon"
PANNEAU_PIECE_EN_BOIS = "ShapedPartTaskPanel"
TYPE_PIECE_EN_BOIS = "Menuiserie::ShapedPart"
PLANCHE = (600.0, 60.0, 22.0)
ENCOCHE = (100.0, 20.0, 22.0)
ALLONGEE = 700.0
VOLUME = PLANCHE[0] * PLANCHE[1] * PLANCHE[2] - ENCOCHE[0] * ENCOCHE[1] * ENCOCHE[2]
TOLERANCE_MM3 = 1.0


def setUpModule() -> None:
    unittest.addModuleCleanup(activer_faulthandler())


def planche_a_encoche(doc: Any) -> tuple[Any, Any]:
    """Corps PartDesign : une planche dont un chant a une encoche ; renvoie le corps et sa
    planche (pour l'allonger ensuite)."""
    corps = doc.addObject("PartDesign::Body", "Corps")
    planche = corps.newObject("PartDesign::AdditiveBox", "Planche")
    planche.Length, planche.Width, planche.Height = PLANCHE
    encoche = corps.newObject("PartDesign::SubtractiveBox", "Encoche")
    encoche.Length, encoche.Width, encoche.Height = ENCOCHE
    encoche.Placement = App.Placement(App.Vector(250.0, 40.0, 0.0), App.Rotation())
    doc.recompute()
    return corps, planche


class PieceDepuisUnCorps(Etapes):
    """Étapes jouées dans l'ordre sur le même document."""

    doc: ClassVar[Any]
    corps: ClassVar[Any]
    planche: ClassVar[Any]
    piece_en_bois: ClassVar[Any]
    mortaise: ClassVar[float]

    @classmethod
    def setUpClass(cls) -> None:
        cls.doc = preparer("ScenarioPieceDepuisUnCorps")
        cls.addClassCleanup(fermer, cls.doc)
        cls.corps, cls.planche = planche_a_encoche(cls.doc)
        cls.doc.clearUndos()
        vider_la_vue_rapport()

    def cotes(self) -> tuple[float, float, float]:
        return tuple(
            getattr(self.piece_en_bois, nom).Value for nom in ("Length", "Width", "Thickness")
        )

    def test_1_convertir(self) -> None:
        avant = set(self.doc.Objects)
        selectionner(self.corps)
        lancer(CONVERTIR)
        form = formulaire(PANNEAU_PIECE_EN_BOIS)
        for nom, cote in zip(("lengthEdit", "widthEdit", "thicknessEdit"), PLANCHE, strict=True):
            self.assertAlmostEqual(enfant(form, nom).property("rawValue"), cote, msg=nom)
        taper(enfant(form, "markEdit"), "P1")
        cliquer(bouton_ok())
        self.assertFalse(panneau_ouvert())
        (creee,) = (obj for obj in self.doc.Objects if obj not in avant)
        type(self).piece_en_bois = creee
        self.assertEqual(creee.Proxy.TYPE, TYPE_PIECE_EN_BOIS)
        self.assertEqual(creee.Mark, "P1")
        self.assertEqual(self.cotes(), PLANCHE)
        self.assertAlmostEqual(creee.Shape.Volume, VOLUME, delta=TOLERANCE_MM3)
        self.assertFalse(self.corps.ViewObject.Visibility, "le corps reste affiché sous la pièce")
        self.assertEqual(len(self.doc.UndoNames), 1, self.doc.UndoNames)
        controler_le_document(self, self.doc)

    def test_2_tenon_mortaise_dans_la_piece(self) -> None:
        traverse = piece(self.doc, (280.0, *SECTION), (60.0, 60.0, 0.0), AXE_Z, 90.0, "T")
        self.doc.recompute()
        self.doc.clearUndos()
        selectionner(traverse, self.piece_en_bois)
        lancer(TENON_MORTAISE)
        self.assertEqual(enfant(formulaire(PANNEAU_ASSEMBLAGE), "errorLabel").text(), "")
        cliquer(bouton_ok())
        self.assertFalse(panneau_ouvert())
        (assemblage,) = assemblages(self.doc)
        self.assertTrue(assemblage.isValid(), assemblage.getStatusString())
        usinee = usinee_de(self.piece_en_bois).Shape
        self.assertEqual(len(usinee.Solids), 1)
        self.assertLess(usinee.Volume, VOLUME - TOLERANCE_MM3, "pas de mortaise")
        type(self).mortaise = VOLUME - usinee.Volume
        self.assertEqual(len(self.doc.UndoNames), 1, self.doc.UndoNames)
        controler_le_document(self, self.doc)

    def test_3_le_corps_allonge_la_piece_suit(self) -> None:
        self.planche.Length = ALLONGEE
        self.doc.recompute()
        self.assertEqual(self.cotes(), (ALLONGEE, PLANCHE[1], PLANCHE[2]))
        (assemblage,) = assemblages(self.doc)
        self.assertTrue(assemblage.isValid(), assemblage.getStatusString())
        allonge = VOLUME + (ALLONGEE - PLANCHE[0]) * PLANCHE[1] * PLANCHE[2]
        self.assertAlmostEqual(
            usinee_de(self.piece_en_bois).Shape.Volume, allonge - self.mortaise, delta=TOLERANCE_MM3
        )
        controler_le_document(self, self.doc)

    def test_4_panneau_rouvert_puis_annule(self) -> None:
        annulations = list(self.doc.UndoNames)
        double_cliquer(self.piece_en_bois)
        form = formulaire(PANNEAU_PIECE_EN_BOIS)
        self.assertAlmostEqual(enfant(form, "lengthEdit").property("rawValue"), ALLONGEE)
        self.assertEqual(enfant(form, "markEdit").text(), "P1")
        taper(enfant(form, "markEdit"), "P2")
        cliquer(bouton_annuler())
        self.assertFalse(panneau_ouvert())
        self.assertEqual(self.piece_en_bois.Mark, "P1")
        self.assertEqual(self.doc.UndoNames, annulations)
        controler_le_document(self, self.doc)
        self.assertEqual(erreurs_python(vue_rapport()), [])
