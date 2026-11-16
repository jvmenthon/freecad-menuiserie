# SPDX-License-Identifier: LGPL-2.1-or-later
"""Scénario QTest S8 : un cadre complet, puis sa liste de débit.

Quatre pièces (deux montants, deux traverses), quatre tenons-mortaises posés par la commande et
son panneau, puis l'aperçu de la liste de débit, son export CSV par la vraie boîte
d'enregistrement, et la feuille « Liste de débit ». Attrape une rupture de la chaîne création,
assemblage, débit : les traverses doivent y figurer avec leurs tenons (cote hors tout).
"""

from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path
from typing import Any, ClassVar

from PySide import QtGui

from tests.gui.verifications_assemblages import usinee_de
from tests.qtest.aides import (
    Etapes,
    ReponseAEnregistrer,
    ReponseAuxBoites,
    activer_faulthandler,
    attendre,
    bouton_ok,
    cliquer,
    fermer,
    lancer,
    panneau_ouvert,
    preparer,
    selectionner,
    vider_la_vue_rapport,
    vue_rapport,
)
from tests.qtest.angle_a_queues import controler_le_document
from tests.qtest.pieces import assemblages, cadre, erreurs_python, piece

TENON_MORTAISE = "Menuiserie_MortiseTenon"
APERCU = "Menuiserie_CutListPreview"
FEUILLE = "Menuiserie_CutList"
FENETRE_APERCU = "MenuiserieCutListPreview"
TEXTE_APERCU = "MenuiserieCutListPreviewBrowser"
BOUTON_CSV = "MenuiserieCutListPreviewCsv"
BOUTON_ACTUALISER = "MenuiserieCutListPreviewRefresh"
BOUTON_FERMER = "MenuiserieCutListPreviewClose"
COUPLES = (("T1", "M1"), ("T1", "M2"), ("T2", "M1"), ("T2", "M2"))
NUMEROTER = "Numéroter"


def setUpModule() -> None:
    unittest.addModuleCleanup(activer_faulthandler())


def apercus() -> list[Any]:
    """Fenêtres d'aperçu de la liste de débit ouvertes."""
    import FreeCADGui as Gui

    return [
        fenetre
        for fenetre in Gui.getMainWindow().findChildren(QtGui.QDialog, FENETRE_APERCU)
        if fenetre.isVisible()
    ]


