# SPDX-License-Identifier: LGPL-2.1-or-later
"""Scénario QTest : page « Menuiserie » des préférences, construite d'après le catalogue (ADR 0069).

Lancé dans le vrai FreeCAD, par son mode test (unittest) :

    xvfb-run -a freecad -t tests.qtest.scenario_page_reglages

Gestes joués sur les vrais widgets : recherche au clavier, case « Afficher les réglages
avancés », saisie d'une cote, case « Dernier utilisé », bouton « Rétablir » d'une ligne et
« Rétablir tout ». Les réglages sont écrits dans un stockage en mémoire, jamais dans les
préférences de l'utilisateur. Le module n'a besoin que de Qt (couche ``PySide``).
"""

from __future__ import annotations

import unittest
from typing import Any

from PySide import QtCore, QtGui

from freecad.menuiserie.kit.config.catalog import Catalog, Kind, Setting
from freecad.menuiserie.kit.config.page import SettingsPage
from freecad.menuiserie.kit.config.store import MemoryStore, Settings
from tests.qtest.qttest import QTest

JEU = Setting(
    "Jeu", Kind.FLOAT, 2.0, "Jeu de fond", "Profondeur en plus.", "Assemblages",
    unit="mm", minimum=0.0, maximum=20.0, remember_last=True,
)  # fmt: skip
NOMBRE = Setting("Nombre", Kind.INT, 3, "Nombre de queues", "Quantité.", "Assemblages")
FIN = Setting(
    "Fin", Kind.BOOL, False, "Réglage fin", "Pour les experts.", "Avancé", advanced=True
)  # fmt: skip
DOSSIER = Setting("Dossier", Kind.PATH, "", "Dossier de l'atelier", "Fichiers.", "Stockage")
CATALOGUE = Catalog([JEU, NOMBRE, FIN, DOSSIER])


# Dans FreeCAD, l'application Qt existe ; seule, elle est créée ici (essai hors FreeCAD).
_APPLICATION = QtGui.QApplication.instance() or QtGui.QApplication([])


def _traiter() -> None:
    QtGui.QApplication.processEvents()


def _cliquer(widget: Any) -> None:
    QTest.mouseClick(widget, QtCore.Qt.MouseButton.LeftButton)
    _traiter()


def _taper(champ: Any, texte: str) -> None:
    champ.setFocus(QtCore.Qt.FocusReason.OtherFocusReason)
    QTest.keyClick(champ, QtCore.Qt.Key.Key_A, QtCore.Qt.KeyboardModifier.ControlModifier)
    QTest.keyClick(champ, QtCore.Qt.Key.Key_Backspace)  # efface la sélection (champ vidé)
    QTest.keyClicks(champ, texte)
    QTest.keyClick(champ, QtCore.Qt.Key.Key_Tab)
    _traiter()


