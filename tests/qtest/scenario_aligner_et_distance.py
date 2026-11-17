# SPDX-License-Identifier: LGPL-2.1-or-later
"""Scénario QTest S14 : « Aligner deux faces », sa grille « Parallèle et aligner sur », puis une
distance gardée.

Deux pièces libres, la seconde tournée de 30° : commande « Aligner deux faces » et son panneau
(chaque mode, centre sur X et Y, « // X », ligne Z grisée, décalage, « Inverser »).
Puis deux pièces d'un ensemble : « Définir une distance » gardée, qui doit tenir quand
l'ensemble s'élargit, se régler par son propre panneau
et disparaître quand on décoche « Garder cette distance ».

Non simulés : les clics sur les faces dans la vue 3D (``Gui.Selection``).
"""

from __future__ import annotations

import unittest
from typing import Any, ClassVar

import FreeCAD as App

from tests.qtest.aides import (
    Etapes,
    activer_faulthandler,
    bouton_ok,
    choisir,
    cliquer,
    enfant,
    fermer,
    formulaire,
    lancer,
    panneau_ouvert,
    preparer,
    selectionner,
    selectionner_des_faces,
    taper,
    vider_la_vue_rapport,
    vue_rapport,
)
from tests.qtest.angle_a_queues import PANNEAU_PIECE, controler_le_document, double_cliquer
from tests.qtest.pieces import (
    AXE_Z,
    boite_globale,
    deplacer,
    du_type,
    erreurs_python,
    face_vers,
    piece,
)

ALIGNER = "Menuiserie_AlignFaces"
DISTANCE = "Menuiserie_SetDistance"
ENSEMBLE = "Menuiserie_Furniture"
RELIER = "Menuiserie_FurnitureRebind"
PANNEAU_ALIGNER = "AlignTaskPanel"
PANNEAU_DISTANCE = "DistanceTaskPanel"
PANNEAU_DISTANCE_GARDEE = "KeptDistancePanel"
PANNEAU_ENSEMBLE = "FurnitureTaskPanel"
TYPE_DISTANCE = "Menuiserie::Distance"
TYPE_ENSEMBLE = "Menuiserie::Furniture"
EPAISSEUR = 22.0
DESSUS, DESSOUS = (0.0, 0.0, 1.0), (0.0, 0.0, -1.0)
DROITE, GAUCHE = (1.0, 0.0, 0.0), (-1.0, 0.0, 0.0)
MODES = 4  # automatique, au ras, face contre face, d'équerre
TOLERANCE_MM = 1e-6


def setUpModule() -> None:
    unittest.addModuleCleanup(activer_faulthandler())


def distances(doc: Any) -> list[Any]:
    return du_type(doc, TYPE_DISTANCE)


