# SPDX-License-Identifier: LGPL-2.1-or-later
"""Scénario QTest S13 : la rotation d'une pièce depuis son panneau.

Boutons de quart de tour X, Y, Z et champs d'angle du panneau « Pièce en bois », sur une pièce
libre (angles retapés hors de la forme canonique : le champ est recalculé), sur une pièce
assemblée (la rotation défait l'assemblage : fenêtre « Assemblage défait », réponses « Annuler
le déplacement » puis « Supprimer l'assemblage ») et sur une pièce d'un ensemble.
"""

from __future__ import annotations

import unittest
from typing import Any, ClassVar

import FreeCAD as App

from tests.qtest.aides import (
    Etapes,
    ReponseAuxBoites,
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
from tests.qtest.angle_a_queues import PANNEAU_PIECE, controler_le_document, double_cliquer
from tests.qtest.pieces import (
    assemblages,
    boite_globale,
    cadre,
    erreurs_python,
    piece,
    tenon_mortaise,
)

ENSEMBLE = "Menuiserie_Furniture"
RETIRER = "Menuiserie_FurnitureRemove"
COTES = (500.0, 200.0, 22.0)
ANNULER_LE_DEPLACEMENT = "Annuler le déplacement"
SUPPRIMER_L_ASSEMBLAGE = "Supprimer l'assemblage"
TOLERANCE_MM = 1e-6
TOLERANCE_DEGRES = 0.05  # les champs montrent le dixième de degré


def setUpModule() -> None:
    unittest.addModuleCleanup(activer_faulthandler())


def etendues(membre: Any) -> tuple[float, float, float]:
    englobante = boite_globale(membre)
    return tuple(
        round(cote, 6) for cote in (englobante.XLength, englobante.YLength, englobante.ZLength)
    )


class ScenarioDeRotation(Etapes):
    """Lecture des champs d'angle du panneau ouvert."""

    doc: ClassVar[Any]

    def angles(self) -> tuple[float, float, float]:
        form = formulaire(PANNEAU_PIECE)
        x, y, z = (float(enfant(form, f"angle{axe}Edit").property("rawValue")) for axe in "XYZ")
        return x, y, z

    def verifier_les_angles(self, attendus: tuple[float, float, float]) -> None:
        for lu, attendu in zip(self.angles(), attendus, strict=True):
            self.assertAlmostEqual(lu, attendu, delta=TOLERANCE_DEGRES, msg=str(self.angles()))


class PieceLibre(ScenarioDeRotation):
    """Étapes jouées dans l'ordre : le panneau reste ouvert de l'étape 1 à l'étape 4."""

    libre: ClassVar[Any]
    centre: ClassVar[App.Vector]

    @classmethod
    def setUpClass(cls) -> None:
        cls.doc = preparer("ScenarioRotationLibre")
        cls.addClassCleanup(fermer, cls.doc)
        cls.libre = piece(cls.doc, COTES, repere="L")
        cls.doc.recompute()
        cls.centre = boite_globale(cls.libre).Center
        cls.doc.clearUndos()
        vider_la_vue_rapport()

    def verifier_le_centre(self) -> None:
        ecart = boite_globale(self.libre).Center.distanceToPoint(self.centre)
        self.assertLess(ecart, TOLERANCE_MM, "la pièce ne tourne pas autour de son centre")

    def test_1_quart_de_tour_z(self) -> None:
        double_cliquer(self.libre)
        self.verifier_les_angles((0.0, 0.0, 0.0))
        cliquer(enfant(formulaire(PANNEAU_PIECE), "rotateZButton"))
        self.verifier_les_angles((0.0, 0.0, 90.0))
        self.assertEqual(etendues(self.libre), (COTES[1], COTES[0], COTES[2]))
        self.verifier_le_centre()

    def test_2_angle_tape_hors_forme_canonique(self) -> None:
        """270° tapé : la pièce tourne comme saisi et le champ est recalculé à -90°."""
        champ = enfant(formulaire(PANNEAU_PIECE), "angleZEdit")
        taper(champ, "270")
        self.verifier_les_angles((0.0, 0.0, -90.0))
        self.assertEqual(etendues(self.libre), (COTES[1], COTES[0], COTES[2]))
        taper(champ, "-360")
        self.verifier_les_angles((0.0, 0.0, 0.0))
        self.assertEqual(etendues(self.libre), COTES)
        taper(champ, "45")
        self.verifier_les_angles((0.0, 0.0, 45.0))
        self.verifier_le_centre()
        taper(champ, "0")

    def test_3_quarts_de_tour_x_et_y(self) -> None:
        form = formulaire(PANNEAU_PIECE)
        cliquer(enfant(form, "rotateXButton"))
        self.assertEqual(etendues(self.libre), (COTES[0], COTES[2], COTES[1]))
        self.verifier_les_angles((90.0, 0.0, 0.0))
        cliquer(enfant(form, "rotateYButton"))
        self.assertEqual(etendues(self.libre), (COTES[1], COTES[2], COTES[0]))
        self.verifier_le_centre()
        for _ in range(3):
            cliquer(enfant(form, "rotateYButton"))
        self.assertEqual(etendues(self.libre), (COTES[0], COTES[2], COTES[1]))
        self.verifier_les_angles((90.0, 0.0, 0.0))

    def test_4_valider_puis_annuler(self) -> None:
        cliquer(bouton_ok())
        self.assertFalse(panneau_ouvert())
        self.assertEqual(len(self.doc.UndoNames), 1, self.doc.UndoNames)
        controler_le_document(self, self.doc)
        lancer("Std_Undo")
        self.doc.recompute()
        self.assertEqual(etendues(self.libre), COTES)
        self.verifier_le_centre()
        self.assertEqual(erreurs_python(vue_rapport()), [])


class PieceAssemblee(ScenarioDeRotation):
    """La traverse d'un tenon-mortaise tournée debout : l'assemblage est défait."""

    montant: ClassVar[Any]
    traverse: ClassVar[Any]

    @classmethod
    def setUpClass(cls) -> None:
        cls.doc = preparer("ScenarioRotationAssemblee")
        cls.addClassCleanup(fermer, cls.doc)
        cls.montant, cls.traverse = tenon_mortaise(cls.doc)
        vider_la_vue_rapport()

    def test_1_annuler_le_deplacement(self) -> None:
        double_cliquer(self.traverse)
        avant = self.angles()
        debout = etendues(self.traverse)
        with ReponseAuxBoites(ANNULER_LE_DEPLACEMENT) as boites:
            taper(enfant(formulaire(PANNEAU_PIECE), "angleYEdit"), "90")
        self.assertEqual(len(boites.vues), 1, boites.vues)
        self.assertIn("défait", boites.vues[0][0])
        self.verifier_les_angles(avant)
        self.assertEqual(etendues(self.traverse), debout)
        (assemblage,) = assemblages(self.doc)
        self.assertTrue(assemblage.isValid(), assemblage.getStatusString())

    def test_2_supprimer_l_assemblage(self) -> None:
        with ReponseAuxBoites(SUPPRIMER_L_ASSEMBLAGE) as boites:
            taper(enfant(formulaire(PANNEAU_PIECE), "angleYEdit"), "90")
        self.assertEqual(len(boites.vues), 1, boites.vues)
        self.assertEqual(assemblages(self.doc), [])
        self.assertAlmostEqual(etendues(self.traverse)[2], self.traverse.Length.Value)
        cliquer(bouton_ok())
        self.assertFalse(panneau_ouvert())
        self.assertEqual(len(self.doc.UndoNames), 1, self.doc.UndoNames)
        controler_le_document(self, self.doc)

    def test_3_annuler_rend_l_assemblage(self) -> None:
        lancer("Std_Undo")
        self.doc.recompute()
        (assemblage,) = assemblages(self.doc)
        self.assertTrue(assemblage.isValid(), assemblage.getStatusString())
        controler_le_document(self, self.doc)
        self.assertEqual(erreurs_python(vue_rapport()), [])


class PieceDUnEnsemble(ScenarioDeRotation):
    """Une traverse rangée dans un ensemble ne tourne pas depuis son panneau : boutons et champs
    grisés, avec l'explication en infobulle ; retirée de l'ensemble, elle tourne."""

    pieces: ClassVar[dict[str, Any]]

    @classmethod
    def setUpClass(cls) -> None:
        cls.doc = preparer("ScenarioRotationEnsemble")
        cls.addClassCleanup(fermer, cls.doc)
        cls.pieces = cadre(cls.doc)
        selectionner(*cls.pieces.values())
        lancer(ENSEMBLE)
        selectionner()
        cls.doc.clearUndos()
        vider_la_vue_rapport()

    def test_1_rotation_grisee_et_expliquee(self) -> None:
        traverse = self.pieces["T1"]
        avant = etendues(traverse)
        double_cliquer(traverse)
        form = formulaire(PANNEAU_PIECE)
        for nom in ("rotateXButton", "rotateYButton", "rotateZButton", "angleZEdit"):
            with self.subTest(widget=nom):
                widget = enfant(form, nom)
                self.assertTrue(widget.isVisible())
                self.assertFalse(widget.isEnabled(), "actif pour une pièce d'un ensemble")
        self.assertIn("ensemble", enfant(form, "rotateZButton").toolTip())
        cliquer(bouton_annuler())
        self.assertFalse(panneau_ouvert())
        self.assertEqual(etendues(traverse), avant)
        self.assertEqual(self.doc.UndoNames, [])

    def test_2_retiree_de_l_ensemble_elle_tourne(self) -> None:
        traverse = self.pieces["T1"]
        avant, centre = etendues(traverse), boite_globale(traverse).Center
        selectionner(traverse)
        lancer(RETIRER)
        selectionner()
        double_cliquer(traverse)
        cliquer(enfant(formulaire(PANNEAU_PIECE), "rotateZButton"))
        self.assertEqual(etendues(traverse), (avant[1], avant[0], avant[2]))
        self.assertLess(boite_globale(traverse).Center.distanceToPoint(centre), TOLERANCE_MM)
        cliquer(bouton_ok())
        self.assertFalse(panneau_ouvert())
        self.assertEqual(len(self.doc.UndoNames), 2, self.doc.UndoNames)
        controler_le_document(self, self.doc)
        self.assertEqual(erreurs_python(vue_rapport()), [])
