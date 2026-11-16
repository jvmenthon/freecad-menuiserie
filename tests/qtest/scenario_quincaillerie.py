# SPDX-License-Identifier: LGPL-2.1-or-later
"""Scénario QTest S16 : la quincaillerie d'un caisson.

Commande « Caisson » et son panneau, pieds sous le dessous, perçage au pas de 32 mm des deux
côtés (nombre de rangs retapé, jusqu'au refus), puis la hauteur du caisson changée par le
panneau de l'ensemble : les perçages suivent et restent dans la pièce ; quand le côté devient
trop petit, le perçage est signalé en erreur avec son explication.
"""

from __future__ import annotations

import unittest
from typing import Any, ClassVar

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
    traiter_les_evenements,
    vider_la_vue_rapport,
    vue_rapport,
)
from tests.qtest.angle_a_queues import PANNEAU_ASSEMBLAGE, controler_le_document, double_cliquer
from tests.qtest.pieces import commande_active, du_type, erreurs_python, retablir_tout

CAISSON = "Menuiserie_Carcass"
PIEDS = "Menuiserie_Foot"
PAS_DE_32 = "Menuiserie_ShelfPins"
COULISSES = "Menuiserie_DrawerSlide"
PANNEAU_CAISSON = "CarcassTaskPanel"
PANNEAU_ENSEMBLE = "FurnitureTaskPanel"
TYPE_PIECE = "Menuiserie::WoodPart"
TYPE_ENSEMBLE = "Menuiserie::Furniture"
TYPE_PIEDS = "Menuiserie::Foot"
TYPE_PAS_DE_32 = "Menuiserie::ShelfPins"
HAUTEUR, HAUT, BAS, TROP_BAS = 720.0, 900.0, 300.0, 150.0
TOLERANCE_MM = 1e-6


def setUpModule() -> None:
    unittest.addModuleCleanup(activer_faulthandler())


