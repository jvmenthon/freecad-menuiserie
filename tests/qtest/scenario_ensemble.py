# SPDX-License-Identifier: LGPL-2.1-or-later
"""Scénario QTest S11 : un ensemble, de sa création à sa rotation.

Un cadre de quatre pièces regroupé par la commande « Ensemble », une cinquième pièce ajoutée,
puis le panneau de l'ensemble : largeur retapée (les pièces suivent), une pièce mise en « cotes
fixes » qui bloque la cote suivante, « Déverrouiller et appliquer », rotation de 90° autour de
Z, « OK » et Ctrl+Z. Enfin un tenon-mortaise demandé entre une pièce d'un ensemble et une pièce
d'un second ensemble (issue #209, ouverte) : refusé avec une explication, rien d'écrit.
"""

from __future__ import annotations

import unittest
from typing import Any, ClassVar

from PySide import QtCore, QtGui

from tests.qtest.aides import (
    Etapes,
    activer_faulthandler,
    bouton_ok,
    cliquer,
    enfant,
    fermer,
    formulaire,
    lancer,
    panneau_ouvert,
    preparer,
    refus_signale,
    selectionner,
    taper,
    traiter_les_evenements,
    vider_la_vue_rapport,
    vue_rapport,
)
from tests.qtest.angle_a_queues import controler_le_document, double_cliquer
from tests.qtest.pieces import (
    AXE_Z,
    SECTION,
    assemblages,
    boite_globale,
    cadre,
    du_type,
    erreurs_python,
    piece,
)
from tests.qtest.qttest import QTest

ENSEMBLE = "Menuiserie_Furniture"
AJOUTER = "Menuiserie_FurnitureAdd"
TENON_MORTAISE = "Menuiserie_MortiseTenon"
PANNEAU_ENSEMBLE = "FurnitureTaskPanel"
TYPE_ENSEMBLE = "Menuiserie::Furniture"
LARGEUR, PROFONDEUR, HAUTEUR = 600.0, 400.0, 22.0
ELARGI, ENCORE_ELARGI = 800.0, 900.0
EPAISSI = 30.0
TOLERANCE_MM = 1e-6


def setUpModule() -> None:
    unittest.addModuleCleanup(activer_faulthandler())