class PageReglages(unittest.TestCase):
    """La page, jouée comme un utilisateur ouvrant Édition > Préférences."""

    def setUp(self) -> None:
        self.reglages = Settings(CATALOGUE, MemoryStore())
        self.page = SettingsPage(CATALOGUE, self.reglages)
        self.page.form.resize(700, 500)
        self.page.form.show()
        _traiter()
        self.addCleanup(self.page.form.deleteLater)

    def visibles(self) -> list[str]:
        return [
            cle for cle, ligne in self.page._rows.items() if ligne.label.isVisibleTo(self.page.form)
        ]

    def test_construction_un_groupe_par_groupe_du_catalogue(self) -> None:
        self.assertEqual(list(self.page._groups), ["Assemblages", "Avancé", "Stockage"])
        self.assertEqual(self.visibles(), ["Jeu", "Nombre", "Dossier"])  # avancé caché
        self.assertTrue(self.page.search.placeholderText())

    def test_recherche_sur_le_libelle_et_l_infobulle(self) -> None:
        _taper(self.page.search, "queues")
        self.assertEqual(self.visibles(), ["Nombre"])
        _taper(self.page.search, "profondeur")  # mot de l'infobulle de « Jeu »
        self.assertEqual(self.visibles(), ["Jeu"])
        _taper(self.page.search, "rien de tel")
        self.assertEqual(self.visibles(), [])
        self.assertTrue(self.page.nothing.isVisibleTo(self.page.form))
        _taper(self.page.search, "")
        self.assertEqual(self.visibles(), ["Jeu", "Nombre", "Dossier"])

    def test_reglages_avances_sur_demande(self) -> None:
        _cliquer(self.page.advanced)
        self.assertIn("Fin", self.visibles())
        _cliquer(self.page.advanced)
        self.assertNotIn("Fin", self.visibles())

    def test_groupe_replie_donne_son_resume(self) -> None:
        groupe = self.page._groups["Assemblages"]
        self.page._rows["Jeu"].editor.widget.setValue(5.0)
        _cliquer(groupe.header)
        self.assertFalse(groupe.body.isVisibleTo(self.page.form))
        self.assertEqual(groupe.summary.text(), "(2 réglages, 1 modifié)")
        _cliquer(groupe.header)
        self.assertTrue(groupe.body.isVisibleTo(self.page.form))

    def test_ecriture_a_la_validation_seulement(self) -> None:
        ligne = self.page._rows["Jeu"]
        _taper(ligne.editor.widget, "5")
        self.assertTrue(ligne.modified_shown)
        self.assertIn("bold", ligne.label.styleSheet())
        self.assertEqual(self.reglages.value("Jeu"), 2.0)  # rien d'écrit avant « OK »
        _cliquer(ligne.remember)
        self.page.saveSettings()
        self.assertEqual(self.reglages.value("Jeu"), 5.0)
        self.assertTrue(self.reglages.remembers_last("Jeu"))
        self.assertIsNone(self.page._rows["Nombre"].remember)  # pas de case : non prévu

    def test_retablir_une_ligne_puis_tout(self) -> None:
        ligne = self.page._rows["Jeu"]
        ligne.editor.widget.setValue(7.0)
        self.page._rows["Nombre"].editor.widget.setValue(9)
        _cliquer(ligne.reset_button)
        self.assertEqual(ligne.value(), 2.0)
        self.assertFalse(ligne.modified_shown)
        self.assertEqual(ligne.label.styleSheet(), "")
        self.assertEqual(self.page._rows["Nombre"].value(), 9)  # les autres lignes restent
        self.page.saveSettings()
        self.assertEqual(self.reglages.value("Nombre"), 9)
        _cliquer(self.page.form.findChild(QtGui.QPushButton, "resetAll"))
        self.assertEqual(self.page._rows["Nombre"].value(), 3)
        self.page.saveSettings()
        self.assertEqual(self.reglages.value("Nombre"), 3)

    def test_rechargement_affiche_les_valeurs_enregistrees(self) -> None:
        self.reglages.set("Jeu", 4.0)
        self.reglages.set_remember_last("Jeu", True)
        self.page.loadSettings()
        self.assertEqual(self.page._rows["Jeu"].value(), 4.0)
        self.assertTrue(self.page._rows["Jeu"].remembers())

    def test_champ_dossier_et_texte_trop_long(self) -> None:
        champ = self.page._rows["Dossier"].editor.widget.layout().itemAt(0).widget()
        _taper(champ, "/donnees/atelier")
        self.page.saveSettings()
        self.assertEqual(self.reglages.value("Dossier"), "/donnees/atelier")

    def test_dossier_relatif_refuse_et_non_ecrit(self) -> None:
        champ = self.page._rows["Dossier"].editor.widget.layout().itemAt(0).widget()
        _taper(champ, "atelier/pieces")
        self.page.saveSettings()
        self.assertEqual(self.reglages.value("Dossier"), "")  # refusé : jamais écrit
        self.assertEqual(champ.text(), "")  # la ligne retrouve la valeur enregistrée

    def test_ligne_non_touchee_n_est_pas_reecrite(self) -> None:
        self.reglages.set("Nombre", 5)
        self.page.loadSettings()
        self.reglages.set("Nombre", 6)  # changé ailleurs pendant que la page est ouverte
        self.page.saveSettings()  # « OK » sans toucher à cette ligne
        self.assertEqual(self.reglages.value("Nombre"), 6)


MATERIAU = Setting(
    "Materiau", Kind.TEXT, "", "Matériau", "Matériau d'une pièce neuve.", "Pièces neuves"
)
CATALOGUE_LISTE = Catalog([MATERIAU])
CHOIX = {"Materiau": [("", "Premier matériau"), ("chene", "Chêne")]}


class PageReglagesListe(unittest.TestCase):
    """Texte à liste déroulante (matériau) : une valeur enregistrée absente de la liste (matériau
    retiré de la bibliothèque) ne doit pas être effacée en silence par « OK »."""

    def setUp(self) -> None:
        self.reglages = Settings(CATALOGUE_LISTE, MemoryStore())
        self.page = SettingsPage(CATALOGUE_LISTE, self.reglages, choices=CHOIX)
        self.page.form.show()
        _traiter()
        self.addCleanup(self.page.form.deleteLater)

    def test_valeur_de_la_liste_enregistree(self) -> None:
        combo = self.page._rows["Materiau"].editor.widget
        combo.setCurrentIndex(combo.findData("chene"))
        self.page.saveSettings()
        self.assertEqual(self.reglages.value("Materiau"), "chene")

    def test_valeur_absente_de_la_liste_conservee_par_ok(self) -> None:
        self.reglages.set("Materiau", "noyer")  # matériau de l'utilisateur, plus dans la liste
        self.page.loadSettings()
        self.page.saveSettings()  # « OK » sans toucher à ce réglage
        self.assertEqual(self.reglages.value("Materiau"), "noyer")
