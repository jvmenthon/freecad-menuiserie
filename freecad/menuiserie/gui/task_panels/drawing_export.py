# SPDX-License-Identifier: LGPL-2.1-or-later
"""Panneau « Exporter en PDF » (issue #153, retour de jv du 24/11, maquette B choisie).

Même arbre à cocher que « Plans de pièce » (ensembles, pièces, copies par lien), précédé des
plans de l'ouvrage (existants, ou à créer) et des autres pages. Une seconde colonne dit pour
chaque pièce si son plan existe ou s'il sera créé. Ce qui était sélectionné avant le clic est
déjà coché. « OK » crée les plans qui manquent puis écrit toutes les pages cochées dans un seul
PDF, ouvert ensuite si la case « Ouvrir le PDF » (précochée) le demande ; « Annuler » ne laisse
rien. Le fichier est vérifié avant de créer les plans (s'il existe : écraser, « <nom> 2 » ou
annuler) ; si l'écriture échoue ensuite, les plans créés restent (annulables) et le panneau
reste ouvert.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Final

import FreeCADGui as Gui
from PySide import QtCore, QtGui

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.text import escaped_text
from freecad.menuiserie.features.cutlist_export import PDF_SUFFIX, validated_path, with_suffix
from freecad.menuiserie.features.drawing import TITLE as OVERALL_TITLE
from freecad.menuiserie.features.drawing import DrawingOptions, is_page
from freecad.menuiserie.features.drawing_exploded import TITLE as EXPLODED_TITLE
from freecad.menuiserie.features.drawing_export import (
    ExportState,
    PlanKind,
    export_state,
    pages_to_export,
)
from freecad.menuiserie.features.drawing_parts import blanks_of
from freecad.menuiserie.features.freecad_types import Document, DocumentObject
from freecad.menuiserie.features.i18n import report_warning, translated
from freecad.menuiserie.gui import existing_file
from freecad.menuiserie.gui.commands.base import report_refusal
from freecad.menuiserie.gui.commands.cutlist import show_status
from freecad.menuiserie.gui.drawing_hlr import HlrWait
from freecad.menuiserie.gui.drawing_pdf import ask_save_path
from freecad.menuiserie.gui.drawing_pdf_pages import export_pages_pdf, proposed_plans_path
from freecad.menuiserie.gui.task_panels.part_drawings import (
    NAME_ROLE,
    PartDrawingsTaskPanel,
    check_state,
    counted,
)

__all__ = ["FORM_NAME", "ExportPdfTaskPanel", "open_url"]

FORM_NAME: Final = "MenuiserieExportPdfPanel"
KIND_ROLE: Final = QtCore.Qt.UserRole + 1  # genre du plan de l'ouvrage à créer
_TITLE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Exporter en PDF")
_HINT: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Cochez les plans à exporter, ou des pièces : leur plan est créé s'il manque. Tout part dans "
    "un seul PDF, une page par plan.",
)
_EXISTS: Final = QT_TRANSLATE_NOOP("Menuiserie", "plan existant")
_TO_CREATE: Final = QT_TRANSLATE_NOOP("Menuiserie", "à créer")
_FILE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Fichier :")
_OPEN: Final = QT_TRANSLATE_NOOP("Menuiserie", "Ouvrir le PDF après l'export")
_NOT_OPENED: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Le PDF est écrit mais n'a pas pu être ouvert : « {path} »."
)
_BROWSE: Final = QT_TRANSLATE_NOOP("Menuiserie", "…")
_DIALOG: Final = QT_TRANSLATE_NOOP("Menuiserie", "Exporter les plans")
_FILTER: Final = QT_TRANSLATE_NOOP("Menuiserie", "Fichiers PDF (*.pdf)")
_COUNT: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "{count} pages dans un seul PDF, dont {new} à créer."
)
_COUNT_ONE: Final = QT_TRANSLATE_NOOP("Menuiserie", "{count} page dans le PDF, dont {new} à créer.")
_NOTHING: Final = QT_TRANSLATE_NOOP("Menuiserie", "Export PDF : cochez au moins un plan.")
_NO_FILE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Export PDF : choisissez le fichier.")
_DONE: Final = QT_TRANSLATE_NOOP("Menuiserie", "{count} plans exportés dans « {path} ».")
_DONE_ONE: Final = QT_TRANSLATE_NOOP("Menuiserie", "1 plan exporté dans « {path} ».")


def open_url(url: Any) -> bool:
    """Ouvre ``url`` dans l'application du système (remplaçable dans les vérifications)."""
    return bool(QtGui.QDesktopServices.openUrl(url))


def _open_in_viewer(path: Path) -> None:
    """Ouvre ``path`` dans le lecteur de PDF du système ; un avertissement si c'est refusé."""
    if not open_url(QtCore.QUrl.fromLocalFile(str(path))):
        report_warning(translated(_NOT_OPENED, {"path": escaped_text(str(path))}))


def _resize_mode(name: str) -> Any:
    modes = getattr(QtGui.QHeaderView, "ResizeMode", QtGui.QHeaderView)
    return getattr(QtGui.QHeaderView, name, None) or getattr(modes, name)


