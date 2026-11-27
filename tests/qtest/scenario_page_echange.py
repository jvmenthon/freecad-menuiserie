# SPDX-License-Identifier: LGPL-2.1-or-later
"""Scénario QTest : export et import des réglages depuis la page de préférences (ADR 0069).

Lancé dans le vrai FreeCAD, par son mode test (unittest) :

    xvfb-run -a freecad -t tests.qtest.scenario_page_echange

Gestes joués sur les vrais widgets : boutons « Exporter… » et « Importer… », aperçu avec une case
décochée, « Reprendre la sélection », puis « Appliquer » (``saveSettings``). Les dialogues de
fichier et de message sont remplacés par des doublures (``Dialogs``) : aucune fenêtre modale
ne s'ouvre. Les réglages sont écrits dans un stockage en mémoire. Le module n'a besoin que de Qt
(couche ``PySide``) et du paquet générique ``kit/config``.
"""

from __future__ import annotations

import tempfile
import unittest
from collections.abc import Mapping, Sequence
from pathlib import Path

from PySide import QtCore, QtGui

from freecad.menuiserie.kit.config import exchange
from freecad.menuiserie.kit.config.catalog import Catalog, Kind, Relation, Setting, Value
from freecad.menuiserie.kit.config.import_model import (
    ImportOffer,
    ImportRow,
    build_rows,
    chosen_values,
)
from freecad.menuiserie.kit.config.page import SettingsPage
from freecad.menuiserie.kit.config.page_exchange import ExchangeActions, ExchangeRow
from freecad.menuiserie.kit.config.page_import import ImportPreview
from freecad.menuiserie.kit.config.page_model import ExtraRow
from freecad.menuiserie.kit.config.store import MemoryStore, Settings
from tests.qtest.doublures_echange import Doublures, cliquer

JEU = Setting(
    "Jeu", Kind.FLOAT, 2.0, "Jeu de fond", "Profondeur en plus.", "Assemblages",
    unit="mm", minimum=0.0, maximum=20.0, remember_last=True,
)  # fmt: skip
NOMBRE = Setting("Nombre", Kind.INT, 3, "Nombre de queues", "Quantité.", "Assemblages")
DOSSIER = Setting("Dossier", Kind.PATH, "", "Dossier de l'atelier", "Fichiers.", "Stockage")
CATALOGUE = Catalog([JEU, NOMBRE, DOSSIER])

_APPLICATION = QtGui.QApplication.instance() or QtGui.QApplication([])


def _traiter() -> None:
    QtGui.QApplication.processEvents()


