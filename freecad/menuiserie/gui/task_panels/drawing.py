# SPDX-License-Identifier: LGPL-2.1-or-later
"""Panneau « Plan de l'ouvrage » (issue #153, ADR 0053, lot P-b).

Format et sens de la feuille (préremplis par la configuration de l'atelier), titre, client et
numéro de devis (facultatifs), case « Exporter en PDF ». « OK » crée ou refait la page par l'api
(sa propre transaction), l'ouvre, puis propose le fichier PDF si la case est cochée. Le panneau
n'ouvre aucune transaction : « Annuler » ne laisse rien.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Final

import FreeCADGui as Gui
from PySide import QtGui

from freecad.menuiserie import api
from freecad.menuiserie.core.drawing import MAX_FIELD_LENGTH, PAGE_FORMATS, Orientation
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.features import drawing_settings
from freecad.menuiserie.features.drawing import drawing_sources, find_overall_drawing
from freecad.menuiserie.features.drawing_title import STORED
from freecad.menuiserie.features.freecad_types import Document, DocumentObject
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.gui import drawing_pdf

__all__ = ["FORM_NAME", "DrawingTaskPanel"]

FORM_NAME: Final = "MenuiserieDrawingPanel"
_TITLE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Plan de l'ouvrage")
_SCOPE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Dessine : {labels}")
_FORMAT: Final = QT_TRANSLATE_NOOP("Menuiserie", "Format")
_ORIENTATION: Final = QT_TRANSLATE_NOOP("Menuiserie", "Sens")
_LANDSCAPE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Paysage")
_PORTRAIT: Final = QT_TRANSLATE_NOOP("Menuiserie", "Portrait")
_WORK: Final = QT_TRANSLATE_NOOP("Menuiserie", "Ouvrage")
_CLIENT: Final = QT_TRANSLATE_NOOP("Menuiserie", "Client (facultatif)")
_QUOTE: Final = QT_TRANSLATE_NOOP("Menuiserie", "N° de devis (facultatif)")
_PDF: Final = QT_TRANSLATE_NOOP("Menuiserie", "Exporter aussi en PDF")
_HINT: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Le format par défaut se règle dans la configuration de l'atelier. Les cotes suivent le "
    "modèle ; relancer la commande refait la mise en page.",
)
_MAX_LABELS: Final = 4


def _scope_text(objects: Sequence[DocumentObject]) -> str:
    labels = [str(obj.Label) for obj in objects[:_MAX_LABELS]]
    if len(objects) > _MAX_LABELS:
        labels.append("…")
    return translated(_SCOPE, {"labels": ", ".join(labels)})


class DrawingTaskPanel:
    """Panneau du plan de l'ouvrage de ``objects`` dans ``doc``."""

    def __init__(self, doc: Document, objects: Sequence[DocumentObject]) -> None:
        self.doc = doc
        self.objects = list(objects)
        self.page: DocumentObject | None = None
        self.form = QtGui.QWidget()
        self.form.setObjectName(FORM_NAME)
        self.form.setWindowTitle(translated(_TITLE))
        layout = QtGui.QFormLayout(self.form)
        layout.addRow(QtGui.QLabel(_scope_text(self.objects)))
        self.page_format = QtGui.QComboBox()
        self.page_format.addItems(list(PAGE_FORMATS))
        self.page_format.setCurrentText(drawing_settings.default_format())
        layout.addRow(translated(_FORMAT), self.page_format)
        self.orientation = QtGui.QComboBox()
        self.orientation.addItem(translated(_LANDSCAPE), Orientation.LANDSCAPE.value)
        self.orientation.addItem(translated(_PORTRAIT), Orientation.PORTRAIT.value)
        default = drawing_settings.default_orientation()
        self.orientation.setCurrentIndex(0 if default is Orientation.LANDSCAPE else 1)
        layout.addRow(translated(_ORIENTATION), self.orientation)
        existing = self._existing_page()
        self.title = self._line(layout, _WORK, existing, "title")
        self.client = self._line(layout, _CLIENT, existing, "client")
        self.quote = self._line(layout, _QUOTE, existing, "quote")
        self.pdf = QtGui.QCheckBox(translated(_PDF))
        layout.addRow(self.pdf)
        hint = QtGui.QLabel(translated(_HINT))
        hint.setWordWrap(True)
        layout.addRow(hint)

    def _existing_page(self) -> DocumentObject | None:
        try:
            return find_overall_drawing(self.doc, drawing_sources(self.doc, self.objects))
        except ValueError:
            return None

    @staticmethod
    def _line(layout: Any, label: str, page: DocumentObject | None, key: str) -> Any:
        field = QtGui.QLineEdit(str(getattr(page, STORED[key], "")) if page is not None else "")
        field.setMaxLength(MAX_FIELD_LENGTH)
        layout.addRow(translated(label), field)
        return field

    def options(self) -> api.DrawingOptions:
        """Choix du panneau ; un titre laissé vide reprend le nom de l'ouvrage."""
        title = self.title.text().strip()
        return api.DrawingOptions(
            page_format=self.page_format.currentText(),
            orientation=Orientation(self.orientation.currentData()),
            title=title or None,
            client=self.client.text(),
            quote=self.quote.text(),
        )

    def accept(self) -> bool:
        """Crée ou refait la page, l'ouvre et, si demandé, l'exporte en PDF ; un refus de l'api
        laisse le panneau ouvert."""
        from freecad.menuiserie.gui.commands.base import report_refusal

        try:
            self.page = api.make_overall_drawing(self.doc, self.objects, self.options())
        except (TypeError, ValueError) as error:
            report_refusal(str(error))
            return False
        Gui.Control.closeDialog()
        drawing_pdf.show_page(self.page)
        if self.pdf.isChecked():
            from freecad.menuiserie.gui.commands.drawing import export_with_dialog

            export_with_dialog(self.page)
        return True

    def reject(self) -> bool:
        """Ferme sans rien créer."""
        Gui.Control.closeDialog()
        return True

    def getStandardButtons(self) -> int:
        """Boutons « OK » et « Annuler »."""
        return int(QtGui.QDialogButtonBox.Ok | QtGui.QDialogButtonBox.Cancel)
