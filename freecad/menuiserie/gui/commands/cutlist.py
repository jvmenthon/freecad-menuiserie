# SPDX-License-Identifier: LGPL-2.1-or-later
"""Commandes de la liste de débit (J2d, critères G1 à G3, ADR 0012).

« Liste de débit » crée ou met à jour la feuille de calcul du document (une seule transaction,
posée par l'api) puis l'ouvre dans un onglet ; « Exporter la liste de débit (CSV)… » demande un
fichier puis y écrit le CSV. La portée est la sélection courante (objets sans doublon) ou, sans
sélection, tout le document. Aucune des deux ne touche à la sélection ; seul le recalcul du
document, s'il contient des objets à recalculer, précède le calcul (sinon les ajouts des pièces
usinées seraient ignorés). Un refus de l'api est affiché comme celui des assemblages.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any, Final

import FreeCAD as App
import FreeCADGui as Gui

from freecad.menuiserie import api
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.features.cutlist_export import proposed_path, with_csv_suffix
from freecad.menuiserie.features.freecad_types import Document, DocumentObject
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.gui.commands.joints import TransactionCommand, report_refusal

# Noms des commandes, aussi noms de leurs icônes (``<nom>.svg``) et contextes de traduction.
CUT_LIST: Final = "Menuiserie_CutList"
CUT_LIST_EXPORT: Final = "Menuiserie_CutListExport"
COMMANDS: Final = (CUT_LIST, CUT_LIST_EXPORT)
CONFIRMATION_DISPLAY_MS: Final = 10_000  # durée d'affichage de la confirmation d'export
TOUCHED: Final = "Touched"

_DIALOG_TITLE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Exporter la liste de débit")
_DIALOG_FILTER: Final = QT_TRANSLATE_NOOP("Menuiserie", "Fichiers CSV (*.csv)")
_EXPORTED: Final = QT_TRANSLATE_NOOP("Menuiserie", "Liste de débit exportée dans « {path} ».")


def selected_objects() -> list[DocumentObject] | None:
    """Objets sélectionnés du document actif, sans doublon (un objet dont plusieurs éléments
    sont sélectionnés compte une fois), dans l'ordre de sélection ; ``None`` sans sélection :
    la liste couvre alors tout le document. La sélection n'est pas modifiée."""
    found: dict[str, DocumentObject] = {}
    for obj in Gui.Selection.getSelection():
        found.setdefault(obj.Name, obj)
    return list(found.values()) or None


def recompute_if_touched(doc: Document) -> None:
    """Recalcule ``doc`` si un de ses objets est à recalculer : la forme d'une pièce usinée
    n'est à jour qu'ensuite, et la collecte lit ses ajouts (tenons, languettes, queues)."""
    if any(TOUCHED in obj.State for obj in doc.Objects):
        doc.recompute()


def open_in_tab(sheet: DocumentObject) -> None:
    """Ouvre ``sheet`` dans l'onglet de la vue Spreadsheet, comme un double-clic dans l'arbre
    (``doubleClicked`` du ViewProvider, présent en FreeCAD 1.0 et 1.1) ; à défaut, ``setEdit``.
    Sans interface (pas de ViewProvider), ne fait rien."""
    view_object = getattr(sheet, "ViewObject", None)
    if view_object is None:
        return
    try:
        view_object.doubleClicked()
    except (AttributeError, RuntimeError):
        Gui.ActiveDocument.setEdit(sheet.Name)


def show_status(message: str) -> None:
    """Message dans la barre d'état de la fenêtre principale."""
    window = Gui.getMainWindow()
    if window is not None:
        window.statusBar().showMessage(message, CONFIRMATION_DISPLAY_MS)