class Quincaillerie(Etapes):
    """Étapes jouées dans l'ordre sur le même document."""

    doc: ClassVar[Any]
    pieces: ClassVar[dict[str, Any]]

    @classmethod
    def setUpClass(cls) -> None:
        cls.doc = preparer("ScenarioQuincaillerie")
        cls.addClassCleanup(fermer, cls.doc)
        vider_la_vue_rapport()

    def enleve(self, nom: str) -> float:
        """Volume enlevé à la pièce ``nom`` par ses usinages (mm³)."""
        brute = self.pieces[nom]
        return float(brute.Shape.Volume - usinee_de(brute).Shape.Volume)

    def controler_les_percages(self, *noms: str) -> None:
        """Pièces percées en un seul solide, sans rien qui dépasse de la pièce brute."""
        for nom in noms:
            with self.subTest(piece=nom):
                brute, usinee = self.pieces[nom].Shape, usinee_de(self.pieces[nom]).Shape
                self.assertEqual(len(usinee.Solids), 1)
                self.assertTrue(usinee.isValid())
                self.assertGreater(self.enleve(nom), 0.0, "aucun perçage")
                for cote in ("XMin", "YMin", "ZMin", "XMax", "YMax", "ZMax"):
                    self.assertAlmostEqual(
                        getattr(usinee.BoundBox, cote),
                        getattr(brute.BoundBox, cote),
                        delta=TOLERANCE_MM,
                        msg=f"perçage hors de la pièce ({cote})",
                    )

    def changer_la_hauteur(self, hauteur: float) -> Any:
        """Double-clic sur l'ensemble et hauteur retapée ; renvoie le formulaire, panneau
        laissé ouvert."""
        selectionner()
        (ensemble,) = du_type(self.doc, TYPE_ENSEMBLE)
        double_cliquer(ensemble)
        form = formulaire(PANNEAU_ENSEMBLE)
        taper(enfant(form, "Height"), f"{hauteur:g} mm")
        return form

    def fin_de_geste(self, hauteur: float) -> None:
        """Hauteur de l'ensemble écrite comme par une poignée de la vue 3D, puis panneau relu
        par la séance de glissement."""
        from freecad.menuiserie.gui.drag import events

        (ensemble,) = du_type(self.doc, TYPE_ENSEMBLE)
        ensemble.Height = hauteur
        self.doc.recompute()
        session = events.current_session()
        assert session is not None and session.panel is not None, "panneau hors séance"
        session.panel.refresh()
        traiter_les_evenements()

    def test_1_caisson(self) -> None:
        selectionner()
        lancer(CAISSON)
        form = formulaire(PANNEAU_CAISSON)
        taper(enfant(form, "height"), f"{HAUTEUR:g} mm")
        self.assertEqual(enfant(form, "errorLabel").text(), "")
        cliquer(bouton_ok())
        self.assertFalse(panneau_ouvert())
        type(self).pieces = {brute.Label: brute for brute in du_type(self.doc, TYPE_PIECE)}
        self.assertLessEqual({"Côté gauche", "Côté droit", "Dessous", "Dessus"}, set(self.pieces))
        (ensemble,) = du_type(self.doc, TYPE_ENSEMBLE)
        self.assertAlmostEqual(ensemble.Height.Value, HAUTEUR)
        self.assertEqual(len(self.doc.UndoNames), 1, self.doc.UndoNames)
        controler_le_document(self, self.doc)

    def test_2_pieds_sous_le_dessous(self) -> None:
        selectionner(self.pieces["Dessous"])
        self.assertFalse(commande_active(COULISSES), "coulisses actives avec une seule pièce")
        lancer(PIEDS)
        self.assertEqual(enfant(formulaire(PANNEAU_ASSEMBLAGE), "errorLabel").text(), "")
        cliquer(bouton_ok())
        self.assertFalse(panneau_ouvert())
        (pieds,) = du_type(self.doc, TYPE_PIEDS)
        self.assertTrue(pieds.isValid(), pieds.getStatusString())
        self.assertEqual(pieds.Label, "Pieds : Dessous")  # la pièce n'est nommée qu'une fois
        self.controler_les_percages("Dessous")
        self.assertEqual(len(self.doc.UndoNames), 2, self.doc.UndoNames)

    def test_3_pas_de_32_et_nombre_de_rangs(self) -> None:
        """Rangs en automatique, puis retapés : un nombre qui ne tient pas dans le côté est
        refusé avec une explication et « OK » se grise ; un nombre qui tient est accepté."""
        selectionner(self.pieces["Côté gauche"])
        lancer(PAS_DE_32)
        form = formulaire(PANNEAU_ASSEMBLAGE)
        erreur = enfant(form, "errorLabel")
        self.assertEqual(erreur.text(), "")
        automatique = enfant(form, "Rows").value()
        self.assertGreater(automatique, 1)
        cliquer(enfant(form, "RowsAuto"))
        taper(enfant(form, "Rows"), str(automatique + 10))
        self.assertEqual(enfant(form, "Rows").value(), automatique + 10)
        self.assertIn("trop petit", erreur.text())
        self.assertFalse(bouton_ok().isEnabled(), "OK actif malgré le refus")
        # Plafond : le champ ne laisse pas taper au-delà de son maximum (les chiffres en trop
        # sont ignorés), et le maximum lui-même est refusé sur ce côté.
        rangs = enfant(form, "Rows")
        taper(rangs, "99999")
        self.assertLessEqual(rangs.value(), rangs.maximum())
        self.assertLess(rangs.maximum(), 1000, "aucun plafond au nombre de rangs")
        taper(rangs, str(rangs.maximum()))
        self.assertEqual(rangs.value(), rangs.maximum())
        self.assertIn("trop petit", erreur.text())
        self.assertFalse(bouton_ok().isEnabled(), "OK actif malgré le refus")
        taper(enfant(form, "Rows"), str(automatique - 2))
        self.assertEqual(erreur.text(), "")
        self.assertTrue(bouton_ok().isEnabled())
        cliquer(enfant(form, "RowsAuto"))  # retour à l'automatique pour la suite
        self.assertEqual(enfant(form, "Rows").value(), automatique)
        cliquer(bouton_ok())
        self.assertFalse(panneau_ouvert())
        (percage,) = du_type(self.doc, TYPE_PAS_DE_32)
        self.assertTrue(percage.isValid(), percage.getStatusString())
        self.controler_les_percages("Côté gauche", "Côté droit")
        self.assertAlmostEqual(self.enleve("Côté gauche"), self.enleve("Côté droit"), delta=1.0)
        self.assertEqual(len(self.doc.UndoNames), 3, self.doc.UndoNames)
        controler_le_document(self, self.doc)

    def test_4_les_percages_suivent_la_hauteur(self) -> None:
        enleve = {HAUTEUR: self.enleve("Côté gauche")}
        for hauteur in (HAUT, BAS):
            with self.subTest(hauteur=hauteur):
                form = self.changer_la_hauteur(hauteur)
                self.assertEqual(enfant(form, "refusalLabel").text(), "")
                cliquer(bouton_ok())
                self.assertFalse(panneau_ouvert())
                self.assertAlmostEqual(self.pieces["Côté gauche"].Length.Value, hauteur)
                for quincaillerie in (TYPE_PIEDS, TYPE_PAS_DE_32):
                    (objet,) = du_type(self.doc, quincaillerie)
                    self.assertTrue(objet.isValid(), objet.getStatusString())
                self.controler_les_percages("Côté gauche", "Côté droit", "Dessous")
                enleve[hauteur] = self.enleve("Côté gauche")
                controler_le_document(self, self.doc)
        # Plus le côté est haut, plus il a de rangs de trous.
        self.assertGreater(enleve[HAUT], enleve[HAUTEUR] + 1.0)
        self.assertLess(enleve[BAS], enleve[HAUTEUR] - 1.0)

    def test_5_cote_trop_petit_pour_le_percage(self) -> None:
        """Le perçage devenu impossible est refusé dans le panneau, « OK » grisé, avec son
        explication (aussi sur l'objet et dans la vue rapport) ; une hauteur qui convient lève
        le refus ; « Annuler » rend le caisson d'avant, perçage valide."""
        form = self.changer_la_hauteur(TROP_BAS)
        (percage,) = du_type(self.doc, TYPE_PAS_DE_32)
        self.assertIn("Invalid", percage.State)
        self.assertIn("trop petit pour un rang", percage.getStatusString())
        self.assertIn("trop petit", vue_rapport())
        refus = enfant(form, "refusalLabel").text()
        self.assertIn("Perçage LR32", refus)
        self.assertIn("trop petit pour un rang", refus)
        self.assertFalse(bouton_ok().isEnabled(), "OK actif malgré le perçage impossible")
        taper(enfant(form, "Height"), f"{BAS:g} mm")
        self.assertEqual(enfant(form, "refusalLabel").text(), "")
        self.assertTrue(bouton_ok().isEnabled())
        self.assertTrue(percage.isValid(), percage.getStatusString())
        taper(enfant(form, "Height"), f"{TROP_BAS:g} mm")
        self.assertFalse(bouton_ok().isEnabled())
        # Fin d'un geste à la souris sur l'ensemble (poignée non simulée : la cote est écrite
        # dans la transaction du panneau, qui relit ses champs comme au relâchement).
        for hauteur, refuse in ((BAS, False), (TROP_BAS, True)):
            with self.subTest(geste=hauteur):
                self.fin_de_geste(hauteur)
                self.assertAlmostEqual(enfant(form, "Height").property("rawValue"), hauteur)
                self.assertEqual(bool(enfant(form, "refusalLabel").text()), refuse)
                self.assertEqual(bouton_ok().isEnabled(), not refuse)
        cliquer(bouton_annuler())
        self.assertFalse(panneau_ouvert())
        self.doc.recompute()
        self.assertTrue(percage.isValid(), percage.getStatusString())
        self.assertAlmostEqual(self.pieces["Côté gauche"].Length.Value, BAS)
        self.controler_les_percages("Côté gauche", "Côté droit")
        controler_le_document(self, self.doc)

    def test_6_tout_annuler(self) -> None:
        self.assertEqual(erreurs_python(vue_rapport()), [])
        noms = [objet.Name for objet in self.doc.Objects]
        for _ in self.doc.UndoNames:
            lancer("Std_Undo")
        self.assertEqual(self.doc.Objects, [])
        retablir_tout(self.doc)
        self.assertEqual([objet.Name for objet in self.doc.Objects], noms)
        for quincaillerie in (TYPE_PIEDS, TYPE_PAS_DE_32):
            (objet,) = du_type(self.doc, quincaillerie)
            self.assertTrue(objet.isValid(), objet.getStatusString())
        controler_le_document(self, self.doc)
