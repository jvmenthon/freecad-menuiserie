# SPDX-License-Identifier: LGPL-2.1-or-later
"""Scénario QTest : page « Menuiserie », éditeur de dimensions, export et import (ADR 0069).

Lancé dans le vrai FreeCAD, par son mode test (unittest) :

    xvfb-run -a freecad -t tests.qtest.scenario_page_menuiserie

Gestes joués sur les vrais widgets de la page de l'atelier : « Modifier… » des épaisseurs et
formats (saisie bornée, « + », « - », « OK »), « Appliquer » (``saveSettings``), « Exporter… » et
« Importer… » avec une ligne décochée dans l'aperçu. Les dialogues de fichier et de message sont
remplacés par des doublures ; le dossier de l'atelier est un dossier temporaire, et les réglages
sont rétablis à la fin.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from PySide import QtCore, QtGui

from freecad.menuiserie.core.user_dimensions import UserDimensions
from freecad.menuiserie.features import settings as config
from freecad.menuiserie.features.user_dimensions import (
    dimensions_path,
    read_dimensions,
    write_dimensions,
)
from freecad.menuiserie.gui.dimensions_dialog import DimensionsDialog
from freecad.menuiserie.gui.preferences_page import MenuiseriePreferencePage
from tests.qtest.doublures_echange import Doublures, cliquer
from tests.qtest.qttest import QTest

PERSONNELLES = UserDimensions((22.0,), ((2800.0, 2070.0),))
INTEGREES = (12.0, 19.0)

_APPLICATION = QtGui.QApplication.instance() or QtGui.QApplication([])


def _traiter() -> None:
    QtGui.QApplication.processEvents()


def _taper(champ: Any, texte: str) -> None:
    """Saisie au clavier validée par Entrée (un champ numérique prend sa valeur à Entrée)."""
    champ.setFocus(QtCore.Qt.FocusReason.OtherFocusReason)
    QTest.keyClick(champ, QtCore.Qt.Key.Key_A, QtCore.Qt.KeyboardModifier.ControlModifier)
    QTest.keyClicks(champ, texte)
    QTest.keyClick(champ, QtCore.Qt.Key.Key_Return)
    _traiter()


def _selectionner(liste: Any, texte: str) -> None:
    (item,) = liste.findItems(texte, QtCore.Qt.MatchFlag.MatchExactly)
    liste.setCurrentItem(item)
    _traiter()


class Editeur:
    """Remplace la fenêtre modale « Modifier… » : la vraie fenêtre, jouée par ``gestes`` avant
    « OK » (ou « Annuler » si ``annuler``)."""

    def __init__(self) -> None:
        self.gestes: Any = None
        self.annuler = False
        self.fenetres: list[DimensionsDialog] = []

    def __call__(
        self, parent: Any, dimensions: UserDimensions, _integrees: tuple[float, ...]
    ) -> UserDimensions | None:
        fenetre = DimensionsDialog(dimensions, INTEGREES, parent)
        fenetre.show()
        self.fenetres.append(fenetre)
        if self.gestes is not None:
            self.gestes(fenetre)
        bouton = QtGui.QDialogButtonBox.StandardButton.Cancel
        if not self.annuler:
            bouton = QtGui.QDialogButtonBox.StandardButton.Ok
        cliquer(fenetre.buttons.button(bouton))
        resultat = fenetre.result_dimensions() if fenetre.result() else None
        fenetre.deleteLater()
        return resultat


class PageMenuiserie(unittest.TestCase):
    """La page « Menuiserie », jouée comme un utilisateur ouvrant Édition > Préférences."""

    def setUp(self) -> None:
        dossier = tempfile.TemporaryDirectory()
        self.addCleanup(dossier.cleanup)
        self.dossier = Path(dossier.name)
        self.reglages = config.settings()
        self.reglages.reset_all()
        self.addCleanup(self.reglages.reset_all)
        self.reglages.set(config.WORKSHOP_FOLDER, str(self.dossier / "atelier"))
        self.page = MenuiseriePreferencePage()
        self.editeur = Editeur()
        self.page._dimensions._editor = self.editeur
        self.doublures = Doublures()
        self.page._exchange.dialogs = self.doublures.dialogues()
        self.page.form.resize(800, 600)
        self.page.form.show()
        _traiter()
        self.addCleanup(self.page.form.deleteLater)

    def resume(self) -> str:
        return str(self.page._dimensions.summary.text())

    # --- Éditeur de dimensions ------------------------------------------------------------

    def test_groupe_avant_stockage_avec_resume_et_bouton(self) -> None:
        groupes = list(self.page._groups)
        self.assertEqual(groupes[groupes.index("Stockage") - 1], "Épaisseurs et formats")
        self.assertEqual(self.resume(), "aucune valeur personnelle")
        self.assertTrue(self.page._dimensions.button.isVisibleTo(self.page.form))
        self.assertTrue(self.page._exchange.export_button.isVisibleTo(self.page.form))
        self.assertTrue(self.page._exchange.import_button.isVisibleTo(self.page.form))

    def test_ajout_puis_appliquer_ecrit_le_fichier(self) -> None:
        def gestes(fenetre: DimensionsDialog) -> None:
            _taper(fenetre.thickness_spin, "30")
            cliquer(fenetre.thicknesses.add)
            _taper(fenetre.sheet_spins[0], "2800")
            _taper(fenetre.sheet_spins[1], "2070")
            cliquer(fenetre.sheets.add)

        self.editeur.gestes = gestes
        cliquer(self.page._dimensions.button)
        self.assertEqual(self.resume(), "1 épaisseur, 1 format")
        self.assertTrue(self.page.has_pending())
        self.assertFalse(dimensions_path().exists())  # rien n'est écrit avant « Appliquer »
        self.page.saveSettings()
        self.assertEqual(read_dimensions(), UserDimensions((30.0,), ((2800.0, 2070.0),)))
        self.assertFalse(self.page.has_pending())

    def test_suppression_d_une_valeur_personnelle(self) -> None:
        write_dimensions(PERSONNELLES)
        self.page.loadSettings()
        self.assertEqual(self.resume(), "1 épaisseur, 1 format")

        def gestes(fenetre: DimensionsDialog) -> None:
            self.assertFalse(fenetre.thicknesses.remove.isEnabled())  # rien de sélectionné
            _selectionner(fenetre.thicknesses.list, "22")
            self.assertTrue(fenetre.thicknesses.remove.isEnabled())
            cliquer(fenetre.thicknesses.remove)
            _selectionner(fenetre.sheets.list, "2800 x 2070")
            cliquer(fenetre.sheets.remove)

        self.editeur.gestes = gestes
        cliquer(self.page._dimensions.button)
        self.assertEqual(self.resume(), "aucune valeur personnelle")
        self.assertEqual(read_dimensions(), PERSONNELLES)  # fichier intact avant « Appliquer »
        self.page.saveSettings()
        self.assertEqual(read_dimensions(), UserDimensions())

    def test_valeurs_integrees_en_gris_et_non_supprimables(self) -> None:
        def gestes(fenetre: DimensionsDialog) -> None:
            liste = fenetre.thicknesses.list
            self.assertEqual([liste.item(i).text() for i in range(liste.count())], ["12", "19"])
            for index in range(liste.count()):
                item = liste.item(index)
                self.assertFalse(item.flags() & QtCore.Qt.ItemFlag.ItemIsSelectable)
                self.assertEqual(item.foreground().color().name(), "#808080")
            liste.setCurrentRow(0)  # refusé : la ligne n'est pas sélectionnable
            _traiter()
            self.assertFalse(fenetre.thicknesses.remove.isEnabled())
            self.assertEqual(fenetre.sheets.list.count(), 3)  # formats du commerce
            self.assertFalse(fenetre.sheets.remove.isEnabled())

        self.editeur.gestes = gestes
        cliquer(self.page._dimensions.button)
        self.assertEqual(self.editeur.fenetres[0].result_dimensions(), UserDimensions())

    def test_saisie_bornee_comme_le_modele(self) -> None:
        def gestes(fenetre: DimensionsDialog) -> None:
            epaisseur = fenetre.thickness_spin
            self.assertEqual((epaisseur.minimum(), epaisseur.maximum()), (0.1, 300.0))
            for champ in fenetre.sheet_spins:
                self.assertEqual((champ.minimum(), champ.maximum()), (0.1, 20000.0))
            _taper(epaisseur, "0")  # refusé par le champ : la valeur reste dans les bornes
            self.assertGreaterEqual(epaisseur.value(), 0.1)
            epaisseur.setValue(0.1)
            cliquer(fenetre.thicknesses.add)  # le minimum est accepté

        self.editeur.gestes = gestes
        cliquer(self.page._dimensions.button)
        self.assertEqual(self.page._dimensions.shown().thicknesses, (0.1,))

    def test_annuler_ne_change_rien_et_charger_abandonne_l_attente(self) -> None:
        self.editeur.annuler = True
        self.editeur.gestes = lambda fenetre: cliquer(fenetre.thicknesses.add)
        cliquer(self.page._dimensions.button)
        self.assertFalse(self.page.has_pending())
        self.assertEqual(self.resume(), "aucune valeur personnelle")
        self.editeur.annuler = False  # « OK » : l'ajout est mis en attente, puis abandonné
        cliquer(self.page._dimensions.button)
        self.assertTrue(self.page.has_pending())
        self.page.loadSettings()
        self.assertFalse(self.page.has_pending())
        self.assertEqual(self.resume(), "aucune valeur personnelle")

    def test_retablir_tout_ne_touche_pas_aux_dimensions(self) -> None:
        write_dimensions(PERSONNELLES)
        fichier = dimensions_path()
        texte = fichier.read_text(encoding="utf-8")
        self.page.loadSettings()
        cliquer(self.page.form.findChild(QtGui.QPushButton, "resetAll"))
        self.page.saveSettings()  # rétablit aussi le dossier de l'atelier : le fichier reste là
        self.assertEqual(fichier.read_text(encoding="utf-8"), texte)

    # --- Export et import -----------------------------------------------------------------

    def exporter(self) -> Path:
        sortie = self.dossier / "atelier.json"
        self.doublures.fichier = sortie
        cliquer(self.page._exchange.export_button)
        return sortie

    def test_export_contient_reglages_et_dimensions(self) -> None:
        self.reglages.set(config.LENGTH, 1234.0)
        write_dimensions(PERSONNELLES)
        self.page.loadSettings()
        contenu = json.loads(self.exporter().read_text(encoding="utf-8"))
        self.assertEqual(contenu["settings"][config.LENGTH], 1234.0)
        self.assertEqual(contenu["dimensions"]["thicknesses"], [22.0])
        self.assertEqual(contenu["dimensions"]["sheets"], [[2800.0, 2070.0]])
        ((texte, erreur),) = self.doublures.messages
        self.assertFalse(erreur)
        self.assertIn("atelier.json", texte)

    def test_import_apercu_decoche_les_dimensions_puis_les_reprend(self) -> None:
        self.reglages.set(config.LENGTH, 1234.0)
        write_dimensions(PERSONNELLES)
        self.page.loadSettings()
        fichier = self.exporter()
        self.reglages.reset(config.LENGTH)
        write_dimensions(UserDimensions())
        self.page.loadSettings()
        self.doublures.messages.clear()
        # 1. dimensions décochées : seul le réglage est repris, dans le champ, sans être écrit
        self.doublures.fichier = fichier
        self.doublures.decocher = {"dimensions"}
        cliquer(self.page._exchange.import_button)
        lignes, entete, avertissement = self.doublures.apercus[-1]
        self.assertEqual([ligne.key for ligne in lignes], [config.LENGTH, "dimensions"])
        self.assertEqual(lignes[1].label, "Épaisseurs et formats personnels")
        self.assertEqual(lignes[1].imported, "22 mm ; 2800 x 2070 mm")
        self.assertEqual((avertissement, self.doublures.messages), ("", []))
        self.assertIn("2 réglages changés", entete)
        ligne = self.page._rows[config.LENGTH]
        self.assertEqual(ligne.value(), 1234.0)
        self.assertTrue(ligne.modified_shown)
        self.assertEqual(self.resume(), "aucune valeur personnelle")
        self.assertEqual(self.reglages.value(config.LENGTH), 800.0)  # pas encore écrit
        self.page.saveSettings()
        self.assertEqual(self.reglages.value(config.LENGTH), 1234.0)
        self.assertEqual(read_dimensions(), UserDimensions())
        # 2. tout coché : les dimensions attendent « Appliquer » comme le reste de la page
        self.reglages.reset(config.LENGTH)
        self.page.loadSettings()
        self.doublures.decocher = set()
        cliquer(self.page._exchange.import_button)
        self.assertEqual(self.resume(), "1 épaisseur, 1 format")
        self.assertTrue(self.page.has_pending())
        self.assertEqual(read_dimensions(), UserDimensions())
        self.page.saveSettings()
        self.assertEqual(read_dimensions(), PERSONNELLES)
        self.assertEqual(self.reglages.value(config.LENGTH), 1234.0)

    def test_fichier_refuse_ne_change_rien(self) -> None:
        fichier = self.dossier / "mauvais.json"
        fichier.write_text('{"format": 1, "dimensions": {"thicknesses": [0]}}', encoding="utf-8")
        self.doublures.fichier = fichier
        cliquer(self.page._exchange.import_button)
        ((texte, erreur),) = self.doublures.messages
        self.assertTrue(erreur)
        self.assertIn("Fichier refusé, aucun réglage n'est modifié.", texte)
        self.assertFalse(self.page.has_pending())