class ExportPdfTaskPanel(PartDrawingsTaskPanel):
    """Panneau du choix des plans à exporter dans un seul PDF, dans ``doc`` ; ``selected`` (la
    sélection d'avant le clic : pages, pièces, ensembles) est précochée."""

    FORM_NAME = FORM_NAME
    TITLE = _TITLE
    HINT = _HINT

    def __init__(self, doc: Document, selected: list[DocumentObject] | None = None) -> None:
        self.plans: ExportState = export_state(doc)
        self._selected = list(selected or [])
        self.written: Path | None = None
        self._confirmed: Path | None = None  # écrasement déjà validé par la boîte « … »
        super().__init__(doc)

    def _add_options(self, layout: Any) -> None:
        self.tree.setColumnCount(2)
        header = self.tree.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, _resize_mode("Stretch"))
        header.setSectionResizeMode(1, _resize_mode("ResizeToContents"))
        row = QtGui.QHBoxLayout()
        row.addWidget(QtGui.QLabel(translated(_FILE)))
        self.path = QtGui.QLineEdit(str(proposed_plans_path(self.doc)))
        row.addWidget(self.path, 1)
        browse = QtGui.QPushButton(translated(_BROWSE))
        browse.clicked.connect(self._browse)
        row.addWidget(browse)
        layout.addLayout(row)
        self.open_pdf = QtGui.QCheckBox(translated(_OPEN))
        self.open_pdf.setChecked(True)  # le cas courant : relire le PDF tout de suite
        layout.addWidget(self.open_pdf)

    def _fill(self) -> None:
        """Plans de l'ouvrage (à créer s'il n'y en a pas), autres pages, puis l'arbre des
        ensembles avec l'état du plan de chaque pièce ; la sélection d'avant est cochée."""
        for kind, title in ((PlanKind.OVERALL, OVERALL_TITLE), (PlanKind.EXPLODED, EXPLODED_TITLE)):
            if kind not in self.plans.kinds:
                item = self.new_item(translated(title), "")
                item.setData(0, KIND_ROLE, kind.value)
                item.setText(1, translated(_TO_CREATE))
                self.tree.addTopLevelItem(item)
        for page in self.plans.other_pages:
            item = self.new_item(str(page.Label), page.Name)
            item.setText(1, translated(_EXISTS))
            self.tree.addTopLevelItem(item)
        super()._fill()
        for item in self.items():
            obj = self._object(item)
            if obj is not None and not is_page(obj) and item.childCount() == 0:
                missing = self.plans.missing(self._blanks(obj))
                item.setText(1, translated(_TO_CREATE if missing else _EXISTS))
        for obj in self._selected:
            self.check(obj.Name)

    def _object(self, item: Any) -> DocumentObject | None:
        name = item.data(0, NAME_ROLE)
        return self.doc.getObject(name) if name else None

    @staticmethod
    def _blanks(obj: DocumentObject) -> list[DocumentObject]:
        try:
            return blanks_of([obj])
        except ValueError:  # document démesuré : la ligne reste « à créer »
            return []

    def check(self, name: str) -> None:
        """Coche la ligne de ``name`` ; une page de plan de pièce coche ses pièces."""
        page = self.doc.getObject(name)
        mapped = self.plans.parts_of(page) if page is not None and is_page(page) else []
        if not mapped:
            super().check(name)
            return
        for key in mapped:
            super().check(key)

    def _kinds(self) -> list[PlanKind]:
        checked = check_state("Checked")
        return [
            PlanKind(item.data(0, KIND_ROLE))
            for item in self.items()
            if item.data(0, KIND_ROLE) is not None and item.checkState(0) == checked
        ]

    def _count_text(self, chosen: list[DocumentObject]) -> str:
        pages = [obj for obj in chosen if is_page(obj)]
        try:
            blanks = blanks_of([obj for obj in chosen if not is_page(obj)])
        except ValueError:
            blanks = []
        new = self.plans.plans_to_create(blanks) + len(self._kinds())
        count = len(pages) + len(self.plans.blank_pages(blanks)) + new
        values = {"new": str(new)}
        return counted(count, _COUNT_ONE, _COUNT, values)

    def _browse(self, *_args: object) -> None:
        chosen = ask_save_path(Path(self.path.text()), title=_DIALOG)
        if chosen is not None:
            self._confirmed = chosen
            self.path.setText(str(chosen))

    def _free_target(self, target: Path) -> Path | None:
        """``target`` si l'écrasement est déjà validé ou s'il est libre ; sinon le choix de
        l'utilisateur (écraser, « <nom> 2 », annuler), écrit dans le champ du fichier."""
        if target == self._confirmed:
            return target
        chosen = existing_file.free_target(target)
        if chosen is not None:
            self.path.setText(str(chosen))
        return chosen

    def accept(self) -> bool:
        """Crée les plans qui manquent, écrit le PDF et ferme ; un refus (rien de coché, pas de
        fichier, plan ou fichier impossible) laisse le panneau ouvert."""
        chosen, kinds = self.chosen(), self._kinds()  # lus avant la fermeture
        wants_open = self.open_pdf.isChecked()
        path = self.path.text().strip()
        if not chosen and not kinds:
            report_refusal(translated(_NOTHING))
            return False
        if not path:
            report_refusal(translated(_NO_FILE))
            return False
        pages = [obj for obj in chosen if is_page(obj)]
        parts = [obj for obj in chosen if not is_page(obj)]
        try:
            target = self._free_target(validated_path(with_suffix(path, PDF_SUFFIX), PDF_SUFFIX))
            if target is None:  # l'utilisateur garde le panneau pour changer de fichier
                return False
            options = DrawingOptions(settle=HlrWait())
            found = pages_to_export(self.doc, pages, parts, kinds, options)
            self.written = export_pages_pdf(found, target)
        except (TypeError, ValueError, OSError, RuntimeError) as error:
            report_refusal(str(error))
            return False
        self.detach()
        Gui.Control.closeDialog()
        values = {"path": escaped_text(str(self.written))}
        show_status(counted(len(found), _DONE_ONE, _DONE, values))
        if wants_open:
            _open_in_viewer(self.written)
        return True