class PageEchange(unittest.TestCase):
    """Page avec la ligne « Réglages de l'atelier » dans « Stockage » et une ligne de l'atelier
    dans un groupe nouveau, jouée comme un utilisateur."""

    def setUp(self) -> None:
        dossier = tempfile.TemporaryDirectory()
        self.addCleanup(dossier.cleanup)
        self.dossier = Path(dossier.name)
        self.reglages = Settings(CATALOGUE, MemoryStore())
        self.doublures = Doublures()
        self.appels: list[str] = []
        self.etiquette = QtGui.QLabel("3 valeurs")
        extra = ExtraRow(
            "Épaisseurs", "Valeurs personnelles", self.etiquette, "Propres à l'atelier.",
            "Stockage", load=self.charger, save=self.ecrire, pending=self.en_attente,
        )  # fmt: skip
        self.attente = False
        actions = ExchangeActions(
            lambda: self.dossier / "atelier.json",
            self.exporter,
            self.lire,
            lambda erreur: f"refus : {erreur.reason.value}",
            self.reprendre,
            lambda: self.page.has_pending(),
        )
        self.echange = ExchangeRow(actions, "Stockage", dialogs=self.doublures.dialogues())
        self.page = SettingsPage(CATALOGUE, self.reglages, extras=[extra, self.echange.extra_row()])
        self.page.form.resize(700, 500)
        self.page.form.show()
        _traiter()
        self.addCleanup(self.page.form.deleteLater)

    # --- Ce que l'atelier fournit à la page -----------------------------------------------

    def charger(self) -> None:
        self.appels.append("load")
        self.attente = False

    def ecrire(self) -> None:
        self.appels.append("save")
        self.attente = False

    def en_attente(self) -> bool:
        return self.attente

    def exporter(self, chemin: Path) -> None:
        exchange.write_export(chemin, exchange.export_payload(CATALOGUE, self.reglages))

    def lire(self, chemin: Path) -> ImportOffer:
        resultat = exchange.read_import(chemin, CATALOGUE)
        changements = exchange.preview(CATALOGUE, self.reglages, resultat)
        return ImportOffer(tuple(build_rows(CATALOGUE, changements)), resultat.ignored)

    def reprendre(self, rows: Sequence[ImportRow]) -> None:
        self.page.set_pending(chosen_values(rows, [row.key for row in rows]))

    def fichier_importe(self, texte: str) -> Path:
        chemin = self.dossier / "entree.json"
        chemin.write_text(texte, encoding="utf-8")
        self.doublures.fichier = chemin
        return chemin

    # --- Lignes supplémentaires -----------------------------------------------------------

    def test_groupe_nouveau_avant_stockage_et_ligne_de_stockage(self) -> None:
        self.assertEqual(list(self.page._groups), ["Assemblages", "Épaisseurs", "Stockage"])
        self.assertTrue(self.etiquette.isVisibleTo(self.page.form))
        self.assertTrue(self.echange.export_button.isVisibleTo(self.page.form))
        self.assertTrue(self.echange.import_button.isVisibleTo(self.page.form))
        self.assertEqual(self.page._groups["Stockage"].summary.text(), "(2 réglages)")

    def test_recherche_trouve_la_ligne_de_l_atelier(self) -> None:
        self.page.search.setText("personnelles")
        _traiter()
        self.assertTrue(self.etiquette.isVisibleTo(self.page.form))
        self.assertFalse(self.page._groups["Assemblages"].frame.isVisibleTo(self.page.form))
        self.assertFalse(self.page.nothing.isVisibleTo(self.page.form))
        self.page.search.setText("introuvable")
        _traiter()
        self.assertFalse(self.etiquette.isVisibleTo(self.page.form))
        self.assertTrue(self.page.nothing.isVisibleTo(self.page.form))

    def test_chargement_et_enregistrement_suivent_la_page(self) -> None:
        self.page.loadSettings()
        self.page.saveSettings()
        self.assertEqual(self.appels, ["load", "load", "save"])  # un chargement à la construction

    # --- Import ---------------------------------------------------------------------------

    def test_import_apercu_decoche_reprendre_puis_appliquer(self) -> None:
        self.fichier_importe(
            '{"format": 1, "settings": {"Jeu": 5.0, "JeuRememberLast": true, "Nombre": 7,'
            ' "Inconnue": 1}, "autre": {}}'
        )
        self.doublures.decocher = {"Nombre"}
        cliquer(self.echange.import_button)
        ((lignes, entete, avertissement),) = self.doublures.apercus
        self.assertEqual([ligne.key for ligne in lignes], ["Jeu", "JeuRememberLast", "Nombre"])
        self.assertIn("3 réglages changés", entete)
        self.assertIn("2 réglages inconnus ignorés", avertissement)
        self.assertEqual(self.doublures.messages, [])
        jeu, nombre = self.page._rows["Jeu"], self.page._rows["Nombre"]
        self.assertEqual((jeu.value(), jeu.remembers()), (5.0, True))  # repris dans les champs
        self.assertTrue(jeu.modified_shown)
        self.assertEqual(nombre.value(), 3)  # case décochée : champ inchangé
        self.assertTrue(self.page.has_pending())
        self.assertEqual(self.reglages.value("Jeu"), 2.0)  # rien n'est écrit avant « Appliquer »
        self.page.saveSettings()
        self.assertEqual(self.reglages.value("Jeu"), 5.0)
        self.assertTrue(self.reglages.remembers_last("Jeu"))
        self.assertEqual(self.reglages.value("Nombre"), 3)
        self.assertFalse(self.page.has_pending())

    def test_import_annule_ne_change_rien(self) -> None:
        self.fichier_importe('{"format": 1, "settings": {"Jeu": 5.0}}')
        self.doublures.annuler_apercu = True
        cliquer(self.echange.import_button)
        self.assertEqual(self.page._rows["Jeu"].value(), 2.0)
        self.assertFalse(self.page.has_pending())

    def test_import_sans_choix_de_fichier_ne_fait_rien(self) -> None:
        self.doublures.fichier = None
        cliquer(self.echange.import_button)
        self.assertEqual((self.doublures.apercus, self.doublures.messages), ([], []))

    def test_fichier_refuse_message_et_rien_ne_change(self) -> None:
        self.fichier_importe('{"format": 1, "settings": {"Jeu": 99.0}}')  # hors bornes
        cliquer(self.echange.import_button)
        self.assertEqual(self.doublures.messages, [("refus : invalid_setting", True)])
        self.assertEqual(self.doublures.apercus, [])
        self.assertEqual(self.page._rows["Jeu"].value(), 2.0)
        self.assertFalse(self.page.has_pending())

    def test_aucun_changement_message_bref_avec_les_ignores(self) -> None:
        self.fichier_importe('{"format": 1, "settings": {"Jeu": 2.0, "Inconnue": 1}}')
        cliquer(self.echange.import_button)
        ((texte, erreur),) = self.doublures.messages
        self.assertFalse(erreur)
        self.assertTrue(texte.startswith("Aucun réglage à changer."))
        self.assertIn("1 réglage inconnu ignoré : « Inconnue »", texte)
        self.assertEqual(self.doublures.apercus, [])

    # --- Export ---------------------------------------------------------------------------

    def test_export_relu_identique(self) -> None:
        self.reglages.set("Jeu", 4.0)
        self.reglages.set("Nombre", 6)
        self.page.loadSettings()
        sortie = self.dossier / "atelier.json"
        self.doublures.fichier = sortie
        cliquer(self.echange.export_button)
        resultat = exchange.read_import(sortie, CATALOGUE)
        self.assertEqual(resultat.values["Jeu"], 4.0)
        self.assertEqual(resultat.values["Nombre"], 6)
        self.assertEqual(resultat.ignored, ())
        self.assertEqual(exchange.preview(CATALOGUE, self.reglages, resultat), [])  # identique
        ((texte, erreur),) = self.doublures.messages
        self.assertFalse(erreur)
        self.assertIn(str(sortie), texte)
        self.assertNotIn("non enregistrées", texte)

    def test_export_avec_modifications_non_enregistrees_le_dit(self) -> None:
        self.page._rows["Nombre"].editor.widget.setValue(8)  # modifié, pas enregistré
        sortie = self.dossier / "atelier.json"
        self.doublures.fichier = sortie
        cliquer(self.echange.export_button)
        ((texte, _erreur),) = self.doublures.messages
        self.assertIn("Les modifications non enregistrées ne sont pas exportées.", texte)
        self.assertEqual(exchange.read_import(sortie, CATALOGUE).values["Nombre"], 3)

    def test_export_ajoute_l_extension_json(self) -> None:
        self.doublures.fichier = self.dossier / "sans_extension"
        cliquer(self.echange.export_button)
        self.assertTrue((self.dossier / "sans_extension.json").is_file())

    def test_export_annule_n_ecrit_rien(self) -> None:
        self.doublures.fichier = None
        cliquer(self.echange.export_button)
        self.assertEqual(self.doublures.messages, [])
        self.assertEqual(list(self.dossier.iterdir()), [])

    def test_export_impossible_message_d_erreur(self) -> None:
        (self.dossier / "bloc").write_text("", encoding="utf-8")  # un fichier, pas un dossier
        self.doublures.fichier = self.dossier / "bloc" / "atelier.json"
        cliquer(self.echange.export_button)
        self.assertEqual(self.doublures.messages, [("refus : not_written", True)])


