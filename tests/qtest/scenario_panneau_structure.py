# SPDX-License-Identifier: LGPL-2.1-or-later
"""Scénario QTest S18 : le panneau « Structure » (ADR 0046).

Commande « Structure », clic sur une ligne (la pièce est sélectionnée) et sélection d'une pièce
(sa ligne l'est), puis le menu contextuel d'une ligne : « Renommer… » et sa boîte de saisie,
« Sortir de l'ensemble », « Supprimer » ; la touche F2, qui renomme la ligne choisie comme
dans l'arbre de FreeCAD ; et une pièce glissée à la souris sur la ligne de l'ensemble. Chaque
action est une entrée d'annulation et l'arbre suit le document.

Les lignes de l'arbre sont recréées à chaque rafraîchissement : le scénario ne garde aucune
ligne, il la retrouve par son texte à chaque geste.
"""

from __future__ import annotations

import unittest
from typing import Any, ClassVar

import FreeCADGui as Gui
from PySide import QtCore, QtGui

from tests.qtest.aides import (
    Etapes,
    ReponseALaSaisie,
    ReponseAuMenu,
    activer_faulthandler,
    attendre,
    clic_droit,
    fermer,
    glisser,
    lancer,
    preparer,
    selectionner,
    traiter_les_evenements,
    vider_la_vue_rapport,
    vue_rapport,
)
from tests.qtest.angle_a_queues import controler_le_document
from tests.qtest.pieces import cadre, erreurs_python, piece
from tests.qtest.qttest import QTest

STRUCTURE = "Menuiserie_Structure"
ENSEMBLE = "Menuiserie_Furniture"
PANNEAU = "MenuiserieStructureDock"
ARBRE = "MenuiserieStructureTree"
NOM_DE_L_ENSEMBLE = "Ensemble"
RENOMMER, SORTIR, SUPPRIMER = "Renommer", "Sortir de l'ensemble", "Supprimer"
RETRAIT = "  "


def setUpModule() -> None:
    unittest.addModuleCleanup(activer_faulthandler())