class CutListCommand(TransactionCommand):
    """Base des commandes de la liste de débit (Command) : active dès qu'un document est
    ouvert et qu'aucun panneau de tâche n'a de transaction en cours (la feuille s'écrit dans la
    sienne, qui validerait celle du panneau)."""

    def IsActive(self) -> bool:
        """Active s'il y a un document et aucun panneau ouvert."""
        return App.ActiveDocument is not None and not Gui.Control.activeDialog()

    def Activated(self) -> None:
        """Portée lue, document recalculé si besoin, puis action de la commande ; un refus de
        l'api est signalé sans rien modifier."""
        doc = App.ActiveDocument
        objects = selected_objects()
        try:
            self.run(doc, objects)
        except (TypeError, ValueError) as error:
            report_refusal(str(error))

    def run(self, doc: Document, objects: Sequence[DocumentObject] | None) -> None:
        """Action propre à la commande, sur ``doc`` limité à ``objects`` (``None`` : tout)."""
        raise NotImplementedError


class CutListSheetCommand(CutListCommand):
    """Crée ou met à jour la feuille « Liste de débit » et l'ouvre dans un onglet."""

    NAME = CUT_LIST
    MENU_TEXT = QT_TRANSLATE_NOOP("Menuiserie_CutList", "Liste de débit")
    TOOL_TIP = QT_TRANSLATE_NOOP(
        "Menuiserie_CutList",
        "Écrit la liste de débit dans une feuille de calcul « Liste de débit » : une ligne par "
        "groupe de pièces identiques (cotes finies et de débit, matériau, volume, masse), les "
        "totaux par matériau et les tourillons. Limitée aux objets sélectionnés, sinon à tout le "
        "document. La feuille n'est pas recalculée toute seule : relancez la commande pour la "
        "mettre à jour (les colonnes ajoutées à droite sont gardées).",
    )

    def run(self, doc: Document, objects: Sequence[DocumentObject] | None) -> None:
        """Feuille écrite par l'api (transaction « Liste de débit », avertissements dans la vue
        rapport), puis ouverte."""
        recompute_if_touched(doc)
        open_in_tab(api.make_cut_list(doc, objects))


class CutListExportCommand(CutListCommand):
    """Exporte la liste de débit en CSV (international : ``,``, point décimal, UTF-8 avec BOM)."""

    NAME = CUT_LIST_EXPORT
    MENU_TEXT = QT_TRANSLATE_NOOP("Menuiserie_CutListExport", "Exporter la liste de débit (CSV)…")
    TOOL_TIP = QT_TRANSLATE_NOOP(
        "Menuiserie_CutListExport",
        "Enregistre la liste de débit dans un fichier CSV au format international (virgule, "
        "point décimal). Limitée aux objets sélectionnés, sinon à tout le document ; "
        "le document n'est pas modifié.",
    )

    def run(self, doc: Document, objects: Sequence[DocumentObject] | None) -> None:
        """Fichier demandé (rien ne se passe si l'on annule), document recalculé si besoin,
        puis CSV écrit par l'api ; confirmation dans la barre d'état."""
        path = ask_path(doc)
        if path is None:
            return
        recompute_if_touched(doc)
        written = api.export_cut_list_csv(doc, path, objects)
        show_status(translated(_EXPORTED, {"path": str(written)}))


def ask_path(doc: Document) -> Path | None:
    """Boîte d'enregistrement (filtre ``*.csv``), au nom proposé « <document> - liste de
    débit.csv » à côté du fichier du document, ou dans le dossier personnel s'il n'est pas
    enregistré. ``None`` si l'utilisateur annule ; « .csv » est ajouté s'il n'a rien saisi
    comme extension."""
    from PySide import QtGui

    proposed = proposed_path(doc.Label, doc.FileName)
    answer: Any = QtGui.QFileDialog.getSaveFileName(
        Gui.getMainWindow(), translated(_DIALOG_TITLE), str(proposed), translated(_DIALOG_FILTER)
    )
    chosen = answer[0] if isinstance(answer, tuple) else answer
    return Path(with_csv_suffix(chosen)) if chosen else None


def register() -> None:
    """Enregistre les commandes de la liste de débit auprès de FreeCAD."""
    Gui.addCommand(CUT_LIST, CutListSheetCommand())
    Gui.addCommand(CUT_LIST_EXPORT, CutListExportCommand())