class Ensemble(Etapes):
    """Étapes jouées dans l'ordre sur le même document."""

    doc: ClassVar[Any]
    pieces: ClassVar[dict[str, Any]]
    ensemble: ClassVar[Any]

    @classmethod
    def setUpClass(cls) -> None:
        cls.doc = preparer("ScenarioEnsemble")
        cls.addClassCleanup(fermer, cls.doc)
        cls.pieces = cadre(cls.doc)
        cls.doc.clearUndos()
        vider_la_vue_rapport()

    def cotes(self) -> tuple[float, float, float]:
        return tuple(getattr(self.ensemble, nom).Value for nom in ("Width", "Depth", "Height"))

    def form(self) -> Any:
        return formulaire(PANNEAU_ENSEMBLE)

    def test_1_creer_l_ensemble(self) -> None:
        selectionner(*self.pieces.values())
        lancer(ENSEMBLE)
        (ensemble,) = du_type(self.doc, TYPE_ENSEMBLE)
        type(self).ensemble = ensemble
        self.assertEqual(self.cotes(), (LARGEUR, PROFONDEUR, HAUTEUR))
        for membre in self.pieces.values():
            self.assertEqual(membre.getParentGeoFeatureGroup().TypeId, "App::Part", membre.Label)
        self.assertEqual(len(self.doc.UndoNames), 1, self.doc.UndoNames)
        controler_le_document(self, self.doc)

    def test_2_ajouter_une_piece(self) -> None:
        milieu = piece(self.doc, (280.0, *SECTION), (330.0, 60.0, 0.0), AXE_Z, 90.0, "T3")
        self.doc.recompute()
        self.doc.clearUndos()
        selectionner(milieu, self.ensemble)
        lancer(AJOUTER)
        type(self).pieces = {**self.pieces, "T3": milieu}
        conteneurs = {membre.getParentGeoFeatureGroup() for membre in self.pieces.values()}
        self.assertEqual(len(conteneurs), 1, "la pièce ajoutée n'est pas dans le Std Part")
        self.assertEqual(self.cotes(), (LARGEUR, PROFONDEUR, HAUTEUR))
        self.assertEqual(len(self.doc.UndoNames), 1, self.doc.UndoNames)
        selectionner()

    def test_2b_une_piece_hors_de_la_boite_l_agrandit(self) -> None:
        """Pièce posée 100 mm derrière l'ensemble puis ajoutée : la boîte grandit jusqu'à
        l'envelopper (ADR 0049), les membres ne bougent pas ; Ctrl+Z rend la boîte d'avant."""
        dehors = piece(self.doc, (600.0, *SECTION), (0.0, PROFONDEUR + 100.0, 0.0), repere="H")
        self.doc.recompute()
        self.doc.clearUndos()
        places = {nom: membre.Placement for nom, membre in self.pieces.items()}
        selectionner(dehors, self.ensemble)
        lancer(AJOUTER)
        agrandie = PROFONDEUR + 100.0 + SECTION[0]
        self.assertEqual(self.cotes(), (LARGEUR, agrandie, HAUTEUR))
        self.assertIs(
            dehors.getParentGeoFeatureGroup(), self.pieces["M1"].getParentGeoFeatureGroup()
        )
        for nom, membre in self.pieces.items():
            self.assertTrue(membre.Placement.isSame(places[nom], TOLERANCE_MM), f"{nom} a bougé")
        self.assertEqual(len(self.doc.UndoNames), 1, self.doc.UndoNames)
        controler_le_document(self, self.doc)
        lancer("Std_Undo")
        self.doc.recompute()
        self.assertEqual(self.cotes(), (LARGEUR, PROFONDEUR, HAUTEUR))
        self.assertIsNone(dehors.getParentGeoFeatureGroup())
        controler_le_document(self, self.doc)
        selectionner()

    def test_3_elargir_au_panneau(self) -> None:
        double_cliquer(self.ensemble)
        liste = self.form().findChild(QtGui.QTreeWidget, "membersTree")
        self.assertEqual(liste.topLevelItemCount(), len(self.pieces))
        taper(enfant(self.form(), "Width"), f"{ELARGI:g} mm")
        self.assertEqual(enfant(self.form(), "refusalLabel").text(), "")
        self.assertTrue(bouton_ok().isEnabled())
        self.assertAlmostEqual(self.ensemble.Width.Value, ELARGI)
        for nom in ("M1", "M2"):
            self.assertAlmostEqual(self.pieces[nom].Length.Value, ELARGI, msg=nom)
        boite = boite_globale(*self.pieces.values())
        self.assertAlmostEqual(boite.XLength, ELARGI, delta=TOLERANCE_MM)
        self.assertAlmostEqual(boite.YLength, PROFONDEUR, delta=TOLERANCE_MM)

    def test_3b_epaisseur_refusee(self) -> None:
        """Les pièces à plat remplissent la hauteur de leurs épaisseurs, qu'un ensemble ne
        change pas : la hauteur retapée est refusée avec une explication, rien ne bouge, et la
        cote d'origine retapée lève le refus."""
        champ = enfant(self.form(), "Height")
        taper(champ, f"{EPAISSI:g} mm")
        self.assertIn("hauteur", enfant(self.form(), "refusalLabel").text())
        self.assertFalse(bouton_ok().isEnabled(), "OK actif malgré le refus")
        for nom, membre in self.pieces.items():
            self.assertAlmostEqual(membre.Thickness.Value, HAUTEUR, msg=nom)
        boite = boite_globale(*self.pieces.values())
        self.assertAlmostEqual(boite.ZLength, HAUTEUR, delta=TOLERANCE_MM)
        taper(champ, f"{HAUTEUR:g} mm")
        self.assertEqual(enfant(self.form(), "refusalLabel").text(), "")
        self.assertTrue(bouton_ok().isEnabled())
        self.assertAlmostEqual(self.ensemble.Height.Value, HAUTEUR)

    def test_4_cotes_fixes_puis_deverrouiller(self) -> None:
        """« Cotes fixes » sur M1 : la largeur suivante est refusée avec une explication et rien
        ne bouge ; « Déverrouiller et appliquer » l'applique."""
        form = self.form()
        liste = form.findChild(QtGui.QTreeWidget, "membersTree")
        ligne = liste.visualItemRect(liste.topLevelItem(0)).center()
        QTest.mouseClick(
            liste.viewport(),
            QtCore.Qt.MouseButton.LeftButton,
            QtCore.Qt.KeyboardModifier.NoModifier,
            ligne,
        )
        traiter_les_evenements()
        self.assertIn("M1", enfant(form, "memberLabel").text())
        cliquer(enfant(form, "lockedCheck"))
        self.assertTrue(enfant(form, "lockedCheck").isChecked())
        taper(enfant(form, "Width"), f"{ENCORE_ELARGI:g} mm")
        self.assertIn("M1", enfant(form, "refusalLabel").text())
        self.assertFalse(bouton_ok().isEnabled(), "OK actif malgré le refus")
        self.assertAlmostEqual(self.pieces["M1"].Length.Value, ELARGI, msg="cote refusée écrite")
        cases = enfant(form, "unlockPieces").findChildren(QtGui.QCheckBox)
        self.assertEqual([case.text() for case in cases], ["M1"])
        if not cases[0].isChecked():
            cliquer(cases[0])
        cliquer(enfant(form, "unlockButton"))
        self.assertEqual(enfant(form, "refusalLabel").text(), "")
        self.assertTrue(bouton_ok().isEnabled())
        for nom in ("M1", "M2"):
            self.assertAlmostEqual(self.pieces[nom].Length.Value, ENCORE_ELARGI, msg=nom)
        self.assertFalse(enfant(form, "lockedCheck").isChecked(), "M1 restée en cotes fixes")

    def test_5_tourner_de_90_degres(self) -> None:
        avant = boite_globale(*self.pieces.values())
        taper(enfant(self.form(), "angleZEdit"), "90")
        apres = boite_globale(*self.pieces.values())
        self.assertAlmostEqual(apres.XLength, avant.YLength, delta=TOLERANCE_MM)
        self.assertAlmostEqual(apres.YLength, avant.XLength, delta=TOLERANCE_MM)
        self.assertLess(apres.Center.distanceToPoint(avant.Center), TOLERANCE_MM, "ensemble parti")
        self.assertTrue(bouton_ok().isEnabled())

    def test_6_valider_puis_annuler(self) -> None:
        cliquer(bouton_ok())
        self.assertFalse(panneau_ouvert())
        self.assertEqual(self.doc.UndoNames, ["Modifier l'ensemble"])
        controler_le_document(self, self.doc)
        tourne = boite_globale(*self.pieces.values())
        lancer("Std_Undo")
        self.doc.recompute()
        self.assertEqual(self.cotes(), (LARGEUR, PROFONDEUR, HAUTEUR))
        self.assertAlmostEqual(boite_globale(*self.pieces.values()).XLength, LARGEUR)
        lancer("Std_Redo")
        self.doc.recompute()
        self.assertAlmostEqual(boite_globale(*self.pieces.values()).YLength, tourne.YLength)
        controler_le_document(self, self.doc)

    def test_7_assembler_deux_ensembles(self) -> None:
        """Issue #209 : un montant d'un second ensemble posé contre le bout d'une traverse du
        premier. Tant que l'issue est ouverte, l'assemblage entre deux conteneurs est refusé
        avec une explication, sans panneau ni rien d'écrit. À retourner quand elle sera
        corrigée."""
        traverse = self.pieces["T1"]
        bout = boite_globale(traverse)
        voisin = piece(self.doc, (300.0, *SECTION), (bout.XMin, bout.YMax, 0.0), repere="L")
        self.doc.recompute()
        selectionner(voisin)
        lancer(ENSEMBLE)
        self.assertEqual(len(du_type(self.doc, TYPE_ENSEMBLE)), 2)
        self.assertIsNot(voisin.getParentGeoFeatureGroup(), traverse.getParentGeoFeatureGroup())
        self.doc.clearUndos()
        selectionner(traverse, voisin)
        lancer(TENON_MORTAISE)
        refus = refus_signale()
        self.assertFalse(panneau_ouvert(), "issue #209 corrigée ? scénario à retourner")
        self.assertIn("conteneur", refus)
        self.assertEqual(assemblages(self.doc), [])
        self.assertEqual(self.doc.UndoNames, [])
        controler_le_document(self, self.doc)

    def test_8_rien_dans_la_vue_rapport(self) -> None:
        self.assertEqual(erreurs_python(vue_rapport()), [])