class AlignerEtCentrer(Etapes):
    """Étapes jouées dans l'ordre : le panneau reste ouvert de l'étape 1 à l'étape 5."""

    doc: ClassVar[Any]
    fixe: ClassVar[Any]
    mobile: ClassVar[Any]
    depart: ClassVar[App.Placement]

    @classmethod
    def setUpClass(cls) -> None:
        cls.doc = preparer("ScenarioAligner")
        cls.addClassCleanup(fermer, cls.doc)
        cls.fixe = piece(cls.doc, (500.0, 200.0, EPAISSEUR), repere="A")
        cls.mobile = piece(
            cls.doc, (300.0, 100.0, EPAISSEUR), (700.0, 300.0, 50.0), AXE_Z, 30.0, "B"
        )
        cls.doc.recompute()
        cls.depart = cls.mobile.Placement
        cls.doc.clearUndos()
        vider_la_vue_rapport()

    def form(self) -> Any:
        return formulaire(PANNEAU_ALIGNER)

    def test_1_face_contre_face(self) -> None:
        """La face choisie en second est celle de la pièce déplacée : le dessous de B vient sur
        le dessus de A, B garde son angle."""
        selectionner_des_faces(
            (self.fixe, face_vers(self.fixe, DESSUS)),
            (self.mobile, face_vers(self.mobile, DESSOUS)),
        )
        lancer(ALIGNER)
        self.assertIn("B", enfant(self.form(), "movedLabel").text())
        self.assertAlmostEqual(boite_globale(self.mobile).ZMin, EPAISSEUR, delta=TOLERANCE_MM)
        self.assertAlmostEqual(self.mobile.Placement.Rotation.toEuler()[0], 30.0, places=6)
        self.assertTrue(self.fixe.Placement.isSame(App.Placement(), TOLERANCE_MM), "A a bougé")

    def test_2_chaque_mode(self) -> None:
        """Chaque ligne de la liste « mode » déplace la pièce sans erreur ; « au ras » met les
        deux faces dans le même plan, du même côté."""
        liste = enfant(self.form(), "modeCombo")
        self.assertEqual(liste.count(), MODES)
        vus = set()
        for rang in range(MODES):
            with self.subTest(mode=liste.itemText(rang)):
                choisir(liste, rang)
                self.assertEqual(enfant(self.form(), "errorLabel").text(), "")
                englobante = boite_globale(self.mobile)
                vus.add((round(englobante.ZMin, 3), round(englobante.ZMax, 3)))
        self.assertIn((0.0, EPAISSEUR), vus, "aucun mode ne met les faces au ras")
        self.assertGreaterEqual(len(vus), 3, vus)
        choisir(liste, 0)
        self.assertAlmostEqual(boite_globale(self.mobile).ZMin, EPAISSEUR, delta=TOLERANCE_MM)

    def test_3_centre_sur_x_y_puis_parallele(self) -> None:
        """Centre sur X puis Y : les centres se confondent, B garde son angle (aligner ne fait
        plus tourner). « // X » couche son grand côté le long de X. La ligne Z, normale des
        faces, est grisée avec une infobulle (doute D9, ADR 0066)."""
        cible = boite_globale(self.fixe).Center
        cliquer(enfant(self.form(), "centerXButton"))
        centre = boite_globale(self.mobile).Center
        self.assertAlmostEqual(centre.x, cible.x, delta=TOLERANCE_MM)
        self.assertNotAlmostEqual(centre.y, cible.y, delta=1.0)
        cliquer(enfant(self.form(), "centerYButton"))
        centre = boite_globale(self.mobile).Center
        self.assertAlmostEqual(centre.x, cible.x, delta=TOLERANCE_MM)
        self.assertAlmostEqual(centre.y, cible.y, delta=TOLERANCE_MM)
        self.assertAlmostEqual(boite_globale(self.mobile).ZMin, EPAISSEUR, delta=TOLERANCE_MM)
        self.assertAlmostEqual(self.mobile.Placement.Rotation.toEuler()[0], 30.0, places=6)
        cliquer(enfant(self.form(), "parallelXButton"))
        self.assertEqual(enfant(self.form(), "errorLabel").text(), "")
        englobante = boite_globale(self.mobile)
        self.assertAlmostEqual(englobante.XLength, 300.0, delta=TOLERANCE_MM)
        self.assertAlmostEqual(englobante.YLength, 100.0, delta=TOLERANCE_MM)
        self.assertTrue(englobante.Center.isEqual(centre, TOLERANCE_MM))
        for nom in ("parallelZButton", "startZButton", "centerZButton", "endZButton"):
            self.assertFalse(enfant(self.form(), nom).isEnabled(), nom)
        self.assertIn("normale", enfant(self.form(), "layoutAxisZ").toolTip())

    def test_4_decalage(self) -> None:
        avant = boite_globale(self.mobile).Center
        taper(enfant(self.form(), "offsetX"), "10 mm")
        apres = boite_globale(self.mobile).Center
        self.assertAlmostEqual(apres.distanceToPoint(avant), 10.0, delta=TOLERANCE_MM)
        self.assertAlmostEqual(apres.z, avant.z, delta=TOLERANCE_MM)

    def test_5_inverser_deux_fois(self) -> None:
        """« Inverser » : c'est A qui vient sur B, revenue à sa place ; un second clic rend
        l'état d'avant."""
        avant = self.mobile.Placement
        cliquer(enfant(self.form(), "swapButton"))
        self.assertIn("A", enfant(self.form(), "movedLabel").text())
        self.assertTrue(self.mobile.Placement.isSame(self.depart, TOLERANCE_MM), "B pas revenue")
        self.assertFalse(self.fixe.Placement.isSame(App.Placement(), TOLERANCE_MM), "A immobile")
        cliquer(enfant(self.form(), "swapButton"))
        self.assertTrue(self.fixe.Placement.isSame(App.Placement(), TOLERANCE_MM))
        self.assertTrue(self.mobile.Placement.isSame(avant, TOLERANCE_MM))

    def test_6_valider_puis_annuler(self) -> None:
        cliquer(bouton_ok())
        self.assertFalse(panneau_ouvert())
        self.assertEqual(len(self.doc.UndoNames), 1, self.doc.UndoNames)
        controler_le_document(self, self.doc)
        lancer("Std_Undo")
        self.doc.recompute()
        self.assertTrue(self.mobile.Placement.isSame(self.depart, TOLERANCE_MM))
        lancer("Std_Redo")
        self.doc.recompute()
        self.assertFalse(self.mobile.Placement.isSame(self.depart, TOLERANCE_MM))
        controler_le_document(self, self.doc)
        self.assertEqual(erreurs_python(vue_rapport()), [])