class ApercuDeLImport(unittest.TestCase):
    """La fenêtre d'aperçu seule : tableau, valeur importée en bleu, bandeau, boutons."""

    LIGNES = (
        ImportRow("Jeu", "Assemblages", "Jeu de fond", "2 mm", "1.5 mm", 1.5),
        ImportRow("Nombre", "Assemblages", "Nombre de queues", "3", "7", 7),
    )

    def fenetre(self, avertissement: str = "") -> ImportPreview:
        fenetre = ImportPreview(self.LIGNES, "Fichier : a.json · 2 réglages changés", avertissement)
        fenetre.show()
        _traiter()
        self.addCleanup(fenetre.deleteLater)
        return fenetre

    def test_tableau_et_cases_cochees(self) -> None:
        fenetre = self.fenetre()
        table = fenetre.table
        self.assertEqual((table.rowCount(), table.columnCount()), (2, 5))
        titres = [table.horizontalHeaderItem(i).text() for i in range(5)]
        self.assertEqual(titres, ["", "Groupe", "Réglage", "Actuel", "Importé"])
        self.assertEqual(
            [table.item(0, colonne).text() for colonne in range(1, 5)],
            ["Assemblages", "Jeu de fond", "2 mm", "1.5 mm"],
        )
        self.assertEqual(fenetre.checked_keys(), ["Jeu", "Nombre"])  # tout est coché au départ
        bleu = table.item(0, 4).foreground().color()
        self.assertEqual(bleu.name(), "#0b5cad")
        self.assertTrue(fenetre.take_button.isDefault())

    def test_bandeau_visible_seulement_s_il_y_a_des_ignores(self) -> None:
        self.assertFalse(self.fenetre().warning.isVisible())
        fenetre = self.fenetre("2 réglages inconnus ignorés : « A », « B ».")
        self.assertTrue(fenetre.warning.isVisible())
        self.assertIn("« A »", fenetre.warning.text())

    def test_textes_du_fichier_jamais_interpretes_en_html(self) -> None:
        fenetre = self.fenetre("1 réglage inconnu ignoré : « <b>x</b> ».")
        texte = QtCore.Qt.TextFormat.PlainText
        self.assertEqual(fenetre.header.textFormat(), texte)
        self.assertEqual(fenetre.warning.textFormat(), texte)

    def test_decocher_une_ligne_puis_reprendre(self) -> None:
        fenetre = self.fenetre()
        fenetre.table.item(1, 0).setCheckState(QtCore.Qt.CheckState.Unchecked)
        cliquer(fenetre.take_button)
        self.assertEqual(fenetre.result(), QtGui.QDialog.DialogCode.Accepted)
        self.assertEqual(fenetre.checked_keys(), ["Jeu"])

    def test_annuler(self) -> None:
        fenetre = self.fenetre()
        cliquer(fenetre.cancel_button)
        self.assertEqual(fenetre.result(), QtGui.QDialog.DialogCode.Rejected)