class PanneauStructure(Etapes):
    """Étapes jouées dans l'ordre sur le même document : un cadre rangé dans un ensemble et un
    tasseau libre."""

    doc: ClassVar[Any]
    pieces: ClassVar[dict[str, Any]]
    tasseau: ClassVar[Any]

    @classmethod
    def setUpClass(cls) -> None:
        cls.doc = preparer("ScenarioStructure")
        cls.addClassCleanup(fermer, cls.doc)
        cls.pieces = cadre(cls.doc)
        cls.tasseau = piece(cls.doc, (300.0, 60.0, 22.0), (0.0, 600.0, 0.0), repere="L")
        cls.doc.recompute()
        selectionner(*cls.pieces.values())
        lancer(ENSEMBLE)
        selectionner()
        cls.doc.clearUndos()
        vider_la_vue_rapport()

    def arbre(self) -> Any:
        panneau = Gui.getMainWindow().findChild(QtGui.QDockWidget, PANNEAU)
        self.assertIsNotNone(panneau, "panneau « Structure » absent")
        return panneau.findChild(QtGui.QTreeWidget, ARBRE)

    def lignes(self) -> list[str]:
        """Textes des lignes, en retrait sous leur ensemble, « * » après une ligne choisie."""
        vues: list[str] = []

        def parcourir(ligne: Any, niveau: int) -> None:
            vues.append(RETRAIT * niveau + ligne.text(0) + ("*" if ligne.isSelected() else ""))
            for rang in range(ligne.childCount()):
                parcourir(ligne.child(rang), niveau + 1)

        arbre = self.arbre()
        for rang in range(arbre.topLevelItemCount()):
            parcourir(arbre.topLevelItem(rang), 0)
        return vues

    def point(self, texte: str) -> QtCore.QPoint:
        """Centre de la ligne ``texte`` dans la zone d'affichage de l'arbre."""
        arbre = self.arbre()
        (ligne,) = arbre.findItems(
            texte, QtCore.Qt.MatchFlag.MatchExactly | QtCore.Qt.MatchFlag.MatchRecursive
        )
        arbre.scrollToItem(ligne)
        return arbre.visualItemRect(ligne).center()

    def attendre_les_lignes(self, attendues: list[str]) -> None:
        attendre(lambda: self.lignes() == attendues)
        self.assertEqual(self.lignes(), attendues)

    def au_menu(self, ligne: str, *entrees: str) -> ReponseAuMenu:
        """Clic droit sur ``ligne`` puis clic sur l'entrée du menu."""
        with ReponseAuMenu(*entrees) as menu:
            clic_droit(self.arbre().viewport(), self.point(ligne))
        return menu

    def test_1_ouvrir_le_panneau(self) -> None:
        lancer(STRUCTURE)
        self.assertTrue(attendre(lambda: self.arbre().isVisible()))
        membres = [RETRAIT + nom for nom in ("M1", "M2", "T1", "T2")]
        self.attendre_les_lignes([NOM_DE_L_ENSEMBLE, *membres, "L"])
        self.assertEqual(self.doc.UndoNames, [])

    def test_2_clic_sur_une_ligne_et_selection(self) -> None:
        QTest.mouseClick(
            self.arbre().viewport(),
            QtCore.Qt.MouseButton.LeftButton,
            QtCore.Qt.KeyboardModifier.NoModifier,
            self.point("T1"),
        )
        traiter_les_evenements()
        self.assertEqual(Gui.Selection.getSelection(), [self.pieces["T1"]])
        selectionner(self.tasseau)
        self.assertTrue(attendre(lambda: "L*" in self.lignes()), self.lignes())
        self.assertNotIn(RETRAIT + "T1*", self.lignes())

    def test_3_renommer_par_le_menu(self) -> None:
        with ReponseALaSaisie("Tasseau") as saisie:
            menu = self.au_menu("L", RENOMMER)
        self.assertEqual(saisie.proposes, ["L"])
        self.assertFalse(menu.vues[SORTIR], "« Sortir de l'ensemble » actif pour une pièce libre")
        self.assertTrue(attendre(lambda: self.tasseau.Label == "Tasseau"), self.tasseau.Label)
        self.assertTrue(
            attendre(lambda: any(ligne.startswith("Tasseau") for ligne in self.lignes()))
        )
        self.assertEqual(len(self.doc.UndoNames), 1, self.doc.UndoNames)

    def test_3b_renommer_par_f2(self) -> None:
        """F2 sur la ligne choisie ouvre la même boîte que le menu (Ctrl+F2, rien) ; le
        renommage est une entrée d'annulation, annulée ici pour la suite du scénario."""
        QTest.mouseClick(
            self.arbre().viewport(),
            QtCore.Qt.MouseButton.LeftButton,
            QtCore.Qt.KeyboardModifier.NoModifier,
            self.point("Tasseau"),
        )
        traiter_les_evenements()
        QTest.keyClick(
            self.arbre(), QtCore.Qt.Key.Key_F2, QtCore.Qt.KeyboardModifier.ControlModifier
        )
        QTest.qWait(200)
        self.assertIsNone(QtGui.QApplication.activeModalWidget(), "Ctrl+F2 a ouvert une boîte")
        with ReponseALaSaisie("Liteau") as saisie:
            QTest.keyClick(self.arbre(), QtCore.Qt.Key.Key_F2)
        self.assertEqual(saisie.proposes, ["Tasseau"])
        self.assertTrue(attendre(lambda: self.tasseau.Label == "Liteau"), self.tasseau.Label)
        self.assertTrue(attendre(lambda: any(nom.startswith("Liteau") for nom in self.lignes())))
        self.assertEqual(len(self.doc.UndoNames), 2, self.doc.UndoNames)
        self.doc.undo()
        self.doc.recompute()
        self.assertEqual(self.tasseau.Label, "Tasseau")
        self.assertTrue(
            attendre(lambda: any(ligne.startswith("Tasseau") for ligne in self.lignes())),
            self.lignes(),
        )

    def test_4_glisser_la_piece_dans_l_ensemble(self) -> None:
        glisser(
            self.arbre().viewport(),
            lambda: self.point("Tasseau"),
            lambda: self.point(NOM_DE_L_ENSEMBLE),
        )
        self.assertTrue(
            attendre(lambda: RETRAIT + "Tasseau" in [ligne.rstrip("*") for ligne in self.lignes()]),
            self.lignes(),
        )
        self.assertIs(
            self.tasseau.getParentGeoFeatureGroup(), self.pieces["M1"].getParentGeoFeatureGroup()
        )
        self.assertEqual(len(self.doc.UndoNames), 2, self.doc.UndoNames)
        controler_le_document(self, self.doc)

    def test_5_sortir_de_l_ensemble_par_le_menu(self) -> None:
        self.au_menu("Tasseau", SORTIR)
        self.assertTrue(
            attendre(lambda: "Tasseau" in [ligne.rstrip("*") for ligne in self.lignes()]),
            self.lignes(),
        )
        self.assertIsNone(self.tasseau.getParentGeoFeatureGroup())
        self.assertEqual(len(self.doc.UndoNames), 3, self.doc.UndoNames)
        controler_le_document(self, self.doc)

    def test_6_supprimer_par_le_menu_puis_annuler(self) -> None:
        nom = self.tasseau.Name
        self.au_menu("Tasseau", SUPPRIMER)
        self.assertTrue(attendre(lambda: self.doc.getObject(nom) is None), "pièce non supprimée")
        self.assertTrue(attendre(lambda: not any("Tasseau" in ligne for ligne in self.lignes())))
        self.assertEqual(len(self.doc.UndoNames), 4, self.doc.UndoNames)
        lancer("Std_Undo")
        self.assertIsNotNone(self.doc.getObject(nom))
        self.assertTrue(attendre(lambda: any("Tasseau" in ligne for ligne in self.lignes())))
        self.doc.recompute()
        controler_le_document(self, self.doc)
        lancer("Std_Redo")
        self.assertIsNone(self.doc.getObject(nom), "suppression non rétablie")
        self.assertTrue(attendre(lambda: not any("Tasseau" in ligne for ligne in self.lignes())))
        self.doc.recompute()
        controler_le_document(self, self.doc)
        self.assertEqual(erreurs_python(vue_rapport()), [])