class DistanceGardee(Etapes):
    """Étapes jouées dans l'ordre sur le même document."""

    doc: ClassVar[Any]
    reference: ClassVar[Any]
    mobile: ClassVar[Any]
    ensemble: ClassVar[Any]

    @classmethod
    def setUpClass(cls) -> None:
        cls.doc = preparer("ScenarioDistance")
        cls.addClassCleanup(fermer, cls.doc)
        cls.reference = piece(cls.doc, (500.0, 200.0, EPAISSEUR), repere="A")
        cls.mobile = piece(cls.doc, (300.0, 100.0, EPAISSEUR), (800.0, 0.0, 0.0), repere="C")
        cls.doc.recompute()
        selectionner(cls.reference, cls.mobile)
        lancer(ENSEMBLE)
        (cls.ensemble,) = du_type(cls.doc, TYPE_ENSEMBLE)
        cls.doc.clearUndos()
        vider_la_vue_rapport()

    def ecart(self) -> float:
        """Vide entre le bout droit de A et le bout gauche de C."""
        return float(boite_globale(self.mobile).XMin - boite_globale(self.reference).XMax)

    def test_1_definir_une_distance_gardee(self) -> None:
        selectionner_des_faces(
            (self.reference, face_vers(self.reference, DROITE)),
            (self.mobile, face_vers(self.mobile, GAUCHE)),
        )
        lancer(DISTANCE)
        form = formulaire(PANNEAU_DISTANCE)
        self.assertAlmostEqual(enfant(form, "distanceEdit").property("rawValue"), 300.0)
        garder = enfant(form, "keepCheck")
        self.assertTrue(garder.isEnabled() and garder.isChecked(), garder.toolTip())
        taper(enfant(form, "distanceEdit"), "100 mm")
        self.assertEqual(enfant(form, "errorLabel").text(), "")
        self.assertAlmostEqual(self.ecart(), 100.0, delta=TOLERANCE_MM)
        self.assertAlmostEqual(boite_globale(self.reference).XMin, 0.0, delta=TOLERANCE_MM)
        cliquer(bouton_ok())
        self.assertFalse(panneau_ouvert())
        (distance,) = distances(self.doc)
        self.assertAlmostEqual(distance.Value.Value, 100.0)
        self.assertEqual(len(self.doc.UndoNames), 1, self.doc.UndoNames)
        controler_le_document(self, self.doc)

    def test_1b_la_distance_tient_quand_la_reference_se_deplace(self) -> None:
        """A retouchée à la main de 50 mm (placement écrit, comme un glissement), puis « Relier
        les pièces » : C a suivi, l'écart est de nouveau de 100 mm. Deux Ctrl+Z ramènent les
        deux pièces."""
        depart = boite_globale(self.mobile).XMin
        place = App.Placement(self.reference.Placement)
        place.Base = place.Base + App.Vector(50.0, 0.0, 0.0)
        deplacer(self.doc, self.reference, place)
        selectionner(self.ensemble)
        lancer(RELIER)
        self.assertAlmostEqual(boite_globale(self.reference).XMin, 50.0, delta=TOLERANCE_MM)
        self.assertAlmostEqual(self.ecart(), 100.0, delta=TOLERANCE_MM)
        (distance,) = distances(self.doc)
        self.assertAlmostEqual(distance.Value.Value, 100.0)
        self.assertEqual(len(self.doc.UndoNames), 3, self.doc.UndoNames)
        controler_le_document(self, self.doc)
        lancer("Std_Undo")
        lancer("Std_Undo")
        self.doc.recompute()
        self.assertAlmostEqual(boite_globale(self.reference).XMin, 0.0, delta=TOLERANCE_MM)
        self.assertAlmostEqual(boite_globale(self.mobile).XMin, depart, delta=TOLERANCE_MM)
        self.assertAlmostEqual(self.ecart(), 100.0, delta=TOLERANCE_MM)
        controler_le_document(self, self.doc)

    def test_1c_panneau_d_une_piece_liee_valide_sans_rien_changer(self) -> None:
        """La longueur de A dépend de la distance gardée : champ en lecture seule ; « OK » sans
        rien changer n'ajoute aucune entrée d'annulation."""
        annulations = list(self.doc.UndoNames)
        selectionner()
        double_cliquer(self.reference)
        self.assertTrue(enfant(formulaire(PANNEAU_PIECE), "lengthEdit").isReadOnly())
        cliquer(bouton_ok())
        self.assertFalse(panneau_ouvert())
        self.assertEqual(self.doc.UndoNames, annulations)
        controler_le_document(self, self.doc)

    def test_2_la_distance_tient_quand_l_ensemble_s_elargit(self) -> None:
        longueur = self.reference.Length.Value
        selectionner()
        double_cliquer(self.ensemble)
        form = formulaire(PANNEAU_ENSEMBLE)
        taper(enfant(form, "Width"), f"{self.ensemble.Width.Value + 100.0:g} mm")
        self.assertEqual(enfant(form, "refusalLabel").text(), "")
        cliquer(bouton_ok())
        self.assertFalse(panneau_ouvert())
        self.assertGreater(self.reference.Length.Value, longueur + 1.0, "A n'a pas suivi")
        self.assertAlmostEqual(self.ecart(), 100.0, delta=TOLERANCE_MM)
        controler_le_document(self, self.doc)

    def test_3_regler_la_distance_par_son_panneau(self) -> None:
        (distance,) = distances(self.doc)
        double_cliquer(distance)
        form = formulaire(PANNEAU_DISTANCE_GARDEE)
        taper(enfant(form, "distanceEdit"), "150 mm")
        self.assertEqual(enfant(form, "errorLabel").text(), "")
        self.assertAlmostEqual(self.ecart(), 150.0, delta=TOLERANCE_MM)
        cliquer(bouton_ok())
        self.assertFalse(panneau_ouvert())
        self.assertAlmostEqual(distance.Value.Value, 150.0)
        controler_le_document(self, self.doc)

    def test_4_ne_plus_garder(self) -> None:
        """Case décochée puis « OK » : la Distance disparaît, les pièces restent en place ;
        Ctrl+Z la rend."""
        (distance,) = distances(self.doc)
        annulations = len(self.doc.UndoNames)
        double_cliquer(distance)
        garder = enfant(formulaire(PANNEAU_DISTANCE_GARDEE), "keepCheck")
        cliquer(garder)
        self.assertFalse(garder.isChecked())
        cliquer(bouton_ok())
        self.assertFalse(panneau_ouvert())
        self.assertEqual(distances(self.doc), [])
        self.assertAlmostEqual(self.ecart(), 150.0, delta=TOLERANCE_MM)
        self.assertEqual(len(self.doc.UndoNames), annulations + 1, self.doc.UndoNames)
        controler_le_document(self, self.doc)
        lancer("Std_Undo")
        self.doc.recompute()
        self.assertEqual(len(distances(self.doc)), 1)
        controler_le_document(self, self.doc)
        lancer("Std_Redo")
        self.doc.recompute()
        self.assertEqual(distances(self.doc), [])
        self.assertAlmostEqual(self.ecart(), 150.0, delta=TOLERANCE_MM)
        controler_le_document(self, self.doc)
        self.assertEqual(erreurs_python(vue_rapport()), [])