class CadreEtDebit(Etapes):
    """Étapes jouées dans l'ordre sur le même document."""

    doc: ClassVar[Any]
    pieces: ClassVar[dict[str, Any]]
    dossier: ClassVar[Path]

    @classmethod
    def setUpClass(cls) -> None:
        cls.doc = preparer("ScenarioCadreEtDebit")
        cls.addClassCleanup(fermer, cls.doc)
        temporaire = tempfile.TemporaryDirectory()
        cls.addClassCleanup(temporaire.cleanup)
        cls.dossier = Path(temporaire.name)
        cls.pieces = cadre(cls.doc)
        cls.doc.clearUndos()
        vider_la_vue_rapport()

    def longueur_hors_tout(self) -> float:
        """Longueur d'une traverse avec ses deux tenons, mesurée sur sa pièce usinée (la
        traverse est couchée le long de Y)."""
        return float(usinee_de(self.pieces["T1"]).Shape.BoundBox.YLength)

    def test_1_quatre_tenons_mortaises(self) -> None:
        for traverse, montant in COUPLES:
            with self.subTest(assemblage=f"{traverse}-{montant}"):
                selectionner(self.pieces[traverse], self.pieces[montant])
                lancer(TENON_MORTAISE)
                cliquer(bouton_ok())
                self.assertFalse(panneau_ouvert())
        self.assertEqual(len(assemblages(self.doc)), len(COUPLES))
        self.assertEqual(len(self.doc.UndoNames), len(COUPLES), self.doc.UndoNames)
        controler_le_document(self, self.doc)
        selectionner()

    def test_2_apercu(self) -> None:
        lancer(APERCU)
        self.assertTrue(attendre(lambda: len(apercus()) == 1), "aperçu non ouvert")
        texte = apercus()[0].findChild(QtGui.QTextBrowser, TEXTE_APERCU).toPlainText()
        for attendu in ("M1, M2", "T1, T2", "600", "280"):
            self.assertIn(attendu, texte)
        self.assertEqual(len(self.doc.UndoNames), len(COUPLES), "l'aperçu a modifié le document")

    def test_3_export_csv_depuis_l_apercu(self) -> None:
        fichier = self.dossier / "debit.csv"
        with ReponseAEnregistrer(str(fichier)):
            cliquer(apercus()[0].findChild(QtGui.QPushButton, BOUTON_CSV))
        self.assertTrue(fichier.is_file(), "CSV non écrit")
        contenu = fichier.read_text(encoding="utf-8-sig")
        lignes = list(csv.DictReader(contenu.splitlines(), dialect=csv.Sniffer().sniff(contenu)))
        montants, traverses = lignes[0], lignes[1]
        self.assertEqual((montants["Repère"], montants["Qté"]), ("M1, M2", "2"))
        self.assertEqual((traverses["Repère"], traverses["Qté"]), ("T1, T2", "2"))
        self.assertEqual(float(montants["Longueur finie (mm)"]), 600.0)
        surcote = float(montants["Longueur de débit (mm)"]) - 600.0
        tenons = self.longueur_hors_tout() - 280.0
        self.assertGreater(tenons, 1.0)
        # La traverse est débitée avec ses deux tenons, et la remarque le dit.
        self.assertAlmostEqual(
            float(traverses["Longueur de débit (mm)"]), 280.0 + tenons + surcote, delta=0.01
        )
        self.assertIn(f"+{tenons:g}", traverses["Remarque"])

    def test_4_piece_sans_repere(self) -> None:
        """Une pièce ajoutée sans repère : « Actualiser » la montre, puis la commande propose de
        la numéroter (une entrée d'annulation)."""
        sans_repere = piece(self.doc, (300.0, 40.0, 18.0), (0.0, 500.0, 0.0))
        self.doc.recompute()
        self.doc.clearUndos()
        cliquer(apercus()[0].findChild(QtGui.QPushButton, BOUTON_ACTUALISER))
        texte = apercus()[0].findChild(QtGui.QTextBrowser, TEXTE_APERCU).toPlainText()
        self.assertIn("300", texte)
        cliquer(apercus()[0].findChild(QtGui.QPushButton, BOUTON_FERMER))
        self.assertTrue(attendre(lambda: not apercus()), "aperçu resté ouvert")
        with ReponseAuxBoites(NUMEROTER) as boites:
            lancer(APERCU)
        self.assertEqual(len(boites.vues), 1, boites.vues)
        self.assertTrue(sans_repere.Mark, "pièce non numérotée")
        self.assertEqual(len(self.doc.UndoNames), 1, self.doc.UndoNames)
        self.assertTrue(attendre(lambda: len(apercus()) == 1), "aperçu non ouvert")
        cliquer(apercus()[0].findChild(QtGui.QPushButton, BOUTON_FERMER))
        lancer("Std_Undo")
        self.assertFalse(sans_repere.Mark)
        lancer("Std_Redo")

    def test_5_feuille_liste_de_debit(self) -> None:
        avant = set(self.doc.Objects)
        annulations = len(self.doc.UndoNames)
        lancer(FEUILLE)
        creees = [obj.TypeId for obj in self.doc.Objects if obj not in avant]
        self.assertIn("Spreadsheet::Sheet", creees)
        self.assertEqual(len(self.doc.UndoNames), annulations + 1, self.doc.UndoNames)
        lancer("Std_Undo")
        self.assertEqual(set(self.doc.Objects), avant)

    def test_6_rien_dans_la_vue_rapport(self) -> None:
        self.assertEqual(erreurs_python(vue_rapport()), [])
        controler_le_document(self, self.doc)