class PaireIncompatible(unittest.TestCase):
    """Deux réglages valides seuls mais pas ensemble : la page refuse d'écrire la paire."""

    def setUp(self) -> None:
        pas = Setting(
            "Pas", Kind.FLOAT, 32.0, "Pas", "Écart.", "Taquets", minimum=7.0, maximum=200.0
        )
        diametre = Setting("Diametre", Kind.FLOAT, 5.0, "Diamètre", "Trou.", "Taquets")

        def compatible(valeurs: Mapping[str, Value]) -> bool:
            return float(valeurs["Pas"]) >= float(valeurs["Diametre"]) + 2.0

        catalogue = Catalog([pas, diametre], [Relation(("Pas", "Diametre"), compatible)])
        self.reglages = Settings(catalogue, MemoryStore())
        self.messages: list[str] = []
        self.page = SettingsPage(catalogue, self.reglages, notify=self.messages.append)
        self.page.form.show()
        self.addCleanup(self.page.form.deleteLater)

    def test_paire_incompatible_non_ecrite_et_signalee(self) -> None:
        self.page.set_pending({"Pas": 10.0, "Diametre": 30.0})
        self.page.saveSettings()
        self.assertEqual((self.reglages.value("Pas"), self.reglages.value("Diametre")), (32.0, 5.0))
        self.assertEqual(self.page._rows["Diametre"].value(), 5.0)  # champ revenu à l'enregistré
        self.assertEqual(len(self.messages), 1)
        self.assertIn("Diamètre", self.messages[0])

    def test_paire_compatible_ecrite_sans_message(self) -> None:
        self.page.set_pending({"Pas": 40.0, "Diametre": 30.0})
        self.page.saveSettings()
        self.assertEqual(
            (self.reglages.value("Pas"), self.reglages.value("Diametre")), (40.0, 30.0)
        )
        self.assertEqual(self.messages, [])
